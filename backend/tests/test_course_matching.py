"""Course identity matching with fictional catalog data only, never private history."""

import unicodedata
from unittest.mock import Mock

import pytest

from app.schemas.course_matching import (
    CatalogCourse,
    CourseAlias,
    CourseCatalogSnapshot,
    CourseEquivalence,
)
from app.schemas.transcripts import Course
from app.services.course_catalog import CourseCatalogRepository
from app.services.course_matching import (
    CatalogValidationError,
    match_courses,
    match_courses_from_repository,
)
from app.services.transcript_parser import parse_transcript
from tests.test_transcript_parser import HEADERS, make_pdf


def taken(name="가상기초", code=None, **changes):
    values = {
        "year": 2031,
        "term": "1",
        "course_code": code,
        "name": name,
        "category": "전선",
        "credits": 3,
        "grade": "B0",
        "is_retake": False,
    }
    values.update(changes)
    return Course(**values)


def master(course_id="fake-a", code="FAKE-101", name="가상기초"):
    return CatalogCourse(course_id=course_id, course_code=code, name=name)


def alias(name, course_id="fake-a", source="synthetic://verified-alias"):
    return CourseAlias(name=name, course_id=course_id, source_document=source)


def equivalent(source="fake-a", target="fake-b", document="synthetic://verified-equivalence"):
    return CourseEquivalence(
        source_course_id=source, target_course_id=target, source_document=document
    )


def snapshot(*courses, aliases=(), equivalences=()):
    return CourseCatalogSnapshot(
        courses=list(courses), aliases=list(aliases), equivalences=list(equivalences)
    )


def candidate_ids(result):
    return [candidate.course.course_id for candidate in result.candidates]


def test_code_wins_even_when_transcript_name_identifies_another_course():
    catalog = snapshot(master(), master("fake-b", "FAKE-102", "가상심화"))
    original = taken("가상심화", "FAKE-101")
    result = match_courses([original], catalog)
    match = result.matched[0]
    assert match.matched_course.course_id == "fake-a"
    assert match.lookup == "course_code"
    assert match.candidates[0].matched_by == ["course_code"]
    assert match.original.model_dump() == original.model_dump()
    assert result.unmatched == result.ambiguous == []


def test_unknown_supplied_code_does_not_fall_back_to_current_name_or_alias():
    catalog = snapshot(master(), aliases=[alias("가상옛이름")])
    result = match_courses(
        [taken("가상기초", "FAKE-999"), taken("가상옛이름", "FAKE-998")], catalog
    )
    assert [item.index for item in result.unmatched] == [0, 1]
    assert all(item.lookup == "course_code" for item in result.unmatched)
    assert all(item.candidates == [] and item.matched_course is None for item in result.unmatched)
    assert all(item.reason for item in result.unmatched)
    assert result.matched == []


@pytest.mark.parametrize(
    ("provided", "catalog_code"),
    [
        ("fake-101", "FAKE-101"),
        ("FAKE-01", "FAKE-1"),
        ("FAKE101", "FAKE-101"),
        ("FAKE 101", "FAKE101"),
    ],
)
def test_code_identity_does_not_discard_case_digits_or_punctuation(provided, catalog_code):
    result = match_courses([taken(code=provided)], snapshot(master(code=catalog_code)))
    assert len(result.unmatched) == 1
    assert result.matched == []


def test_outer_code_whitespace_is_accepted():
    result = match_courses([taken(code="  FAKE-101  ")], snapshot(master()))
    assert result.matched[0].matched_course.course_id == "fake-a"


def test_duplicate_catalog_codes_are_ambiguous_even_if_name_matches_only_one():
    catalog = snapshot(master(), master("fake-b", "FAKE-101", "가상심화"))
    result = match_courses([taken(code="FAKE-101")], catalog)
    ambiguous = result.ambiguous[0]
    assert ambiguous.lookup == "course_code"
    assert ambiguous.matched_course is None
    assert candidate_ids(ambiguous) == ["fake-a", "fake-b"]
    assert all(candidate.matched_by == ["course_code"] for candidate in ambiguous.candidates)
    assert result.matched == []


@pytest.mark.parametrize(
    "name",
    ["가 상 기 초", "가상\t기초\n", "가상\u3000기초", unicodedata.normalize("NFD", "가상기초")],
)
def test_no_code_name_matching_handles_pdf_whitespace_and_unicode(name):
    result = match_courses([taken(name)], snapshot(master()))
    match = result.matched[0]
    assert match.lookup == "name"
    assert match.candidates[0].matched_by == ["name"]
    assert match.matched_course.course_id == "fake-a"


def test_name_matching_is_case_insensitive_for_english_text():
    result = match_courses([taken("가상 api 설계")], snapshot(master(name="가상API설계")))
    assert result.matched[0].matched_course.course_id == "fake-a"


@pytest.mark.parametrize(
    ("provided", "catalog_name"),
    [
        ("가상C", "가상C++"),
        ("가상C#", "가상C++"),
        ("가상과목1", "가상과목2"),
        ("가상과목I", "가상과목Ⅰ"),
        ("가상과목1", "가상과목１"),
        ("가상기초론", "가상기초"),
    ],
)
def test_name_matching_does_not_guess_similar_names_or_remove_meaningful_symbols(
    provided, catalog_name
):
    result = match_courses([taken(provided)], snapshot(master(name=catalog_name)))
    assert len(result.unmatched) == 1
    assert result.matched == []


def test_duplicate_normalized_current_names_are_ambiguous():
    catalog = snapshot(master(name="가상 기초"), master("fake-b", "FAKE-102", "가상기초"))
    result = match_courses([taken()], catalog)
    assert candidate_ids(result.ambiguous[0]) == ["fake-a", "fake-b"]
    assert result.ambiguous[0].matched_course is None


def test_old_name_alias_maps_to_existing_course_with_source_evidence():
    result = match_courses(
        [taken("가상 옛 이름")], snapshot(master(), aliases=[alias("가상옛이름")])
    )
    match = result.matched[0]
    assert match.matched_course.course_id == "fake-a"
    assert match.candidates[0].matched_by == ["alias"]
    assert match.candidates[0].source_documents == ["synthetic://verified-alias"]
    assert match.original.name == "가상 옛 이름"


def test_repeated_alias_records_for_one_course_do_not_create_false_ambiguity():
    catalog = snapshot(
        master(),
        aliases=[
            alias("가상옛이름", source="synthetic://source-b"),
            alias("가상옛이름", source="synthetic://source-a"),
            alias("가상옛이름", source="synthetic://source-a"),
        ],
    )
    result = match_courses([taken("가상옛이름")], catalog)
    assert len(result.matched[0].candidates) == 1
    assert result.matched[0].candidates[0].source_documents == [
        "synthetic://source-a",
        "synthetic://source-b",
    ]
    assert result.ambiguous == []


def test_current_and_alias_names_for_same_course_merge_evidence():
    result = match_courses([taken()], snapshot(master(), aliases=[alias("가상기초")]))
    candidate = result.matched[0].candidates[0]
    assert set(candidate.matched_by) == {"name", "alias"}
    assert candidate.source_documents == ["synthetic://verified-alias"]
    assert result.ambiguous == []


def test_current_name_and_another_courses_alias_are_ambiguous():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상심화"),
        aliases=[alias("가상기초", "fake-b")],
    )
    result = match_courses([taken()], catalog)
    assert candidate_ids(result.ambiguous[0]) == ["fake-a", "fake-b"]
    assert [candidate.matched_by for candidate in result.ambiguous[0].candidates] == [
        ["name"],
        ["alias"],
    ]
    assert result.matched == []


def test_one_alias_name_for_multiple_courses_is_ambiguous():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상심화"),
        aliases=[alias("가상공통옛이름"), alias("가상공통옛이름", "fake-b")],
    )
    result = match_courses([taken("가상공통옛이름")], catalog)
    assert candidate_ids(result.ambiguous[0]) == ["fake-a", "fake-b"]


def test_every_input_is_preserved_once_in_order_including_failures_and_ambiguity():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상모호"),
        master("fake-c", "FAKE-103", "가상모호"),
    )
    originals = [taken(), taken("가상미등록", grade=None), taken("가상모호", grade="F")]
    result = match_courses(originals, catalog)
    assert [item.index for item in result.matched] == [0]
    assert [item.index for item in result.unmatched] == [1]
    assert [item.index for item in result.ambiguous] == [2]
    assert [item.status for item in result.ordered_results] == ["matched", "unmatched", "ambiguous"]
    assert [item.original.model_dump() for item in result.ordered_results] == [
        original.model_dump() for original in originals
    ]
    assert result.unmatched[0].reason and result.ambiguous[0].reason


def test_empty_catalog_preserves_every_input_as_unmatched():
    originals = [taken(), taken("가상다른과목", code="FAKE-999")]
    result = match_courses(originals, snapshot())
    assert len(result.unmatched) == 2
    assert result.matched == result.ambiguous == []
    assert [item.original for item in result.ordered_results] == originals


def test_empty_input_returns_empty_groups():
    result = match_courses([], snapshot(master()))
    assert result.ordered_results == []
    assert result.matched == result.unmatched == result.ambiguous == []
    assert result.duplicate_inputs == result.repeated_matches == []


def test_equivalence_candidates_do_not_replace_the_matched_source_course():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상인정대상"),
        equivalences=[equivalent()],
    )
    original = taken(credits=1.5, grade="F")
    match = match_courses([original], catalog).matched[0]
    assert match.matched_course.course_id == "fake-a"
    assert match.original.credits == 1.5
    assert match.original.grade == "F"
    assert len(match.equivalence_candidates) == 1
    relation = match.equivalence_candidates[0]
    assert relation.source_course_id == "fake-a"
    assert relation.target.course_id == "fake-b"
    assert relation.source_documents == ["synthetic://verified-equivalence"]


def test_equivalence_does_not_apply_in_reverse_or_transitively():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상중간"),
        master("fake-c", "FAKE-103", "가상최종"),
        equivalences=[equivalent(), equivalent("fake-b", "fake-c")],
    )
    result = match_courses([taken(), taken("가상최종")], catalog)
    assert [item.target.course_id for item in result.matched[0].equivalence_candidates] == [
        "fake-b"
    ]
    assert result.matched[1].equivalence_candidates == []


def test_explicit_equivalence_cycle_is_finite_and_remains_one_hop():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상연결"),
        equivalences=[equivalent(), equivalent("fake-b", "fake-a")],
    )
    result = match_courses([taken(), taken("가상연결")], catalog)
    assert [item.target.course_id for item in result.matched[0].equivalence_candidates] == [
        "fake-b"
    ]
    assert [item.target.course_id for item in result.matched[1].equivalence_candidates] == [
        "fake-a"
    ]


def test_duplicate_equivalence_links_merge_source_documents():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상연결"),
        equivalences=[
            equivalent(document="synthetic://source-b"),
            equivalent(document="synthetic://source-a"),
            equivalent(document="synthetic://source-a"),
        ],
    )
    relations = match_courses([taken()], catalog).matched[0].equivalence_candidates
    assert len(relations) == 1
    assert relations[0].source_documents == ["synthetic://source-a", "synthetic://source-b"]


def test_ambiguous_identity_does_not_choose_an_equivalence_target():
    catalog = snapshot(
        master(),
        master("fake-b", "FAKE-102", "가상기초"),
        master("fake-c", "FAKE-103", "가상연결"),
        equivalences=[equivalent("fake-a", "fake-c")],
    )
    result = match_courses([taken()], catalog)
    assert len(result.ambiguous) == 1
    assert result.ambiguous[0].equivalence_candidates == []
    assert result.ambiguous[0].matched_course is None


@pytest.mark.parametrize("status", ["matched", "unmatched", "ambiguous"])
def test_exact_duplicate_inputs_are_flagged_but_not_dropped_in_any_result_group(status):
    catalog = snapshot(master())
    if status == "unmatched":
        catalog = snapshot()
    elif status == "ambiguous":
        catalog = snapshot(master(), master("fake-b", "FAKE-102", "가상기초"))
    original = taken()
    result = match_courses(
        [original, original.model_copy(deep=True), original.model_copy(deep=True)], catalog
    )
    items = getattr(result, status)
    assert [item.index for item in items] == [0, 1, 2]
    assert [item.duplicate_of for item in items] == [None, 0, 0]
    assert [(item.index, item.duplicate_of) for item in result.duplicate_inputs] == [(1, 0), (2, 0)]
    assert len(result.ordered_results) == 3


def test_repeated_course_history_is_not_treated_as_duplicate_input_or_filtered():
    originals = [
        taken(year=2030, grade="F"),
        taken(year=2030, term="2", grade="C+(삭제)"),
        taken(year=2031, grade="NP", is_retake=True),
        taken(year=2031, term="2", grade=None, is_retake=True),
    ]
    result = match_courses(originals, snapshot(master()))
    assert len(result.matched) == 4
    assert result.duplicate_inputs == []
    assert all(item.duplicate_of is None for item in result.matched)
    assert [(group.course_id, group.indices) for group in result.repeated_matches] == [
        ("fake-a", [0, 1, 2, 3])
    ]
    assert [item.original.model_dump() for item in result.ordered_results] == [
        original.model_dump() for original in originals
    ]


def test_name_alias_and_code_matches_to_same_course_are_reported_as_repeated_identity():
    catalog = snapshot(master(), aliases=[alias("가상옛이름")])
    originals = [
        taken(),
        taken("가상옛이름", term="2"),
        taken("가상이름수정", "FAKE-101", year=2032),
    ]
    result = match_courses(originals, catalog)
    assert len(result.matched) == 3
    assert result.duplicate_inputs == []
    assert result.repeated_matches[0].course_id == "fake-a"
    assert result.repeated_matches[0].indices == [0, 1, 2]


def test_matching_does_not_mutate_inputs_or_catalog_and_result_owns_input_copy():
    original = taken()
    catalog = snapshot(master(), aliases=[alias("가상옛이름")])
    before_course = original.model_dump()
    before_catalog = catalog.model_dump()
    result = match_courses([original], catalog)
    assert original.model_dump() == before_course
    assert catalog.model_dump() == before_catalog
    result.matched[0].original.name = "가상검수수정"
    assert original.name == before_course["name"]


def test_ambiguity_candidate_order_does_not_depend_on_catalog_order():
    records = [master("fake-b", "FAKE-102"), master("fake-a", "FAKE-101")]
    first = match_courses([taken()], snapshot(*records)).ambiguous[0]
    second = match_courses([taken()], snapshot(*reversed(records))).ambiguous[0]
    assert candidate_ids(first) == candidate_ids(second) == ["fake-a", "fake-b"]


def test_catalog_snapshots_are_scoped_per_call_without_a_global_matching_cache():
    first = match_courses([taken()], snapshot(master("fake-context-a")))
    second = match_courses([taken()], snapshot(master("fake-context-b")))
    assert first.matched[0].matched_course.course_id == "fake-context-a"
    assert second.matched[0].matched_course.course_id == "fake-context-b"


@pytest.mark.parametrize(
    "catalog",
    [
        snapshot(master(), master()),
        snapshot(master(), master("fake-a", "FAKE-999", "가상충돌")),
        snapshot(master(), aliases=[alias("가상옛이름", "missing")]),
        snapshot(master(), equivalences=[equivalent("missing", "fake-a")]),
        snapshot(master(), equivalences=[equivalent("fake-a", "missing")]),
        snapshot(master(), equivalences=[equivalent("fake-a", "fake-a")]),
    ],
)
def test_invalid_catalog_references_fail_instead_of_becoming_unmatched_success(catalog):
    with pytest.raises(CatalogValidationError):
        match_courses([taken()], catalog)


def test_repository_is_loaded_once_for_the_whole_batch():
    repository = Mock(spec=CourseCatalogRepository)
    repository.load_snapshot.return_value = snapshot(master())
    result = match_courses_from_repository([taken(), taken(term="2")], repository)
    repository.load_snapshot.assert_called_once_with()
    assert len(result.matched) == 2


def test_repository_failure_is_not_replaced_with_unmatched_courses():
    repository = Mock(spec=CourseCatalogRepository)
    repository.load_snapshot.side_effect = RuntimeError("Synthetic catalog unavailable")
    with pytest.raises(RuntimeError, match="Synthetic catalog unavailable"):
        match_courses_from_repository([taken()], repository)
    repository.load_snapshot.assert_called_once_with()


def test_45_fictional_courses_without_codes_match_current_names_and_verified_aliases():
    records = []
    aliases = []
    originals = []
    expected_ids = []
    for number in range(1, 46):
        course_id = f"fake-course-{number:03d}"
        canonical_name = f"가상과목{number:03d}"
        records.append(master(course_id, f"FAKE-{number:03d}", canonical_name))
        if number % 3 == 0:
            old_name = f"가상옛이름{number:03d}"
            aliases.append(alias(old_name, course_id, f"synthetic://verified-alias-{number}"))
            name = f"가상 옛이름 {number:03d}"
        else:
            name = f"가상\t과목 {number:03d}"
        originals.append(
            taken(
                name,
                year=2030 + (number - 1) // 15,
                term=["1", "summer", "winter"][(number - 1) // 15],
                grade=["F", "NP", None, "C+(삭제)", "A0"][(number - 1) % 5],
                is_retake=number % 5 == 0,
            )
        )
        expected_ids.append(course_id)
    result = match_courses(originals, snapshot(*records, aliases=aliases))
    assert all(original.course_code is None for original in originals)
    assert len(result.matched) == 45
    assert result.unmatched == result.ambiguous == []
    assert [item.matched_course.course_id for item in result.ordered_results] == expected_ids
    assert sum(item.candidates[0].matched_by == ["alias"] for item in result.matched) == 15
    assert [item.original.model_dump() for item in result.ordered_results] == [
        original.model_dump() for original in originals
    ]


def test_generated_pdf_without_course_code_connects_to_matcher_without_changing_parser():
    parsed = parse_transcript(
        make_pdf([HEADERS, ["2031", "1학기", "", "가상 연동", "전선", "3", "", ""]])
    )
    assert len(parsed.courses) == 1
    assert parsed.courses[0].course_code is None
    result = match_courses(parsed.courses, snapshot(master(name="가상연동")))
    assert result.matched[0].matched_course.course_id == "fake-a"
    assert result.matched[0].original.model_dump() == parsed.courses[0].model_dump()
    assert result.matched[0].original.grade is None
