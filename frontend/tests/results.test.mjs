import test from 'node:test';
import assert from 'node:assert/strict';
import { parseProgram } from '../src/context/program.ts';
import { combineStatus, getMockResults } from '../src/pages/ResultsPage/results.mock.ts';
import {
  creditProgress,
  formatCredit,
  getResultSummary,
  hasCourseCount,
  isMissingListUnsettled,
  parseSubMajor,
  progressLabel,
  remainingLabel,
} from '../src/pages/ResultsPage/results.presentation.ts';
const scenarios = [
  'pending',
  'pending-unmet',
  'unmet',
  'met',
  'review',
  'program-difference',
  'thesis-unmet',
];

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
    'excluded_courses',
    'graduation_status',
    'pending_data',
    'program_results',
    'unmatched_courses',
    'warnings',
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
          combineStatus(
            [...result.common_requirements, ...result.program_results].map((r) => r.status),
          ),
        );
        const statuses = [
          result.graduation_status,
          ...result.common_requirements.map((r) => r.status),
        ];
        for (const r of result.program_results) {
          statuses.push(r.status, r.total.status, ...r.categories.map((c) => c.status));
          const decided = r.categories.every((c) => c.earned !== null && c.remaining !== null);
          if (decided)
            for (const key of ['required', 'earned', 'remaining'])
              assert.equal(
                r.categories.reduce((sum, c) => sum + c[key], 0),
                r.total[key],
              );
          for (const credit of [r.total, ...r.categories])
            if (credit.earned === null || credit.remaining === null)
              assert.equal(credit.status, 'pending');
            else assert.equal(credit.remaining, Math.max(0, credit.required - credit.earned));
        }
        assert.equal(
          statuses.every((status) => ['met', 'unmet', 'pending'].includes(status)),
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
test('판정 보류 예시는 지금 서버처럼 최종 pending과 보류 사유를 낸다', () => {
  const result = getMockResults('pending', 'engineering', 'ai');
  assert.equal(result.graduation_status, 'pending');
  assert.deepEqual(getResultSummary(result), {
    status: 'pending',
    label: '졸업요건 판정 보류',
    needsReview: false,
  });
  for (const program of result.program_results) {
    assert.equal(program.status, 'pending');
    for (const category of program.categories) {
      assert.equal(category.status, 'pending');
      // 서버처럼 required는 숫자, earned·remaining만 null
      assert.equal(typeof category.required, 'number');
      assert.equal(category.earned, null);
      assert.equal(category.remaining, null);
      assert.ok(category.reason);
    }
  }
  assert.ok(result.warnings.length > 0);
  assert.ok(result.pending_data.length > 0);
});
test('최종 판정은 unmet > pending > met 순서로 합친다', () => {
  assert.equal(combineStatus(['met', 'pending', 'unmet']), 'unmet');
  assert.equal(combineStatus(['met', 'pending']), 'pending');
  assert.equal(combineStatus(['met', 'met']), 'met');
});
test('판정할 수 없는 숫자는 —와 보류 문구로 표시한다', () => {
  assert.equal(formatCredit(null), '—');
  assert.equal(formatCredit(0), '0');
  assert.equal(formatCredit(12.5), '12.5');
  assert.equal(
    remainingLabel({ required: null, earned: null, remaining: null, status: 'pending' }),
    '부족 학점 판정 보류',
  );
  assert.equal(
    remainingLabel({ required: 130, earned: 98, remaining: 32, status: 'unmet' }),
    '32학점 부족',
  );
  assert.equal(
    creditProgress({ required: null, earned: 98, remaining: null, status: 'pending' }),
    0,
  );
});
test('제외 과목은 요청 index와 사유를 그대로 전달한다', () => {
  const result = getMockResults('review', 'general', 'software');
  assert.deepEqual(
    result.excluded_courses.map((c) => c.index),
    [3],
  );
  assert.match(result.excluded_courses[0].reason, /F/);
});
test('총학점이 부족하면 영역이 보류여도 프로그램은 unmet이고, 빈 미이수 목록을 확정하지 않는다', () => {
  const result = getMockResults('pending-unmet', 'engineering', 'ai');
  for (const program of result.program_results) {
    assert.equal(program.status, 'unmet');
    assert.equal(program.total.earned, 100);
    assert.equal(program.missing_required_courses.length, 0);
    assert.equal(isMissingListUnsettled(program, result), true);
  }
  assert.equal(result.graduation_status, 'unmet');
});
test('보류 영역도 pending_data도 없을 때만 미이수 목록을 확정으로 본다', () => {
  const met = getMockResults('met', 'general', 'software');
  assert.equal(isMissingListUnsettled(met.program_results[0], met), false);
  const withPendingData = { ...met, pending_data: ['something'] };
  assert.equal(isMissingListUnsettled(met.program_results[0], withPendingData), true);
  const withPendingStatus = { ...met, graduation_status: 'pending' };
  assert.equal(isMissingListUnsettled(met.program_results[0], withPendingStatus), true);
});
test('총학점 요구·이수가 null이면 이수율을 0%가 아니라 —로 표시한다', () => {
  assert.equal(
    progressLabel({ required: null, earned: 98, remaining: null, status: 'pending' }),
    '총학점 이수율 —',
  );
  assert.equal(
    progressLabel({ required: 130, earned: 65, remaining: 65, status: 'unmet' }),
    '총학점 기준 50% 이수',
  );
});
