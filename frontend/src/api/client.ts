import type { EvaluateRequest, EvaluationResult, TranscriptParseResponse } from '../types/api';
import { ApiError, toApiError } from './errors.ts';

export interface RequestOptions {
  /** 화면 이동·재시도 시 이전 요청을 취소할 때 사용 */
  signal?: AbortSignal;
}

/** 화면은 이 인터페이스만 사용한다. 실제 서버(http)와 mock이 같은 형태를 구현한다. */
export interface ApiClient {
  parseTranscript(file: Blob, options?: RequestOptions): Promise<TranscriptParseResponse>;
  evaluate(request: EvaluateRequest, options?: RequestOptions): Promise<EvaluationResult>;
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

function isAbort(error: unknown, signal?: AbortSignal): boolean {
  return signal?.aborted === true || (error instanceof Error && error.name === 'AbortError');
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export function createHttpClient(baseUrl: string, fetchImpl: FetchLike = fetch): ApiClient {
  const root = baseUrl.replace(/\/+$/, '');

  async function request<T>(path: string, init: RequestInit, signal?: AbortSignal): Promise<T> {
    let response: Response;
    try {
      response = await fetchImpl(`${root}${path}`, { ...init, signal });
    } catch (error) {
      throw new ApiError({ kind: isAbort(error, signal) ? 'aborted' : 'network' });
    }

    let body: unknown;
    try {
      body = await readJson(response);
    } catch (error) {
      if (isAbort(error, signal)) throw new ApiError({ kind: 'aborted' });
      throw new ApiError({ kind: 'network', status: response.status });
    }

    if (!response.ok) throw toApiError(response.status, body ?? null);
    if (body === undefined || body === null) {
      throw new ApiError({ kind: 'invalid_response', status: response.status });
    }
    return body as T;
  }

  return {
    parseTranscript(file, options) {
      const form = new FormData();
      // 서버는 file 필드 1개와 filename을 요구한다.
      const name = file instanceof File && file.name ? file.name : 'transcript.pdf';
      form.append('file', file, name);
      // Content-Type은 브라우저가 boundary와 함께 정하므로 직접 넣지 않는다.
      return request<TranscriptParseResponse>(
        '/transcripts/parse',
        { method: 'POST', body: form },
        options?.signal,
      );
    },
    evaluate(payload, options) {
      return request<EvaluationResult>(
        '/evaluate',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
        options?.signal,
      );
    },
  };
}
