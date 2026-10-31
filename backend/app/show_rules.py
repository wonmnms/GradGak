"""규칙 조회 시연용 CLI. 학생 정보를 입력하거나 저장하지 않는다."""

import argparse
import json

from app.db import SessionLocal
from app.services.rule_repository import get_rule_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--program", choices=("engineering", "general"), default="engineering")
    parser.add_argument("--sub-major", choices=("software", "ai"), default="ai")
    args = parser.parse_args()
    with SessionLocal() as session:
        result = get_rule_bundle(session, args.year, args.program, args.sub_major)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
