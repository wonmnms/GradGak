/* global Response, File, FormData, Blob, AbortController, DOMException */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHttpClient } from '../src/api/client.ts';
import { resolveApiConfig, DEFAULT_API_BASE_URL } from '../src/api/config.ts';
import { ApiError, toApiError, VALIDATION_ERROR } from '../src/api/errors.ts';
import { buildMockEvaluation, createMockClient, MOCK_COURSES } from '../src/api/mock.ts';
import { isCourseGroupResult } from '../src/types/api.ts';

const BASE = 'http://api.test';
const evaluateRequest = (overrides = {}) => ({
  admission_year: 2024,
  program: 'engineering',
  sub_major: 'ai',
  thesis_passed: false,
  topcit_taken: true,
  courses: MOCK_COURSES,
  ...overrides,
});
const jsonResponse = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function recordingFetch(response) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return typeof response === 'function' ? response() : response;
  };
  return { calls, fetchImpl };
}

// ── 설정 ──────────────────────────────────────────────
test('VITE_API_MODE가 http일 때만 실제 서버를 쓴다', () => {
  assert.equal(resolveApiConfig({ VITE_API_MODE: 'http' }).mode, 'http');
  assert.equal(resolveApiConfig({ VITE_API_MODE: ' HTTP ' }).mode, 'http');
  for (const value of [undefined, '', 'mock', 'real', 'true'])
    assert.equal(resolveApiConfig({ VITE_API_MODE: value }).mode, 'mock');
});
test('base URL이 비어 있으면 로컬 기본값을 쓴다', () => {
  assert.equal(resolveApiConfig({}).baseUrl, DEFAULT_API_BASE_URL);
  assert.equal(resolveApiConfig({ VITE_API_BASE_URL: '  ' }).baseUrl, DEFAULT_API_BASE_URL);
  assert.equal(resolveApiConfig({ VITE_API_BASE_URL: 'https://x.dev' }).baseUrl, 'https://x.dev');
});

// ── 에러 변환 ────────────────────────────────────────
test('400/500 에러는 detail.code와 detail.message를 그대로 쓴다', () => {
  const error = toApiError(400, {
    detail: {
      code: 'UNSUPPORTED_SCOPE',
      message: '선택한 프로그램·세부전공의 졸업요건 데이터가 없습니다.',
    },
  });
  assert.equal(error.kind, 'http');
  assert.equal(error.status, 400);
  assert.equal(error.code, 'UNSUPPORTED_SCOPE');
  assert.equal(error.message, '선택한 프로그램·세부전공의 졸업요건 데이터가 없습니다.');
  assert.equal(error.retryable, false);
  assert.equal(
    toApiError(500, { detail: { code: 'INVALID_RULE_DATA', message: 'x' } }).retryable,
    true,
  );
});
test('422는 detail 배열을 VALIDATION_ERROR로 바꾼다', () => {
  const error = toApiError(422, {
    detail: [{ type: 'missing', loc: ['body', 'sub_major'], msg: 'Field required', input: null }],
  });
  assert.equal(error.code, VALIDATION_ERROR);
  assert.deepEqual(error.validation, [
    { type: 'missing', loc: ['body', 'sub_major'], msg: 'Field required' },
  ]);
  assert.match(error.message, /Field required/);
});
test('형식을 모르는 에러 본문은 UNKNOWN_ERROR와 기본 문구를 쓴다', () => {
  for (const body of [null, 'oops', { detail: 'Not Found' }, { error: 1 }]) {
    const error = toApiError(404, body);
    assert.equal(error.code, 'UNKNOWN_ERROR');
    assert.equal(error.status, 404);
    assert.ok(error.message.length > 0);
  }
});

// ── 실제 서버 클라이언트 ─────────────────────────────
test('evaluate는 JSON으로 POST /evaluate를 호출한다', async () => {
  const result = buildMockEvaluation(evaluateRequest());
  const { calls, fetchImpl } = recordingFetch(() => jsonResponse(200, result));
  const client = createHttpClient(`${BASE}/`, fetchImpl);
  const request = evaluateRequest();
  assert.deepEqual(await client.evaluate(request), result);
  assert.equal(calls[0].url, `${BASE}/evaluate`);
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(calls[0].init.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(calls[0].init.body), request);
});
test('parseTranscript는 file 필드 1개로 multipart 요청을 보낸다', async () => {
  const body = { admission_year: 2024, courses: [], parse_warnings: [] };
  const { calls, fetchImpl } = recordingFetch(() => jsonResponse(200, body));
  const client = createHttpClient(BASE, fetchImpl);
  const file = new File(['%PDF-1.7'], 'klas.pdf', { type: 'application/pdf' });
  assert.deepEqual(await client.parseTranscript(file), body);
  assert.equal(calls[0].url, `${BASE}/transcripts/parse`);
  const form = calls[0].init.body;
  assert.ok(form instanceof FormData);
  assert.deepEqual([...form.keys()], ['file']);
  assert.equal(form.get('file').name, 'klas.pdf');
  // boundary를 브라우저가 정하도록 Content-Type을 직접 넣지 않는다.
  assert.equal(calls[0].init.headers, undefined);
});
test('파일명이 없는 Blob도 filename을 붙여 보낸다', async () => {
  const { calls, fetchImpl } = recordingFetch(() =>
    jsonResponse(200, { admission_year: null, courses: [], parse_warnings: [] }),
  );
  await createHttpClient(BASE, fetchImpl).parseTranscript(new Blob(['%PDF-']));
  assert.equal(calls[0].init.body.get('file').name, 'transcript.pdf');
});
test('서버 에러 응답은 ApiError로 던진다', async () => {
  const { fetchImpl } = recordingFetch(() =>
    jsonResponse(400, {
      detail: { code: 'NO_TEXT_LAYER', message: 'PDF에서 텍스트를 읽을 수 없습니다.' },
    }),
  );
  await assert.rejects(
    createHttpClient(BASE, fetchImpl).parseTranscript(new Blob(['x'])),
    (error) => error instanceof ApiError && error.code === 'NO_TEXT_LAYER' && error.status === 400,
  );
});
test('서버에 닿지 못하면 network, 취소하면 aborted다', async () => {
  const down = createHttpClient(BASE, async () => {
    throw new TypeError('Failed to fetch');
  });
  await assert.rejects(
    down.evaluate(evaluateRequest()),
    (e) => e.kind === 'network' && e.retryable,
  );

  const controller = new AbortController();
  controller.abort();
  const aborting = createHttpClient(BASE, async () => {
    throw new DOMException('aborted', 'AbortError');
  });
  await assert.rejects(
    aborting.evaluate(evaluateRequest(), { signal: controller.signal }),
    (e) => e.kind === 'aborted' && !e.retryable,
  );
});
test('200인데 JSON이 아니면 invalid_response다', async () => {
  const client = createHttpClient(BASE, async () => new Response('<html>', { status: 200 }));
  await assert.rejects(client.evaluate(evaluateRequest()), (e) => e.kind === 'invalid_response');
});

// ── mock ────────────────────────────────────────────
test('mock 응답 최상위 필드는 /evaluate 명세와 같다', () => {
  assert.deepEqual(Object.keys(buildMockEvaluation(evaluateRequest())).sort(), [
    'common_requirements',
    'excluded_courses',
    'graduation_status',
    'pending_data',
    'program_results',
    'unmatched_courses',
    'warnings',
  ]);
});
test('mock은 공학이면 공학·일반, 일반이면 일반만 반환한다', () => {
  const programs = (program) =>
    buildMockEvaluation(evaluateRequest({ program })).program_results.map((r) => r.program);
  assert.deepEqual(programs('engineering'), ['engineering', 'general']);
  assert.deepEqual(programs('general'), ['general']);
});
test('mock은 소프트웨어전공에 세부전공필수 항목을 넣지 않는다', () => {
  const ids = (sub_major) =>
    buildMockEvaluation(evaluateRequest({ sub_major })).common_requirements.map((r) => r.id);
  assert.deepEqual(ids('ai'), ['sub_major_required', 'thesis', 'topcit']);
  assert.deepEqual(ids('software'), ['thesis', 'topcit']);
  const group = buildMockEvaluation(evaluateRequest()).common_requirements[0];
  assert.ok(isCourseGroupResult(group));
});
test('mock은 F·빈 성적을 excluded_courses에 요청 index로 넣고 총학점에서 뺀다', () => {
  const result = buildMockEvaluation(evaluateRequest());
  assert.deepEqual(
    result.excluded_courses.map((c) => c.index),
    [2, 4],
  );
  // 인정: 3 + 2 + 3(재수강 B0) = 8
  assert.equal(result.program_results[0].total.earned, 8);
  assert.deepEqual(
    result.unmatched_courses.map((c) => c.index),
    [0, 1, 3],
  );
});
test('mock은 보류 영역을 null 숫자와 reason으로 표시한다', () => {
  const category = buildMockEvaluation(evaluateRequest()).program_results[0].categories[0];
  assert.equal(category.status, 'pending');
  assert.equal(category.required, null);
  assert.ok(category.reason);
});
test('mock 최종 판정은 unmet > pending > met 순서로 합친다', () => {
  assert.equal(buildMockEvaluation(evaluateRequest()).graduation_status, 'unmet');
  const allCommonMet = buildMockEvaluation(
    evaluateRequest({ sub_major: 'software', thesis_passed: true, topcit_taken: true }),
  );
  assert.equal(allCommonMet.graduation_status, 'pending');
});
test('mock 클라이언트는 PDF가 아니면 NOT_PDF, 지원하지 않는 학번이면 400을 낸다', async () => {
  const client = createMockClient();
  await assert.rejects(client.parseTranscript(new Blob(['hello'])), (e) => e.code === 'NOT_PDF');
  const parsed = await client.parseTranscript(new Blob(['%PDF-1.7 ...']));
  assert.equal(parsed.admission_year, 2024);
  assert.equal(parsed.courses.length, MOCK_COURSES.length);
  await assert.rejects(
    client.evaluate(evaluateRequest({ admission_year: 2023 })),
    (e) => e.code === 'UNSUPPORTED_ADMISSION_YEAR' && e.status === 400,
  );
});
test('mock 클라이언트도 취소하면 aborted를 낸다', async () => {
  const controller = new AbortController();
  const pending = createMockClient({ delayMs: 1000 }).evaluate(evaluateRequest(), {
    signal: controller.signal,
  });
  controller.abort();
  await assert.rejects(pending, (e) => e instanceof ApiError && e.kind === 'aborted');
});
