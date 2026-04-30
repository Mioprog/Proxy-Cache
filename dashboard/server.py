import time
import os
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import cache_store

app = FastAPI(title="Proxy-Cache Dashboard", version="1.0.0")

_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_templates_dir)

# Optional bearer-token authentication.
# Set dashboard.token in config.conf to enable; leave empty to disable.
_dashboard_token: str = ""


def _check_token(authorization: Optional[str] = Header(default=None)) -> None:
    """Validate bearer token if one is configured."""
    if not _dashboard_token:
        return
    if authorization != f"Bearer {_dashboard_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── HTML dashboard ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health(_: None = Depends(_check_token)):
    """Return server health status."""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/api/stats")
async def stats(_: None = Depends(_check_token)):
    """Return proxy/cache statistics."""
    with cache_store.cache_lock:
        cache_entries = len(cache_store.cache)
        cache_size_bytes = sum(
            len(entry["data"]) for entry in cache_store.cache.values()
        )
    uptime = time.time() - cache_store.stats["start_time"]
    return {
        "hits": cache_store.stats["hits"],
        "misses": cache_store.stats["misses"],
        "cache_entries": cache_entries,
        "cache_size_bytes": cache_size_bytes,
        "cache_expiration_seconds": cache_store.cache_expiration_time,
        "uptime_seconds": round(uptime, 2),
    }


@app.get("/api/cache")
async def list_cache(page: int = 1, per_page: int = 20, _: None = Depends(_check_token)):
    """Return a paginated list of cached entries."""
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if per_page < 1 or per_page > 200:
        raise HTTPException(status_code=400, detail="per_page must be between 1 and 200")

    now = time.time()
    with cache_store.cache_lock:
        all_entries = [
            {
                "key": key,
                "size_bytes": len(entry["data"]),
                "created_at": entry["timestamp"],
                "expires_at": entry["timestamp"] + cache_store.cache_expiration_time,
                "expired": (now - entry["timestamp"]) > cache_store.cache_expiration_time,
            }
            for key, entry in cache_store.cache.items()
        ]

    total = len(all_entries)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "entries": all_entries[start:end],
    }


@app.delete("/api/cache")
async def clear_cache(_: None = Depends(_check_token)):
    """Clear all cache entries."""
    with cache_store.cache_lock:
        count = len(cache_store.cache)
        cache_store.cache.clear()
    return {"cleared": count}


@app.delete("/api/cache/{key:path}")
async def delete_cache_entry(key: str, _: None = Depends(_check_token)):
    """Delete a specific cache entry by key."""
    with cache_store.cache_lock:
        if key not in cache_store.cache:
            raise HTTPException(status_code=404, detail="Cache entry not found")
        del cache_store.cache[key]
    return {"deleted": key}


def start_dashboard(host: str = "127.0.0.1", port: int = 8080, token: str = ""):
    """Start the dashboard server (blocking – run in a daemon thread)."""
    import uvicorn

    global _dashboard_token
    _dashboard_token = token
    uvicorn.run(app, host=host, port=port, log_level="warning")
