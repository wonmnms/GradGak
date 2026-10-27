import test from 'node:test';
import assert from 'node:assert/strict';
import { parseProgram } from '../src/context/program.ts';
import { getMockResults } from '../src/pages/ResultsPage/results.mock.ts';

test('빈 값과 알 수 없는 프로그램은 공학으로 추정하지 않는다', () => {
  for (const value of ['', '   ', 'unknown', '일반x']) assert.equal(parseProgram(value), null);
});
test('공학과 일반의 기존 문자열 표기를 호환한다', () => {
  for (const value of ['일반', '일반 프로그램', ' GENERAL '])
    assert.equal(parseProgram(value), 'general');
  for (const value of ['공학', '공학 프로그램', ' Engineering '])
    assert.equal(parseProgram(value), 'engineering');
});
test('기본 세 시나리오의 프로그램 상태를 유지한다', () => {
  for (const scenario of ['met', 'unmet', 'review']) {
    assert.deepEqual(
      getMockResults(scenario).map((item) => item.status),
      [scenario, scenario],
    );
  }
});
test('프로그램 비교 예시는 공학 미충족, 일반 충족이다', () => {
  assert.deepEqual(
    getMockResults('program-difference').map(({ program, status }) => [program, status]),
    [
      ['engineering', 'unmet'],
      ['general', 'met'],
    ],
  );
});
test('논문 미충족 예시는 학점 100%여도 전체 미충족이다', () => {
  for (const result of getMockResults('thesis-unmet')) {
    assert.equal(result.status, 'unmet');
    assert.equal(result.total.status, 'met');
    assert.equal(result.total.earned, result.total.required);
    assert.equal(result.total.remaining, 0);
    assert.equal(
      result.categories.every((item) => item.status === 'met' && item.remaining === 0),
      true,
    );
    assert.deepEqual(
      result.specialRequirements.filter((item) => item.status !== 'met').map((item) => item.id),
      ['thesis'],
    );
    assert.deepEqual(result.missingCourses, []);
  }
});
test('모든 가상 학점의 합계와 부족 학점이 일치한다', () => {
  for (const scenario of ['met', 'unmet', 'review', 'program-difference', 'thesis-unmet']) {
    for (const result of getMockResults(scenario)) {
      for (const key of ['required', 'earned', 'remaining']) {
        assert.equal(
          result.categories.reduce((sum, item) => sum + item[key], 0),
          result.total[key],
        );
      }
      for (const item of [result.total, ...result.categories]) {
        assert.equal(item.remaining, Math.max(0, item.required - item.earned));
      }
    }
  }
});
test('각 호출의 가상 결과는 서로 독립적이다', () => {
  const first = getMockResults('met');
  first[0].specialRequirements[0].status = 'unmet';
  assert.equal(getMockResults('met')[0].specialRequirements[0].status, 'met');
});
