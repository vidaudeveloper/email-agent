"""In-memory MCP credential store (P0).

Maps user_id -> {server: api_key}. Production should use encrypted persistent storage.
"""

from __future__ import annotations

from threading import Lock

_lock = Lock()
_store: dict[str, dict[str, str]] = {}


def set_credential(user_id: str, server: str, api_key: str) -> None:
    with _lock:
        if user_id not in _store:
            _store[user_id] = {}
        _store[user_id][server] = api_key


def get_credential(user_id: str, server: str) -> str | None:
    with _lock:
        return _store.get(user_id, {}).get(server)


def clear_credentials() -> None:
    """Reset store (for tests)."""
    with _lock:
        _store.clear()
