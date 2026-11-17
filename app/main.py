from __future__ import annotations

import os
import threading
import time

from fastapi import FastAPI
from fastapi import Request
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from app.bootstrap import ensure_db
from app.i18n import detect_lang
from app.i18n import tr
from app.routers.hadith import router as hadith_router
from app.routers.hijri import router as hijri_router
from app.routers.meta import router as meta_router
from app.routers.prayer import router as prayer_router
from app.routers.quran import router as quran_router

ensure_db()

app = FastAPI(
    title=tr("service_name", "en"),
    version="2.0.0",
    description=tr("service_desc", "en"),
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(meta_router)
app.include_router(quran_router)
app.include_router(hadith_router)
app.include_router(hijri_router)
app.include_router(prayer_router)

_rate_lock = threading.Lock()
_rate_buckets: dict[str, tuple[float, int]] = {}


def _parse_api_keys() -> set[str]:
    raw = os.getenv("ANJAL_API_KEYS", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _extract_api_key(request: Request) -> str | None:
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


@app.middleware("http")
async def v1_auth_and_rate_limit(request: Request, call_next):
    path = request.url.path
    lang = detect_lang(request)
    if not path.startswith("/v1"):
        return await call_next(request)

    configured_keys = _parse_api_keys()
    provided_key = _extract_api_key(request)
    if configured_keys and provided_key not in configured_keys:
        return JSONResponse(status_code=401, content={"ok": False, "lang": lang, "error": tr("unauthorized", lang)})

    window_sec = _get_env_int("ANJAL_RATE_LIMIT_WINDOW_SEC", 60)
    max_requests = _get_env_int("ANJAL_RATE_LIMIT_MAX_REQUESTS", 120)
    now = time.time()
    client_host = request.client.host if request.client else "unknown"
    identity = provided_key if provided_key else f"ip:{client_host}"

    with _rate_lock:
        start, count = _rate_buckets.get(identity, (now, 0))
        if now - start >= window_sec:
            start, count = now, 0
        count += 1
        _rate_buckets[identity] = (start, count)
        if count > max_requests:
            retry_after = max(1, int(window_sec - (now - start)))
            return JSONResponse(
                status_code=429,
                content={"ok": False, "lang": lang, "error": tr("rate_limit_exceeded", lang)},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


@app.middleware("http")
async def enforce_utf8_content_type(request: Request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json") and "charset=" not in content_type.lower():
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


@app.get("/", tags=["meta"])
def service_manifest(request: Request) -> dict:
    """Headless JSON service manifest listing dataset and API endpoints."""
    lang = detect_lang(request)
    return {
        "ok": True,
        "service": tr("service_name", lang),
        "description": tr("service_desc", lang),
        "version": app.version,
        "api_version": "v1",
        "lang": lang,
        "endpoints": {
            "health": "/v1/health",
            "meta": "/v1/meta",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "quran_surahs": "/v1/quran/surahs",
            "quran_ayah": "/v1/quran/ayah/{surah}/{ayah}",
            "quran_search": "/v1/quran/search",
            "hadith_collections": "/v1/hadith/collections",
            "hadith_entry": "/v1/hadith/{collection}/{hadith_number}",
            "hadith_search": "/v1/hadith/search",
            "hijri_to_gregorian": "/v1/hijri/to-gregorian",
            "hijri_from_gregorian": "/v1/hijri/from-gregorian",
            "prayer_countries": "/v1/prayer/countries",
            "prayer_cities": "/v1/prayer/cities",
            "prayer_times": "/v1/prayer/times",
            "prayer_search_city": "/v1/prayer/search-city",
        },
    }


@app.get("/docs", include_in_schema=False)
def custom_docs(request: Request):
    lang = detect_lang(request)
    return get_swagger_ui_html(
        openapi_url=f"/openapi.json?lang={lang}",
        title=f"{tr('service_name', lang)} - {tr('docs_title', lang)}",
    )


@app.get("/redoc", include_in_schema=False)
def custom_redoc(request: Request):
    lang = detect_lang(request)
    return get_redoc_html(
        openapi_url=f"/openapi.json?lang={lang}",
        title=f"{tr('service_name', lang)} - {tr('docs_title', lang)}",
    )


@app.get("/docs/ar", include_in_schema=False)
def custom_docs_ar():
    return RedirectResponse(url="/docs?lang=ar")


@app.get("/docs/en", include_in_schema=False)
def custom_docs_en():
    return RedirectResponse(url="/docs?lang=en")


@app.get("/openapi.json", include_in_schema=False)
def openapi_endpoint(request: Request):
    lang = detect_lang(request)
    schema = get_openapi(
        title=tr("service_name", lang),
        version=app.version,
        description=tr("service_desc", lang),
        routes=app.routes,
    )
    return JSONResponse(schema)


@app.exception_handler(Exception)
def fallback_error_handler(request: Request, exc: Exception):
    lang = detect_lang(request)
    return JSONResponse(status_code=500, content={"ok": False, "lang": lang, "error": str(exc)})
