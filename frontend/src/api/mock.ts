import type {
  Course,
  CourseNotice,
  EvaluateRequest,
  EvaluationResult,
  Program,
  ProgramResult,
  TranscriptParseResponse,
} from '../types/api';
import type { ApiClient, RequestOptions } from './client.ts';
import { ApiError } from './errors.ts';

// 모든 과목·학점·요건은 화면 개발용 가상 데이터입니다. 실제 졸업기준이나 실제 이수내역이 아닙니다.

export const MOCK_COURSES: Course[] = [
  {
    year: 2024,
    term: '1',
    course_code: null,
    name: '가상과목 A',
    category: '전필',
    credits: 3,
    grade: 'A0',
    is_retake: false,
  },
  {
    year: 2024,
    term: '1',
    course_code: null,
    name: '가상과목 B',
    category: '교필',
    credits: 2,
    grade: 'B+',
    is_retake: false,
  },
  {
    year: 2024,
    term: '2',
    course_code: null,
    name: '가상과목 C',
    category: '전선',
    credits: 3,
    grade: 'F',
    is_retake: false,
  },
  {
    year: 2025,
    term: '1',
    course_code: null,
    name: '가상과목 C',
    category: '전선',
    credits: 3,
    grade: 'B0',
    is_retake: true,
  },
  {
    year: 2025,
    term: '2',
    course_code: null,
    name: '가상과목 D',
    category: '전선',
    credits: 3,
    grade: null,
    is_retake: false,
  },
];

/** 인정 성적인지(가상 규칙). F·NP·빈 성적·(삭제)는 제외 */
function isPassing(grade: string | null): boolean {
  if (!grade) return false;
  if (grade.includes('(삭제)')) return false;
  return !['F', 'NP'].includes(grade.trim().toUpperCase());
}

function excludedReason(course: Course): string | null {
  if (course.grade === null) return '성적이 비어 있어 학점·이수로 인정하지 않았습니다.';
  if (!isPassing(course.grade))
    return `성적 '${course.grade}'은(는) 학점·이수로 인정하지 않았습니다.`;
  return null;
}

const MOCK_TOTAL_REQUIRED = 130;

function makeProgram(program: Program, earned: number): ProgramResult {
  return {
    program,
    // 지금 서버도 규칙 데이터가 미완성이라 pending을 낸다. mock도 같은 모양을 따른다.
    status: 'pending',
    total: {
      required: MOCK_TOTAL_REQUIRED,
      earned,
      remaining: Math.max(0, MOCK_TOTAL_REQUIRED - earned),
      status: earned >= MOCK_TOTAL_REQUIRED ? 'met' : 'unmet',
    },
    categories: [
      {
        id: 'major_required',
        label: '전공필수(가상)',
        required: null,
        earned: null,
        remaining: null,
        status: 'pending',
        reason: '영역 인정 과목 목록이 아직 없어 판정을 보류했습니다. (가상)',
      },
    ],
    course_groups: [],
    missing_required_courses: [
      { course_code: null, name: '가상 필수과목', credits: 3, category: null },
    ],
  };
}

/** 요청 과목으로 /evaluate 응답 형태의 가상 결과를 만든다(규칙 계산이 아님). */
export function buildMockEvaluation(request: EvaluateRequest): EvaluationResult {
  const excluded: CourseNotice[] = [];
  const unmatched: CourseNotice[] = [];
  let earned = 0;

  request.courses.forEach((course, index) => {
    const reason = excludedReason(course);
    if (reason) {
      excluded.push({ index, name: course.name, reason });
      return;
    }
    earned += course.credits;
    // 실제 서버도 현재 시드에 학수번호가 없어 대부분 매칭 실패로 나온다.
    if (course.course_code === null) {
      unmatched.push({ index, name: course.name, reason: '과목 데이터에서 찾지 못했습니다.' });
    }
  });

  const programs: Program[] =
    request.program === 'engineering' ? ['engineering', 'general'] : ['general'];

  const common: EvaluationResult['common_requirements'] = [];
  if (request.sub_major === 'ai') {
    common.push({
      id: 'sub_major_required',
      label: '세부전공필수',
      status: 'unmet',
      required_count: 3,
      completed_count: 0,
      courses: [
        { course_code: null, name: '가상 세부전공필수 1', completed: false },
        { course_code: null, name: '가상 세부전공필수 2', completed: false },
      ],
    });
  }
  common.push(
    {
      id: 'thesis',
      label: "졸업논문(작품) '가' 판정",
      status: request.thesis_passed ? 'met' : 'unmet',
    },
    { id: 'topcit', label: 'TOPCIT 응시', status: request.topcit_taken ? 'met' : 'unmet' },
  );

  const programResults = programs.map((program) => makeProgram(program, earned));
  const statuses = [...common.map((item) => item.status), ...programResults.map((p) => p.status)];
  const graduationStatus = statuses.includes('unmet')
    ? 'unmet'
    : statuses.includes('pending')
      ? 'pending'
      : 'met';

  return {
    graduation_status: graduationStatus,
    common_requirements: common,
    program_results: programResults,
    unmatched_courses: unmatched,
    excluded_courses: excluded,
    pending_data: ['program_credit_mappings_and_category_course_lists'],
    warnings: ['규칙 데이터가 미완성이라 최종 충족으로 판정할 수 없습니다. (가상 응답)'],
  };
}

export interface MockClientOptions {
  /** 로딩 상태 확인용 지연(ms) */
  delayMs?: number;
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new ApiError({ kind: 'aborted' }));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new ApiError({ kind: 'aborted' }));
    }
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

const PDF_SIGNATURE = '%PDF-';

async function looksLikePdf(file: Blob): Promise<boolean> {
  const head = await file.slice(0, PDF_SIGNATURE.length).text();
  return head === PDF_SIGNATURE;
}

export function createMockClient(options: MockClientOptions = {}): ApiClient {
  const delayMs = options.delayMs ?? 0;
  return {
    async parseTranscript(file: Blob, requestOptions?: RequestOptions) {
      await wait(delayMs, requestOptions?.signal);
      if (!(await looksLikePdf(file))) {
        throw new ApiError({
          kind: 'http',
          status: 400,
          code: 'NOT_PDF',
          message: 'PDF 파일이 아니거나 열 수 없는 파일입니다. (가상 응답)',
        });
      }
      const response: TranscriptParseResponse = {
        admission_year: 2024,
        courses: MOCK_COURSES.map((course) => ({ ...course })),
        parse_warnings: [],
      };
      return response;
    },
    async evaluate(request: EvaluateRequest, requestOptions?: RequestOptions) {
      await wait(delayMs, requestOptions?.signal);
      if (request.admission_year !== 2024) {
        throw new ApiError({
          kind: 'http',
          status: 400,
          code: 'UNSUPPORTED_ADMISSION_YEAR',
          message: `${request.admission_year}학번 졸업요건은 아직 지원하지 않습니다.`,
        });
      }
      return buildMockEvaluation(request);
    },
  };
}
