"""Bounded, memory-only multipart upload; never use disk-spooled UploadFile."""

from io import BytesIO

from fastapi import APIRouter, HTTPException, Request
from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.concurrency import run_in_threadpool

from app.schemas.transcripts import ParseErrorResponse, TranscriptParseResponse
from app.services.transcript_parser import TranscriptParseError, parse_transcript

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024
MAX_REQUEST_BYTES = MAX_FILE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


def _invalid_upload(message: str = "file 필드에 PDF 파일 1개를 첨부해 주세요.") -> HTTPException:
    # Match FastAPI's validation-error envelope without echoing submitted values.
    return HTTPException(
        status_code=422,
        detail=[{"type": "value_error", "loc": ["body", "file"], "msg": message, "input": None}],
    )


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail={
            "code": "FILE_TOO_LARGE",
            "message": "PDF는 10 MiB 이하, multipart 부가 데이터는 64 KiB 이하만 허용합니다.",
        },
    )


class _MemoryUpload:
    """A single file part, bounded before buffering; no filename or headers retained."""

    def __init__(self) -> None:
        self.buffer = BytesIO()
        self.part_count = 0
        self.finished = False
        self.file_finished = False
        self.header_name = bytearray()
        self.header_value = bytearray()
        self.disposition = b""

    def on_part_begin(self) -> None:
        self.part_count += 1
        if self.part_count > 1:
            raise _invalid_upload()
        self.disposition = b""

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self.header_name.extend(data[start:end])

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self.header_value.extend(data[start:end])

    def on_header_end(self) -> None:
        if self.header_name.lower() == b"content-disposition":
            self.disposition = bytes(self.header_value)
        self.header_name.clear()
        self.header_value.clear()

    def on_headers_finished(self) -> None:
        disposition, options = parse_options_header(self.disposition)
        if disposition != b"form-data" or options.get(b"name") != b"file":
            raise _invalid_upload()
        if not options.get(b"filename"):
            raise _invalid_upload()
        self.disposition = b""

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self.buffer.tell() + end - start > MAX_FILE_BYTES:
            raise _too_large()
        self.buffer.write(data[start:end])

    def on_part_end(self) -> None:
        self.file_finished = True

    def on_end(self) -> None:
        self.finished = True

    def callbacks(self) -> dict:
        return {
            name: getattr(self, name)
            for name in (
                "on_part_begin",
                "on_header_field",
                "on_header_value",
                "on_header_end",
                "on_headers_finished",
                "on_part_data",
                "on_part_end",
                "on_end",
            )
        }


async def _read_pdf(request: Request) -> bytes:
    content_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary or len(boundary) > 200:
        raise _invalid_upload()

    upload = _MemoryUpload()
    try:
        # Our aggregate envelope limit handles oversized headers as HTTP 413.
        parser = MultipartParser(boundary, upload.callbacks(), max_header_size=MAX_REQUEST_BYTES)
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                raise _too_large()
            parser.write(chunk)
            if total - upload.buffer.tell() > MAX_MULTIPART_OVERHEAD_BYTES:
                raise _too_large()
        parser.finalize()
        # python-multipart finalize() alone does not reject truncated input.
        if not upload.finished or not upload.file_finished:
            raise _invalid_upload("multipart 요청이 불완전합니다. PDF를 다시 첨부해 주세요.")
        return upload.buffer.getvalue()
    except (MultipartParseError, ValueError) as exc:
        raise _invalid_upload("multipart 요청 형식을 확인해 주세요.") from exc
    finally:
        upload.buffer.close()


@router.post(
    "/parse",
    response_model=TranscriptParseResponse,
    responses={
        400: {"model": ParseErrorResponse, "description": "PDF 또는 이수내역을 읽을 수 없음"},
        413: {"model": ParseErrorResponse, "description": "파일 10 MiB 또는 요청 크기 초과"},
        422: {"description": "file 필드에 PDF 파일 1개 필요"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    },
                },
            },
        },
    },
)
async def parse_pdf(request: Request) -> TranscriptParseResponse:
    """KLAS 이수내역 PDF를 메모리에서 처리한다. 실제 양식 검증은 샘플 확보 후 필요하다."""
    pdf_bytes = await _read_pdf(request)
    try:
        return await run_in_threadpool(parse_transcript, pdf_bytes)
    except TranscriptParseError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": exc.message}
        ) from exc
