import { createHttpClient } from './client.ts';
import type { ApiClient } from './client.ts';
import { resolveApiConfig } from './config.ts';
import { createMockClient } from './mock.ts';

export type { ApiClient, RequestOptions } from './client.ts';
export { ApiError, VALIDATION_ERROR } from './errors.ts';
export type { ApiErrorKind } from './errors.ts';

export const apiConfig = resolveApiConfig({
  VITE_API_MODE: import.meta.env.VITE_API_MODE,
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
});

/** 화면에서 쓰는 API 클라이언트. .env의 VITE_API_MODE로 mock/실제 서버를 고른다. */
export const api: ApiClient =
  apiConfig.mode === 'http'
    ? createHttpClient(apiConfig.baseUrl)
    : createMockClient({ delayMs: 400 });
