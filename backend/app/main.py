"""Wazuh Autopilot — agentic SOC platform for Wazuh, built on Strands Agents."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .api import admin, auth, ops, swarm
from .config import VERSION, get_config
from .db import SessionLocal, session_scope, utcnow
from .events import bus
from .ingest import cron_matches, poller
from .metrics import prometheus
from .models import Run, Span, Workflow
from .orchestrator import orchestrator
from .seed import init_db
from .settings_store import get_section

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("strands").setLevel(logging.WARNING)
for _n in ("httpx", "httpx2", "mcp"):
    logging.getLogger(_n).setLevel(logging.WARNING)
log = logging.getLogger("autopilot")


class _RedactTokens(logging.Filter):
    """Access logs must not carry credentials passed as ?token= (the SSE stream authenticates that way)."""

    _re = __import__("re").compile(r"(token=)[^&\s\"]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(self._re.sub(r"\1[redacted]", a) if isinstance(a, str) else a for a in record.args)
        if isinstance(record.msg, str):
            record.msg = self._re.sub(r"\1[redacted]", record.msg)
        return True


logging.getLogger("uvicorn.access").addFilter(_RedactTokens())


def _setup_otel() -> None:
    with session_scope() as db:
        obs = get_section(db, "observability")
    endpoint = obs.get("otlp_endpoint")
    if not endpoint:
        return
    try:
        from strands.telemetry import StrandsTelemetry

        headers = dict(h.split("=", 1) for h in (obs.get("otlp_headers") or "").split(",") if "=" in h)
        StrandsTelemetry().setup_otlp_exporter(endpoint=endpoint.rstrip("/") + "/v1/traces", headers=headers or None)
        log.info("OpenTelemetry export enabled → %s", endpoint)
    except Exception:
        log.exception("failed to enable OpenTelemetry export")


async def _poll_loop() -> None:
    while True:
        with session_scope() as db:
            interval = int(get_section(db, "ingestion").get("poll_interval_s", 30))
        await asyncio.to_thread(poller.poll_once)
        await asyncio.sleep(max(10, interval))


async def _scheduler_loop() -> None:
    last_minute = None
    while True:
        now = utcnow().replace(second=0, microsecond=0)
        if now != last_minute:
            last_minute = now
            with session_scope() as db:
                due = [w.id for w in db.query(Workflow).filter_by(enabled=True).all()
                       if (w.trigger or {}).get("type") == "schedule" and cron_matches(w.trigger.get("cron", ""), now)]
            for wf_id in due:
                try:
                    await asyncio.to_thread(orchestrator.start_run, wf_id, {}, "schedule")
                except Exception:
                    log.exception("scheduled run %s failed to start", wf_id)
            await asyncio.to_thread(orchestrator.expire_actions)
            if now.minute == 0:
                await asyncio.to_thread(_retention)
        await asyncio.sleep(15)


def _retention() -> None:
    with session_scope() as db:
        days = int(get_section(db, "observability").get("trace_retention_days", 30))
        cutoff = utcnow() - timedelta(days=days)
        old = [r for (r,) in db.query(Run.id).filter(Run.started_at < cutoff).all()]
        if old:
            db.query(Span).filter(Span.run_id.in_(old)).delete(synchronize_session=False)
            db.query(Run).filter(Run.id.in_(old)).delete(synchronize_session=False)


def _recover_interrupted_runs() -> None:
    with session_scope() as db:
        for r in db.query(Run).filter(Run.status.in_(["queued", "running"])).all():
            r.status, r.error, r.finished_at = "failed", "Interrupted by platform restart", utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _recover_interrupted_runs()
    _setup_otel()
    bus.bind_loop(asyncio.get_running_loop())
    tasks = []
    if get_config().scheduler_enabled:
        tasks = [asyncio.create_task(_poll_loop()), asyncio.create_task(_scheduler_loop())]
    log.info("Wazuh Autopilot %s ready (demo_mode=%s)", VERSION, get_config().demo_mode)
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Wazuh Autopilot", version=VERSION, lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

cfg = get_config()
if cfg.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


for r in (auth.router, ops.router, swarm.router, admin.router):
    app.include_router(r, prefix="/api/v1")



@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    db = SessionLocal()
    try:
        if not get_section(db, "observability").get("prometheus_enabled", True):
            return PlainTextResponse("", status_code=404)
        return prometheus(db)
    finally:
        db.close()


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


# -- SPA ---------------------------------------------------------------------------
dist = cfg.ui_dist
if (dist / "index.html").exists():
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
else:
    @app.get("/", include_in_schema=False)
    def no_ui():
        return JSONResponse({"detail": "UI not built. API docs at /api/docs"})
