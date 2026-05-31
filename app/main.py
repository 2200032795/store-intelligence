from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time, uuid, structlog

from app.ingestion import router as ingest_router
from app.metrics   import router as metrics_router
from app.funnel    import router as funnel_router
from app.anomalies import router as anomaly_router
from app.health    import router as health_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

app = FastAPI(
    title="Store Intelligence API",
    description="Purplle Tech Challenge 2026 — Brigade Bangalore",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())[:8]
    store_id = request.path_params.get("store_id", "-")
    start    = time.time()
    try:
        response = await call_next(request)
        latency  = int((time.time() - start) * 1000)
        log.info("request",
                 trace_id=trace_id,
                 store_id=store_id,
                 endpoint=str(request.url.path),
                 latency_ms=latency,
                 status_code=response.status_code)
        return response
    except Exception as exc:
        latency = int((time.time() - start) * 1000)
        log.error("request_error",
                  trace_id=trace_id,
                  endpoint=str(request.url.path),
                  latency_ms=latency,
                  error=str(exc))
        return JSONResponse(
            status_code=503,
            content={"error": "service_unavailable"},
        )


app.include_router(ingest_router)
app.include_router(metrics_router)
app.include_router(funnel_router)
app.include_router(anomaly_router)
app.include_router(health_router)


@app.get("/")
def root():
    return {"message": "Store Intelligence API v1.0", "docs": "/docs"}