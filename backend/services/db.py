"""Acceso a datos de jobs/resultados. Supabase si esta configurado; memoria en caso contrario."""
import threading
import time
from functools import lru_cache
from typing import Any

import config

TABLE = "tryon_jobs"


class MemoryStore:
    def __init__(self):
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def insert(self, row: dict) -> dict:
        with self._lock:
            self._rows[row["id"]] = dict(row)
            return dict(row)

    def update(self, job_id: str, fields: dict) -> dict | None:
        with self._lock:
            row = self._rows.get(job_id)
            if row is None:
                return None
            row.update(fields)
            return dict(row)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            row = self._rows.get(job_id)
            return dict(row) if row else None

    def list_by_user(self, user_id: str, limit: int) -> list[dict]:
        with self._lock:
            rows = [r for r in self._rows.values() if r.get("user_id") == user_id]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows[:limit]

    def purge_older_than(self, seconds: int) -> None:
        cutoff = time.time() - seconds
        with self._lock:
            stale = [k for k, r in self._rows.items() if r.get("created_ts", 0) < cutoff]
            for key in stale:
                self._rows.pop(key, None)


class SupabaseStore:
    def __init__(self):
        from supabase import create_client

        self._client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

    def _table(self):
        return self._client.table(TABLE)

    def insert(self, row: dict) -> dict:
        payload = {k: v for k, v in row.items() if k != "created_ts"}
        data = self._table().insert(payload).execute().data
        return data[0] if data else payload

    def update(self, job_id: str, fields: dict) -> dict | None:
        data = self._table().update(fields).eq("id", job_id).execute().data
        return data[0] if data else None

    def get(self, job_id: str) -> dict | None:
        data = self._table().select("*").eq("id", job_id).limit(1).execute().data
        return data[0] if data else None

    def list_by_user(self, user_id: str, limit: int) -> list[dict]:
        query = self._table().select("*").eq("user_id", user_id)
        return query.order("created_at", desc=True).limit(limit).execute().data

    def purge_older_than(self, seconds: int) -> None:
        return None  # Se gestiona con politicas/cron en Supabase


@lru_cache(maxsize=1)
def get_store():
    return SupabaseStore() if config.db_enabled() else MemoryStore()
