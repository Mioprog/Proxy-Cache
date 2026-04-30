import time
import pytest
from fastapi.testclient import TestClient

import cache_store
from dashboard.server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset shared state before each test."""
    with cache_store.cache_lock:
        cache_store.cache.clear()
    cache_store.stats["hits"] = 0
    cache_store.stats["misses"] = 0
    cache_store.stats["start_time"] = time.time()
    cache_store.cache_expiration_time = 60
    yield


# ── /api/health ───────────────────────────────────────────────────────────────

def test_health_status_ok():
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_response_fields():
    response = client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert isinstance(data["timestamp"], float)


# ── /api/stats ────────────────────────────────────────────────────────────────

def test_stats_status_ok():
    response = client.get("/api/stats")
    assert response.status_code == 200


def test_stats_response_fields():
    response = client.get("/api/stats")
    data = response.json()
    for field in ("hits", "misses", "cache_entries", "cache_size_bytes",
                  "cache_expiration_seconds", "uptime_seconds"):
        assert field in data, f"Missing field: {field}"


def test_stats_initial_values():
    response = client.get("/api/stats")
    data = response.json()
    assert data["hits"] == 0
    assert data["misses"] == 0
    assert data["cache_entries"] == 0
    assert data["cache_size_bytes"] == 0


def test_stats_reflects_cache_state():
    with cache_store.cache_lock:
        cache_store.cache["get /test http/1.1"] = {
            "data": b"hello",
            "timestamp": time.time(),
        }
    cache_store.stats["hits"] = 3
    cache_store.stats["misses"] = 7

    response = client.get("/api/stats")
    data = response.json()
    assert data["hits"] == 3
    assert data["misses"] == 7
    assert data["cache_entries"] == 1
    assert data["cache_size_bytes"] == 5


# ── /api/cache ────────────────────────────────────────────────────────────────

def test_list_cache_empty():
    response = client.get("/api/cache")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["entries"] == []


def test_list_cache_with_entries():
    with cache_store.cache_lock:
        cache_store.cache["get /a http/1.1"] = {"data": b"aaa", "timestamp": time.time()}
        cache_store.cache["get /b http/1.1"] = {"data": b"bb", "timestamp": time.time()}

    response = client.get("/api/cache")
    data = response.json()
    assert data["total"] == 2
    assert len(data["entries"]) == 2


def test_list_cache_pagination():
    with cache_store.cache_lock:
        for i in range(5):
            cache_store.cache[f"get /path{i} http/1.1"] = {
                "data": b"x",
                "timestamp": time.time(),
            }

    response = client.get("/api/cache?page=1&per_page=2")
    data = response.json()
    assert data["total"] == 5
    assert len(data["entries"]) == 2
    assert data["page"] == 1
    assert data["per_page"] == 2


# ── DELETE /api/cache ─────────────────────────────────────────────────────────

def test_clear_cache():
    with cache_store.cache_lock:
        cache_store.cache["get /x http/1.1"] = {"data": b"x", "timestamp": time.time()}

    response = client.delete("/api/cache")
    assert response.status_code == 200
    assert response.json()["cleared"] == 1

    with cache_store.cache_lock:
        assert len(cache_store.cache) == 0


# ── DELETE /api/cache/{key} ───────────────────────────────────────────────────

def test_delete_entry():
    key = "get /hello http/1.1"
    with cache_store.cache_lock:
        cache_store.cache[key] = {"data": b"hi", "timestamp": time.time()}

    response = client.delete(f"/api/cache/{key}")
    assert response.status_code == 200
    assert response.json()["deleted"] == key

    with cache_store.cache_lock:
        assert key not in cache_store.cache


def test_delete_entry_not_found():
    response = client.delete("/api/cache/nonexistent key")
    assert response.status_code == 404


# ── HTML dashboard ────────────────────────────────────────────────────────────

def test_dashboard_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
