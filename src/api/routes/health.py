import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import store
from errors import RETRY_AFTER_SECONDS
from schemas import DependencyStatus, HealthChecks, HealthResponse, HealthStatus

logger = logging.getLogger("api.health")

router = APIRouter(prefix="/api/v1", include_in_schema=False)


def check_database() -> DependencyStatus:
    try:
        session = store.SessionLocal()
        try:
            session.execute(text("SELECT 1 FROM users LIMIT 1"))
        finally:
            session.close()
    except SQLAlchemyError as exc:
        logger.error("Health check: database is unavailable: %s", exc.__class__.__name__)
        return DependencyStatus.unavailable
    return DependencyStatus.ok


@router.get("/health", response_model=HealthResponse)
def get_health():
    checks = HealthChecks(database=check_database())
    healthy = all(value == DependencyStatus.ok for value in checks.model_dump().values())
    body = HealthResponse(status=HealthStatus.healthy if healthy else HealthStatus.unhealthy, checks=checks)
    if healthy:
        return body
    return JSONResponse(
        status_code=503,
        content=body.model_dump(mode="json"),
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
    )
