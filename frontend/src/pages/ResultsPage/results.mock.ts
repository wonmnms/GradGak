import type { MockScenario, Program, ProgramResult, ResultStatus } from './result.types';

// 전부 가상 수치입니다. 학교의 실제 졸업 규칙이나 사용자 입력으로 계산하지 않습니다.
function makeProgram(program: Program, scenario: ResultStatus): ProgramResult {
  const completed = scenario === 'met';
  const needsReview = scenario === 'review';
  const title = program === 'engineering' ? '공학 프로그램' : '일반 프로그램';
  return {
    program,
    title,
    status: scenario,
    total: {
      id: 'total',
      label: '총학점',
      required: 130,
      earned: completed ? 130 : 104,
      remaining: completed ? 0 : 26,
      status: completed ? 'met' : needsReview ? 'review' : 'unmet',
    },
    categories: [
      {
        id: 'major',
        label: '전공',
        required: 60,
        earned: completed ? 60 : 48,
        remaining: completed ? 0 : 12,
        status: completed ? 'met' : needsReview ? 'review' : 'unmet',
      },
      {
        id: 'general',
        label: '교양',
        required: 40,
        earned: completed ? 40 : 36,
        remaining: completed ? 0 : 4,
        status: completed ? 'met' : 'unmet',
      },
      {
        id: 'other',
        label: '기타',
        required: 30,
        earned: completed ? 30 : 20,
        remaining: completed ? 0 : 10,
        status: completed ? 'met' : 'unmet',
      },
    ],
    specialRequirements: [
      {
        id: 'sub-major',
        label: '세부전공필수',
        status: completed ? 'met' : 'unmet',
        detail: completed ? '5 / 5과목' : '3 / 5과목',
      },
      {
        id: 'thesis',
        label: '졸업논문·작품',
        status: completed ? 'met' : needsReview ? 'review' : 'unmet',
      },
      { id: 'topcit', label: 'TOPCIT 응시', status: 'met' },
      ...(program === 'engineering'
        ? [
            {
              id: 'engineering-extra',
              label: '공학 추가요건 A',
              status: completed ? ('met' as const) : ('unmet' as const),
            },
          ]
        : []),
    ],
    missingCourses: completed
      ? []
      : [
          { id: 'required-a', name: '필수과목 A', credit: 3, category: '전공필수 · 가상 과목' },
          ...(program === 'engineering'
            ? [
                {
                  id: 'required-b',
                  name: '필수과목 B',
                  credit: 3,
                  category: '공학필수 · 가상 과목',
                },
              ]
            : []),
        ],
  };
}
export function getMockResults(scenario: MockScenario): ProgramResult[] {
  if (scenario === 'program-difference') {
    return [makeProgram('engineering', 'unmet'), makeProgram('general', 'met')];
  }
  if (scenario === 'thesis-unmet') {
    return [makeProgram('engineering', 'met'), makeProgram('general', 'met')].map((result) => ({
      ...result,
      status: 'unmet',
      specialRequirements: result.specialRequirements.map((item) =>
        item.id === 'thesis' ? { ...item, status: 'unmet' } : item,
      ),
    }));
  }
  return [makeProgram('engineering', scenario), makeProgram('general', scenario)];
}
