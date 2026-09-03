"""RFC 9457-compatible application error helpers."""

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class ProblemDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    trace_id: str | None = None


def problem_response(
    *,
    type: str,
    title: str,
    status: int,
    detail: str,
    instance: str | None = None,
    trace_id: str | None = None,
    extensions: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ProblemDetails(
        type=type,
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        trace_id=trace_id,
    ).model_dump(exclude_none=True)
    if extensions:
        body["extensions"] = extensions
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )
