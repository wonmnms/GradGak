import type {
  CommonRequirement,
  EvaluationResult,
  MockScenario,
  Program,
  ProgramResult,
  ResultStatus,
  SubMajor,
} from './result.types';

const PENDING_REASON = '영역 인정 과목 목록이 아직 없어 판정을 보류했습니다. (가상)';

// 지금 서버(2024 규칙 데이터 미완성)와 같은 모양: 총학점은 판정하고 영역별 학점은 보류합니다.
function makePendingProgram(program: Program): ProgramResult {
  return {
    program,
    status: 'pending',
    total: { required: 130, earned: 130, remaining: 0, status: 'met' },
    categories: [
      {
        id: 'major_required',
        label: '전공필수',
        required: null,
        earned: null,
        remaining: null,
        status: 'pending',
        reason: PENDING_REASON,
      },
      {
        id: 'other_credits',
        label: '기타 학점(가상)',
        required: null,
        earned: null,
        remaining: null,
        status: 'pending',
        reason: PENDING_REASON,
      },
    ],
    course_groups: [],
    missing_required_courses: [],
  };
}

/** 명세의 결합 규칙: 하나라도 unmet이면 unmet, 아니고 하나라도 pending이면 pending */
export function combineStatus(statuses: ResultStatus[]): ResultStatus {
  if (statuses.includes('unmet')) return 'unmet';
  if (statuses.includes('pending')) return 'pending';
  return 'met';
}

// 숫자·과목은 화면 개발용 가상 데이터입니다. 실제 규칙 계산은 서버가 담당합니다.
function makeProgram(program: Program, scenario: MockScenario): ProgramResult {
  if (scenario === 'pending') return makePendingProgram(program);
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
    graduation_status: combineStatus([
      ...commonRequirements.map((item) => item.status),
      ...programResults.map((item) => item.status),
    ]),
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
    excluded_courses:
      scenario === 'review'
        ? [
            {
              index: 3,
              name: '가상 재수강 전 과목',
              reason: "성적 'F'은(는) 학점·이수로 인정하지 않았습니다.",
            },
          ]
        : [],
    pending_data:
      scenario === 'pending' ? ['program_credit_mappings_and_category_course_lists'] : [],
    warnings:
      scenario === 'pending'
        ? ['규칙 데이터가 미완성이라 최종 충족으로 판정할 수 없습니다.']
        : scenario === 'review'
          ? ['(일반프로그램 기준) 가상 과목의 PDF 학점과 과목 데이터 학점이 다릅니다.']
          : [],
  };
}
