import test from 'node:test';
import assert from 'node:assert/strict';
import { parseProgram } from '../src/context/program.ts';
import { getMockResults } from '../src/pages/ResultsPage/results.mock.ts';
import {
  creditProgress,
  getResultSummary,
  hasCourseCount,
  parseSubMajor,
} from '../src/pages/ResultsPage/results.presentation.ts';
const scenarios = ['unmet', 'met', 'review', 'program-difference', 'thesis-unmet'];

test('빈 값과 알 수 없는 프로그램은 공학으로 추정하지 않는다', () => {
  for (const value of ['', '   ', 'unknown', '일반x']) assert.equal(parseProgram(value), null);
});
test('프로그램의 기존 문자열과 API 값을 호환한다', () => {
  for (const value of ['일반', '일반 프로그램', ' GENERAL '])
    assert.equal(parseProgram(value), 'general');
  for (const value of ['공학', '공학 프로그램', ' Engineering '])
    assert.equal(parseProgram(value), 'engineering');
});
test('세부전공을 인식하되 빈 값과 알 수 없는 값은 추정하지 않는다', () => {
  for (const value of ['AI', '인공지능전공', ' ai ']) assert.equal(parseSubMajor(value), 'ai');
  for (const value of ['SW', '소프트웨어전공', 'software'])
    assert.equal(parseSubMajor(value), 'software');
  for (const value of ['', ' ', 'unknown']) assert.equal(parseSubMajor(value), null);
});
test('mock 최상위 필드는 API 응답 계약과 같다', () => {
  assert.deepEqual(Object.keys(getMockResults('met', 'engineering', 'ai')).sort(), [
    'common_requirements',
    'graduation_status',
    'program_results',
    'unmatched_courses',
  ]);
});
test('공학은 공학·일반 순서, 일반은 일반만 반환한다', () => {
  for (const scenario of scenarios) {
    assert.deepEqual(
      getMockResults(scenario, 'engineering', 'ai').program_results.map((r) => r.program),
      ['engineering', 'general'],
    );
    assert.deepEqual(
      getMockResults(scenario, 'general', 'ai').program_results.map((r) => r.program),
      ['general'],
    );
  }
});
test('AI는 지정 5과목 중 3과목이면 충족이며 나머지는 개별 필수과목이 아니다', () => {
  const result = getMockResults('met', 'engineering', 'ai');
  const item = result.common_requirements.find((r) => r.id === 'sub_major_required');
  assert.equal(hasCourseCount(item), true);
  assert.equal(item.required_count, 3);
  assert.equal(item.completed_count, 3);
  assert.equal(item.courses.length, 5);
  assert.equal(item.courses.filter((course) => course.completed).length, 3);
  assert.equal(item.status, 'met');
  assert.equal(
    result.program_results.every((r) => r.missing_required_courses.length === 0),
    true,
  );
});
test('AI 미충족 예시의 이수 개수와 과목 목록이 일치한다', () => {
  const item = getMockResults('unmet', 'general', 'ai').common_requirements.find(
    (r) => r.id === 'sub_major_required',
  );
  assert.equal(item.completed_count, 1);
  assert.equal(item.courses.filter((course) => course.completed).length, item.completed_count);
  assert.equal(item.status, 'unmet');
});
test('SW 응답에는 세부전공필수 항목 자체가 없다', () => {
  for (const scenario of scenarios)
    assert.deepEqual(
      getMockResults(scenario, 'engineering', 'software').common_requirements.map((r) => r.id),
      ['thesis', 'topcit'],
    );
});
test('공통 요건은 한 번만 존재하며 가공한 공학 추가요건은 없다', () => {
  const result = getMockResults('met', 'engineering', 'ai');
  assert.deepEqual(
    result.common_requirements.map((r) => r.id),
    ['sub_major_required', 'thesis', 'topcit'],
  );
  for (const program of result.program_results) {
    assert.equal('specialRequirements' in program, false);
    assert.deepEqual(program.course_groups, []);
  }
});
test('프로그램 비교 예시는 학점만 다르며 일반 선택 시 최종 판정도 충족이다', () => {
  const result = getMockResults('program-difference', 'engineering', 'ai');
  assert.deepEqual(
    result.program_results.map((r) => r.status),
    ['unmet', 'met'],
  );
  assert.deepEqual(
    result.program_results.map((r) => r.categories[0].earned),
    [12, 18],
  );
  assert.equal(
    result.common_requirements.every((r) => r.status === 'met'),
    true,
  );
  assert.equal(result.graduation_status, 'unmet');
  assert.equal(getMockResults('program-difference', 'general', 'ai').graduation_status, 'met');
});
test('논문 미충족은 프로그램 학점이 충족이어도 최종 미충족이다', () => {
  const result = getMockResults('thesis-unmet', 'engineering', 'ai');
  assert.equal(result.graduation_status, 'unmet');
  assert.equal(
    result.program_results.every((r) => r.status === 'met' && r.total.remaining === 0),
    true,
  );
  assert.deepEqual(
    result.common_requirements.filter((r) => r.status !== 'met').map((r) => r.id),
    ['thesis'],
  );
});
test('미매칭 과목은 API 상태에 review를 추가하지 않고 별도 안내한다', () => {
  const result = getMockResults('review', 'engineering', 'ai');
  assert.equal(result.graduation_status, 'met');
  assert.equal(result.unmatched_courses[0].index, 7);
  assert.deepEqual(getResultSummary(result), {
    status: 'review',
    label: '확인 필요',
    needsReview: true,
  });
});
test('화면은 서버의 최종 판정을 재계산해 덮어쓰지 않는다', () => {
  const result = getMockResults('met', 'engineering', 'ai');
  result.graduation_status = 'unmet';
  assert.deepEqual(getResultSummary(result), {
    status: 'unmet',
    label: '졸업요건 미충족',
    needsReview: false,
  });
});
test('모든 fixture 조합의 판정·학점·선택 개수가 일관된다', () => {
  for (const scenario of scenarios)
    for (const program of ['engineering', 'general'])
      for (const subMajor of ['ai', 'software']) {
        const result = getMockResults(scenario, program, subMajor);
        assert.equal(
          result.graduation_status,
          [...result.common_requirements, ...result.program_results].every(
            (r) => r.status === 'met',
          )
            ? 'met'
            : 'unmet',
        );
        const statuses = [
          result.graduation_status,
          ...result.common_requirements.map((r) => r.status),
        ];
        for (const r of result.program_results) {
          statuses.push(r.status, r.total.status, ...r.categories.map((c) => c.status));
          for (const key of ['required', 'earned', 'remaining'])
            assert.equal(
              r.categories.reduce((sum, c) => sum + c[key], 0),
              r.total[key],
            );
          for (const credit of [r.total, ...r.categories])
            assert.equal(credit.remaining, Math.max(0, credit.required - credit.earned));
        }
        assert.equal(
          statuses.every((status) => status === 'met' || status === 'unmet'),
          true,
        );
        for (const item of result.common_requirements.filter(hasCourseCount))
          assert.equal(
            item.completed_count,
            item.courses.filter((course) => course.completed).length,
          );
      }
});
test('학점 비율은 0~100으로 제한하고 0분모·비정상 값에 안전하다', () => {
  for (const [required, earned, expected] of [
    [130, 130, 100],
    [130, 140, 100],
    [130, -1, 0],
    [0, 0, 0],
    [130, 65, 50],
    [130, NaN, 0],
  ])
    assert.equal(creditProgress({ required, earned, remaining: 0, status: 'met' }), expected);
});
test('Boolean 요건에는 선택 과목 개수 표시를 만들지 않는다', () => {
  assert.equal(hasCourseCount({ id: 'thesis', label: '논문', status: 'met' }), false);
});
test('각 호출은 독립적인 응답·과목 배열을 반환한다', () => {
  const first = getMockResults('met', 'engineering', 'ai');
  first.common_requirements[0].courses[0].completed = false;
  first.program_results[0].categories[0].earned = 0;
  const next = getMockResults('met', 'engineering', 'ai');
  assert.equal(next.common_requirements[0].courses[0].completed, true);
  assert.equal(next.program_results[0].categories[0].earned, 18);
});
