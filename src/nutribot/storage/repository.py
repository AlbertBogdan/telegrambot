"""Storage layer: Protocol interface + Supabase implementation + in-memory fake.

Handlers never touch Supabase directly — they go through this interface,
which enables testing with InMemoryRepository.
"""

import json as _json
import logging
from datetime import date
from typing import Protocol

import httpx
from postgrest import APIError
from supabase import Client, create_client

from nutribot.domain.models import DailyLog, MacroTotals, UserProfile

logger = logging.getLogger(__name__)


class Repository(Protocol):
    """Abstract storage interface for nutribot.

    All implementations must satisfy this protocol. The SupabaseRepository
    is the production implementation; InMemoryRepository is for tests.
    """

    async def get_user(self, user_id: int) -> UserProfile | None:
        """Fetch a user profile by Telegram user_id, or None if not found."""
        ...

    async def upsert_user(
        self, user_id: int, norm_b: float, norm_j: float, norm_u: float
    ) -> UserProfile:
        """Create or update a user profile. Returns the persisted profile."""
        ...

    async def get_log(self, user_id: int, log_date: date) -> DailyLog | None:
        """Fetch today's daily_log row, or None."""
        ...

    async def upsert_log(
        self, user_id: int, log_date: date, totals: MacroTotals
    ) -> DailyLog:
        """Create or update a daily_log row. Returns the persisted log."""
        ...

    async def get_logs_for_month(
        self, user_id: int, year: int, month: int
    ) -> list[DailyLog]:
        """Fetch all daily_log rows for a user in a given month."""
        ...


class InMemoryRepository:
    """In-memory repository for unit tests. Not async-safe across threads."""

    def __init__(self) -> None:
        self._users: dict[int, UserProfile] = {}
        self._logs: dict[tuple[int, date], DailyLog] = {}

    async def get_user(self, user_id: int) -> UserProfile | None:
        return self._users.get(user_id)

    async def upsert_user(
        self, user_id: int, norm_b: float, norm_j: float, norm_u: float
    ) -> UserProfile:
        profile = UserProfile(
            user_id=user_id, norm_b=norm_b, norm_j=norm_j, norm_u=norm_u
        )
        self._users[user_id] = profile
        return profile

    async def get_log(self, user_id: int, log_date: date) -> DailyLog | None:
        return self._logs.get((user_id, log_date))

    async def upsert_log(
        self, user_id: int, log_date: date, totals: MacroTotals
    ) -> DailyLog:
        log = DailyLog(user_id=user_id, date=log_date, totals=totals)
        self._logs[(user_id, log_date)] = log
        return log

    async def get_logs_for_month(
        self, user_id: int, year: int, month: int
    ) -> list[DailyLog]:
        result: list[DailyLog] = []
        for (uid, d), log in self._logs.items():
            if uid == user_id and d.year == year and d.month == month:
                result.append(log)
        return result


class SupabaseRepository:
    """Supabase-backed repository for production use.

    Requires SUPABASE_URL and SUPABASE_KEY env vars (set via config.py
    or passed directly).
    """

    def __init__(self, url: str, key: str) -> None:
        self._client: Client = create_client(url, key)
        self._url = url.rstrip("/")
        self._key = key
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

    async def _upsert(self, table: str, data: dict[str, object], on_conflict: str) -> bool:
        """Raw HTTP upsert with explicit Prefer header (bypasses supabase-py bug)."""
        url = f"{self._url}/rest/v1/{table}?on_conflict={on_conflict}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=self._headers, content=_json.dumps(data))
                if resp.status_code not in (200, 201):
                    logger.error(
                        "Supabase upsert %s failed: HTTP %s body=%s",
                        table, resp.status_code, resp.text[:500],
                    )
                    return False
                return True
        except httpx.HTTPError as e:
            logger.error("Supabase upsert %s request failed: %s", table, e)
            return False

    async def get_user(self, user_id: int) -> UserProfile | None:
        try:
            res = (
                self._client.table("users")
                .select("*")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
        except APIError:
            return None
        if res is None:
            return None
        data = res.data
        if data is None:
            return None
        return UserProfile(
            user_id=int(data["user_id"]),
            norm_b=float(data["norm_b"]),
            norm_j=float(data["norm_j"]),
            norm_u=float(data["norm_u"]),
            onboarded=bool(data.get("onboarded", True)),
        )

    async def upsert_user(
        self, user_id: int, norm_b: float, norm_j: float, norm_u: float
    ) -> UserProfile:
        ok = await self._upsert("users", {
            "user_id": user_id,
            "norm_b": norm_b,
            "norm_j": norm_j,
            "norm_u": norm_u,
            "onboarded": True,
        }, on_conflict="user_id")
        if not ok:
            raise RuntimeError(
                "Не удалось сохранить профиль. Проверьте настройки Supabase."
            )
        saved = await self.get_user(user_id)
        if saved is None:
            raise RuntimeError(
                "Не удалось сохранить профиль. Проверьте настройки Supabase."
            )
        return saved

    async def get_log(self, user_id: int, log_date: date) -> DailyLog | None:
        try:
            res = (
                self._client.table("daily_log")
                .select("*")
                .eq("user_id", user_id)
                .eq("date", log_date.isoformat())
                .maybe_single()
                .execute()
            )
        except APIError:
            return None
        if res is None:
            return None
        data = res.data
        if data is None:
            return None
        return DailyLog(
            user_id=int(data["user_id"]),
            date=date.fromisoformat(data["date"]),
            totals=MacroTotals(
                b=float(data["total_b"]),
                j=float(data["total_j"]),
                u=float(data["total_u"]),
            ),
        )

    async def upsert_log(
        self, user_id: int, log_date: date, totals: MacroTotals
    ) -> DailyLog:
        ok = await self._upsert("daily_log", {
            "user_id": user_id,
            "date": log_date.isoformat(),
            "total_b": totals.b,
            "total_j": totals.j,
            "total_u": totals.u,
        }, on_conflict="user_id,date")
        if not ok:
            raise RuntimeError(
                "Не удалось сохранить запись. Проверьте настройки Supabase."
            )
        saved = await self.get_log(user_id, log_date)
        if saved is None:
            raise RuntimeError(
                "Не удалось сохранить запись. Проверьте настройки Supabase."
            )
        return saved

    async def get_logs_for_month(
        self, user_id: int, year: int, month: int
    ) -> list[DailyLog]:
        start = date(year, month, 1).isoformat()
        # Compute last day of month
        if month == 12:
            end = date(year + 1, 1, 1).isoformat()
        else:
            end = date(year, month + 1, 1).isoformat()
        try:
            res = (
                self._client.table("daily_log")
                .select("*")
                .eq("user_id", user_id)
                .gte("date", start)
                .lt("date", end)
                .order("date")
                .execute()
            )
        except APIError:
            return []
        if res is None:
            return []
        result: list[DailyLog] = []
        for row in res.data or []:
            result.append(
                DailyLog(
                    user_id=int(row["user_id"]),
                    date=date.fromisoformat(row["date"]),
                    totals=MacroTotals(
                        b=float(row["total_b"]),
                        j=float(row["total_j"]),
                        u=float(row["total_u"]),
                    ),
                )
            )
        return result
