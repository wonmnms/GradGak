"""별도 임시 스키마에서 전체 DB 구성을 재현하고 해당 임시 스키마만 정리한다."""

import re
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

import app.db
from alembic import command
from app.models import Base
from app.seed_official_ai_group import seed_verified_ai_group
from app.seed_official_common import seed_verified_common_rules
from app.seed_official_credits import seed_verified_credit_rules
from app.seed_official_engineering import seed_verified_engineering_rules
from app.services.rule_repository import get_rule_bundle


def main():
    original_engine = app.db.engine
    schema = f"gradgak_verify_{uuid4().hex}"
    if not re.fullmatch(r"gradgak_verify_[0-9a-f]{32}", schema):
        raise ValueError("Unexpected temporary schema name")
    isolated_engine = create_engine(
        original_engine.url, connect_args={"options": f"-csearch_path={schema}"}
    )
    created = False
    try:
        with original_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        app.db.engine = isolated_engine
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        command.check(config)

        tables = set(inspect(isolated_engine).get_table_names())
        assert tables == set(Base.metadata.tables) | {"alembic_version"}
        seeders = (
            seed_verified_credit_rules,
            seed_verified_ai_group,
            seed_verified_common_rules,
            seed_verified_engineering_rules,
        )
        with Session(isolated_engine) as session, session.begin():
            for seed in seeders:
                seed(session)
            before = {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }
            for seed in seeders:
                seed(session)
            after = {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }
            assert before == after
            for program in ("engineering", "general"):
                for sub_major in ("software", "ai"):
                    bundle = get_rule_bundle(session, 2024, program, sub_major)
                    assert bundle["data_complete"] is False
            print("Fresh migrations, repeatable seeds and all 4 rule lookups passed.")
            print(after)
    finally:
        app.db.engine = original_engine
        isolated_engine.dispose()
        if created:
            with original_engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            print("Owned temporary schema removed; existing schemas were not changed.")


if __name__ == "__main__":
    main()
