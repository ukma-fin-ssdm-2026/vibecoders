from typing import Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from schemas import ErrorBody, ErrorDetail, ErrorResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[List[ErrorDetail]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        self.headers = headers


ERROR_DESCRIPTIONS = {
    400: "Некоректні вхідні дані: не пройшли валідацію",
    401: "Відсутній або недійсний токен доступу",
    403: "Недостатньо прав для цієї дії",
    404: "Ресурс не знайдено",
    409: "Конфлікт зі станом системи",
}


def error_docs(*codes: int) -> dict:
    return {code: {"model": ErrorResponse, "description": ERROR_DESCRIPTIONS[code]} for code in codes}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[List[ErrorDetail]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = [
            ErrorDetail(field=".".join(str(part) for part in error["loc"]), message=str(error["msg"]))
            for error in exc.errors()
        ]
        return error_response(400, "VALIDATION_ERROR", "Вхідні дані не пройшли валідацію", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        code = codes.get(exc.status_code, "HTTP_ERROR")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        return error_response(500, "INTERNAL_ERROR", "Внутрішня помилка сервера")
