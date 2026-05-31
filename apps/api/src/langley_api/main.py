"""FastAPI app: serves the demo UI and a single analysis endpoint.

Thin by design — the route validates input, calls ``analyze_token`` (the langley_risk
service), and returns the structured report. All intelligence lives in the agent package.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from langley_api.ratelimit import RateLimiter, RateLimitError
from langley_api.schemas import AnalyzeRequest
from langley_risk.config import get_settings, load_env_file
from langley_risk.domain.report import TokenRiskReport
from langley_risk.errors import LangleyRiskError
from langley_risk.observability.logging import configure_logging
from langley_risk.service.analyze import analyze_token
from langley_synthesis.domain.report import IntelligenceReport
from langley_synthesis.service.orchestrate import synthesize_token

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    load_env_file()
    settings = get_settings()
    configure_logging(level=settings.log_level, as_json=settings.log_json)
    logger.info("Langley API ready (provider=%s)", settings.provider.value)
    yield


app = FastAPI(title="Langley", description="Private crypto intelligence", lifespan=_lifespan)

# Public-demo guardrails: bound per-client rate and total daily spend.
_limiter = RateLimiter()


def _guard(request: Request) -> None:
    """Enforce the per-client + daily-cap rate limit; raise HTTP 429 if exceeded."""
    client = request.client.host if request.client else "unknown"
    try:
        _limiter.check(client)
    except RateLimitError as exc:
        raise HTTPException(
            status_code=429, detail=exc.reason, headers={"Retry-After": str(exc.retry_after_s)}
        ) from exc


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/intelligence", response_model=IntelligenceReport)
async def intelligence(body: AnalyzeRequest, request: Request) -> IntelligenceReport:
    """Full multi-agent report: Risk Guardian + On-Chain Forensics, fused by Synthesis."""
    _guard(request)
    try:
        return await synthesize_token(body.query)
    except LangleyRiskError as exc:
        logger.warning("Synthesis failed for %r: %s", body.query, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/analyze", response_model=TokenRiskReport)
async def analyze(body: AnalyzeRequest, request: Request) -> TokenRiskReport:
    """Single-agent endpoint: the Risk Guardian's evidence-cited verdict only."""
    _guard(request)
    try:
        return await analyze_token(body.query)
    except LangleyRiskError as exc:
        logger.warning("Analysis failed for %r: %s", body.query, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def run() -> None:
    """Console entrypoint: launch the dev server."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
