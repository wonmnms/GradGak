export type ApiMode = 'mock' | 'http';

export interface ApiConfig {
  mode: ApiMode;
  baseUrl: string;
}

export const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export interface ApiEnv {
  VITE_API_MODE?: string;
  VITE_API_BASE_URL?: string;
}

/**
 * 환경변수로 mock/실제 API를 고른다.
 * - VITE_API_MODE=http 이면 실제 서버, 그 밖(비어 있음 포함)은 mock
 * - 알 수 없는 값은 실제 서버로 추정하지 않고 mock을 쓴다
 */
export function resolveApiConfig(env: ApiEnv): ApiConfig {
  const mode = env.VITE_API_MODE?.trim().toLowerCase() === 'http' ? 'http' : 'mock';
  const baseUrl = env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL;
  return { mode, baseUrl };
}
