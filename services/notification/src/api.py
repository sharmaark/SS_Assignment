import json
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .business import should_delay, should_fail
from .config import get_settings
from .data import NotificationRepository

settings = get_settings()
repository = NotificationRepository(settings.notification_mongodb_url, settings.notification_mongodb_database)
correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(settings.service_name)


def log_event(event: str, **values) -> None:
    logger.info(json.dumps({"service": settings.service_name, "event": event, "correlation_id": correlation_id_context.get(), **values}, default=str))


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialise()
    yield


app = FastAPI(title="GeoInspect Notification Service", version="1.0.0", lifespan=lifespan)
app.state.mock_mode = settings.mock_mode


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    token = correlation_id_context.set(correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        correlation_id_context.reset(token)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder({"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": {"violations": exc.errors()}}, "correlation_id": correlation_id_context.get()}))


class NotificationCreate(BaseModel):
    delivery_key: str = Field(min_length=1, max_length=100)
    assignment_id: UUID
    work_order_id: UUID
    message: str = Field(min_length=1, max_length=500)


class MockModeUpdate(BaseModel):
    mode: str = Field(pattern="^(normal|fail|slow|commit_then_slow)$")


@app.get("/health")
def health(request: Request):
    repository.health()
    return {"status": "UP", "service": settings.service_name, "mock_mode": request.app.state.mock_mode}


@app.put("/api/v1/mock-mode")
def update_mock_mode(payload: MockModeUpdate, request: Request):
    if not settings.allow_mock_control:
        return JSONResponse(status_code=404, content={"error": {"code": "NOT_FOUND", "message": "Mock control is disabled", "details": {}}, "correlation_id": correlation_id_context.get()})
    request.app.state.mock_mode = payload.mode
    log_event("mock_mode_changed", mode=payload.mode)
    return {"mode": payload.mode}


@app.post("/api/v1/notifications")
def send_notification(payload: NotificationCreate, request: Request):
    data = payload.model_dump(mode="json")
    item, acquired = repository.claim(data)
    if not acquired:
        status_code = 200 if item["status"] == "SENT" else 202
        log_event("notification_replayed", delivery_key=payload.delivery_key, status=item["status"])
        return JSONResponse(status_code=status_code, content=json.loads(json.dumps(item, default=str)))

    mock_mode = request.app.state.mock_mode
    log_event("mock_delivery_started", delivery_key=payload.delivery_key, mode=mock_mode, attempt=item["attempts"])
    if should_fail(mock_mode):
        repository.mark_failed(payload.delivery_key)
        log_event("mock_delivery_failed", delivery_key=payload.delivery_key)
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "PROVIDER_UNAVAILABLE", "message": "Mock provider failed", "details": {}}, "correlation_id": correlation_id_context.get()},
        )

    if mock_mode == "commit_then_slow":
        item = repository.mark_sent(payload.delivery_key)
    if should_delay(mock_mode):
        time.sleep(settings.mock_delay_seconds)
    if mock_mode != "commit_then_slow":
        item = repository.mark_sent(payload.delivery_key)
    log_event("notification_sent", delivery_key=payload.delivery_key)
    return JSONResponse(status_code=201, content=json.loads(json.dumps(item, default=str)))


@app.get("/api/v1/notifications")
def list_notifications():
    return {"items": repository.list_all()}
