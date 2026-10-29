import type {
  CommonRequirement,
  EvaluationResult,
  MockScenario,
  Program,
  ProgramResult,
  SubMajor,
} from './result.types';

// 숫자·과목은 화면 개발용 가상 데이터입니다. 실제 규칙 계산은 서버가 담당합니다.
function makeProgram(program: Program, scenario: MockScenario): ProgramResult {
  const allCreditsMet =
    ['met', 'review', 'thesis-unmet'].includes(scenario) ||
    (scenario === 'program-difference' && program === 'general');
  const onlyMajorMissing = scenario === 'program-difference' && program === 'engineering';
  const majorEarned = allCreditsMet ? 18 : 12;
  const otherEarned = allCreditsMet || onlyMajorMissing ? 112 : 92;
  const earned = majorEarned + otherEarned;
  return {
    program,
    status: allCreditsMet ? 'met' : 'unmet',
    total: {
      required: 130,
      earned,
      remaining: 130 - earned,
      status: allCreditsMet ? 'met' : 'unmet',
    },
    categories: [
      {
        id: 'major_required',
        label: '전공필수',
        required: 18,
        earned: majorEarned,
        remaining: 18 - majorEarned,
        status: allCreditsMet ? 'met' : 'unmet',
      },
      {
        id: 'other_credits',
        label: '기타 학점(가상)',
        required: 112,
        earned: otherEarned,
        remaining: 112 - otherEarned,
        status: otherEarned === 112 ? 'met' : 'unmet',
      },
    ],
    // 캡스톤 요건의 소속은 명세의 열린 질문입니다. 임의로 추가하지 않습니다.
    course_groups: [],
    missing_required_courses:
      scenario === 'unmet'
        ? [
            {
              course_code: 'MOCK-REQUIRED-A',
              name: '가상 필수과목 A',
              credits: 3,
              category: '전공필수',
            },
          ]
        : [],
  };
}
export function getMockResults(
  scenario: MockScenario,
  program: Program,
  subMajor: SubMajor,
): EvaluationResult {
  const commonRequirements: CommonRequirement[] = [];
  if (subMajor === 'ai') {
    const completedCount = scenario === 'unmet' ? 1 : 3;
    commonRequirements.push({
      id: 'sub_major_required',
      label: '세부전공필수',
      status: completedCount >= 3 ? 'met' : 'unmet',
      required_count: 3,
      completed_count: completedCount,
      courses: ['A', 'B', 'C', 'D', 'E'].map((name, index) => ({
        course_code: 'MOCK-AI-' + name,
        name: '가상 선택과목 ' + name,
        completed: index < completedCount,
      })),
    });
  }
  commonRequirements.push(
    {
      id: 'thesis',
      label: "졸업논문(작품) '가' 판정",
      status: scenario === 'unmet' || scenario === 'thesis-unmet' ? 'unmet' : 'met',
    },
    { id: 'topcit', label: 'TOPCIT 응시', status: 'met' },
  );
  const programs: Program[] = program === 'engineering' ? ['engineering', 'general'] : ['general'];
  const programResults = programs.map((value) => makeProgram(value, scenario));
  return {
    // 가상 응답의 일관성만 유지하는 fixture 구성입니다. 실제 학사 판정 함수가 아닙니다.
    graduation_status:
      commonRequirements.every((item) => item.status === 'met') &&
      programResults.every((item) => item.status === 'met')
        ? 'met'
        : 'unmet',
    common_requirements: commonRequirements,
    program_results: programResults,
    unmatched_courses:
      scenario === 'review'
        ? [
            {
              index: 7,
              name: '매칭되지 않은 가상 과목',
              reason: '과목 데이터에서 찾지 못했습니다.',
            },
          ]
        : [],
  };
}
