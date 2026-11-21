import type { ValidationErrorItem } from '../types/api';

/**
 * API 호출 실패를 한 형식으로 다룬다.
 * - http: 서버가 에러 응답을 보냄. code는 서버 code, 422는 VALIDATION_ERROR
 * - network: 서버에 닿지 못함(서버 꺼짐, CORS, 오프라인)
 * - aborted: AbortController로 요청을 취소함
 * - invalid_response: 응답 본문을 JSON으로 읽지 못함
 */
export type ApiErrorKind = 'http' | 'network' | 'aborted' | 'invalid_response';

export const VALIDATION_ERROR = 'VALIDATION_ERROR';
export const UNKNOWN_ERROR = 'UNKNOWN_ERROR';

const FALLBACK_MESSAGES: Record<ApiErrorKind, string> = {
  http: '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.',
  network: '서버에 연결할 수 없습니다. 네트워크 상태를 확인하고 다시 시도해 주세요.',
  aborted: '요청이 취소되었습니다.',
  invalid_response: '서버 응답을 읽을 수 없습니다. 잠시 후 다시 시도해 주세요.',
};

export interface ApiErrorInit {
  kind: ApiErrorKind;
  status?: number | null;
  code?: string;
  message?: string;
  validation?: ValidationErrorItem[];
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  /** HTTP 상태 코드. network·aborted면 null */
  readonly status: number | null;
  /** 서버 code(예: NO_TEXT_LAYER), 422는 VALIDATION_ERROR, 그 밖은 kind 기반 값 */
  readonly code: string;
  /** 422일 때 FastAPI 검증 오류 목록 */
  readonly validation: ValidationErrorItem[];

  constructor(init: ApiErrorInit) {
    super(init.message ?? FALLBACK_MESSAGES[init.kind]);
    this.name = 'ApiError';
    this.kind = init.kind;
    this.status = init.status ?? null;
    this.code = init.code ?? (init.kind === 'http' ? UNKNOWN_ERROR : init.kind.toUpperCase());
    this.validation = init.validation ?? [];
  }

  /** 다시 시도하면 나아질 수 있는 오류인지. 화면의 재시도 버튼 노출 기준 */
  get retryable(): boolean {
    if (this.kind === 'network' || this.kind === 'invalid_response') return true;
    return this.kind === 'http' && this.status !== null && this.status >= 500;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toValidationItems(detail: unknown[]): ValidationErrorItem[] {
  return detail.filter(isRecord).map((item) => ({
    loc: Array.isArray(item.loc) ? (item.loc as (string | number)[]) : [],
    msg: typeof item.msg === 'string' ? item.msg : '',
    type: typeof item.type === 'string' ? item.type : '',
  }));
}

/** 에러 응답 본문(JSON 파싱 결과 또는 null)을 ApiError로 바꾼다. */
export function toApiError(status: number, body: unknown): ApiError {
  const detail = isRecord(body) ? body.detail : undefined;

  if (isRecord(detail) && typeof detail.code === 'string') {
    return new ApiError({
      kind: 'http',
      status,
      code: detail.code,
      message: typeof detail.message === 'string' && detail.message ? detail.message : undefined,
    });
  }

  if (Array.isArray(detail)) {
    const validation = toValidationItems(detail);
    const first = validation.find((item) => item.msg)?.msg;
    return new ApiError({
      kind: 'http',
      status,
      code: VALIDATION_ERROR,
      message: first ? `입력 형식을 확인해 주세요: ${first}` : '입력 형식을 확인해 주세요.',
      validation,
    });
  }

  return new ApiError({ kind: 'http', status });
}
