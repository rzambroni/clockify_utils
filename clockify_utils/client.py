"""
Clockify API Client

A Python client for interacting with the Clockify REST API (v1) and the
Reports API. The original methods keep their exact signatures and behavior;
everything else is additive.

Datetime handling: naive datetimes are sent as-is with a "Z" suffix (the
original behavior, so the weekly scheduler stays identical). Timezone-aware
datetimes are converted to UTC first.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Iterable, Optional

import requests

ID_RE = re.compile(r"^[0-9a-f]{24}$")


class ClockifyAPIError(requests.HTTPError):
    """HTTP error that carries Clockify's response body in its message."""


class AmbiguousMatchError(LookupError):
    def __init__(self, kind: str, query: str, matches: list):
        self.kind, self.query, self.matches = kind, query, matches
        names = ", ".join(m.get("name", m.get("id", "?")) for m in matches[:10])
        super().__init__(f"'{query}' matches {len(matches)} {kind}s: {names}. Be more specific or pass the ID.")


def format_time(dt: datetime) -> str:
    """Format for the API. Naive = legacy passthrough; aware = converted to UTC."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_api_time(value: str) -> datetime:
    """Parse an API timestamp into an aware datetime.

    Handles '2026-11-17T14:04:00Z' (time-entries API) and
    '2026-11-17T06:00:00-03:00' (Reports API).
    """
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_duration(value) -> int:
    """Seconds from an ISO 8601 'PT2H56M' string or a number of seconds."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    m = _DURATION_RE.fullmatch(value)
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def match_by_name(items: list, query: str, kind: str, key: str = "name") -> dict:
    """Resolve an ID or a name (exact, then case-insensitive substring) to one item."""
    if ID_RE.match(query):
        for item in items:
            if item.get("id") == query:
                return item
        raise LookupError(f"No {kind} with ID {query}")
    q = query.lower()
    exact = [i for i in items if str(i.get(key, "")).lower() == q]
    if len(exact) == 1:
        return exact[0]
    partial = exact or [i for i in items if q in str(i.get(key, "")).lower()]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise LookupError(f"No {kind} matches '{query}'")
    raise AmbiguousMatchError(kind, query, partial)


class ClockifyClient:
    """Client for Clockify API interactions."""

    BASE_URL = "https://api.clockify.me/api/v1"
    REPORTS_URL = "https://reports.api.clockify.me/v1"
    MAX_RETRIES = 3

    def __init__(self, api_key: str, workspace_id: Optional[str] = None):
        """
        Initialize the Clockify client.

        Args:
            api_key: Clockify API key
            workspace_id: Workspace ID to operate on. If omitted, the only
                workspace the key can see is used (error if there are several).
        """
        self.api_key = api_key
        self._workspace_id = workspace_id
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        })
        self._user_id: Optional[str] = None
        self._cache: dict = {}

    @classmethod
    def from_env(cls, api_key: Optional[str] = None, workspace_id: Optional[str] = None) -> "ClockifyClient":
        """Build a client from the shared settings (see clockify_utils.settings)."""
        from .settings import get_settings

        s = get_settings(api_key, workspace_id)
        return cls(api_key=s.api_key, workspace_id=s.workspace_id)

    # ── plumbing ──────────────────────────────────────────────────────────

    @property
    def workspace_id(self) -> str:
        if not self._workspace_id:
            workspaces = self.get_workspaces()
            if len(workspaces) != 1:
                names = ", ".join(f"{w['name']} ({w['id']})" for w in workspaces)
                raise LookupError(f"Several workspaces available, set CLOCKIFY_WORKSPACE_ID: {names}")
            self._workspace_id = workspaces[0]["id"]
        return self._workspace_id

    @workspace_id.setter
    def workspace_id(self, value: str) -> None:
        self._workspace_id = value

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        for attempt in range(self.MAX_RETRIES + 1):
            response = self.session.request(method, url, **kwargs)
            if response.status_code == 429 and attempt < self.MAX_RETRIES:
                time.sleep(float(response.headers.get("Retry-After", 1 + attempt * 2)))
                continue
            break
        if not response.ok:
            body = (response.text or "").strip()[:500]
            raise ClockifyAPIError(
                f"{response.status_code} {response.reason} for {method} {url}" + (f": {body}" if body else ""),
                response=response,
            )
        return response

    def _get(self, path: str, params: Optional[dict] = None):
        return self._request("GET", f"{self.BASE_URL}{path}", params=params).json()

    def _get_paginated(self, path: str, params: Optional[dict] = None, page_size: int = 500) -> list:
        params = dict(params or {})
        params["page-size"] = page_size
        results: list = []
        page = 1
        while True:
            params["page"] = page
            batch = self._get(path, params)
            results.extend(batch)
            if len(batch) < page_size:
                return results
            page += 1

    # ── original API (unchanged signatures) ───────────────────────────────

    @property
    def user_id(self) -> str:
        """Get and cache the current user's ID."""
        if self._user_id is None:
            self._user_id = self.get_user()["id"]
        return self._user_id

    def get_user(self) -> dict:
        """Get current user info."""
        return self._get("/user")

    def get_projects(self, archived: bool = False) -> list[dict]:
        """
        Get all projects in the workspace.

        Args:
            archived: Whether to include archived projects

        Returns:
            List of project dictionaries
        """
        params = {"archived": str(archived).lower()}
        return self._get_paginated(f"/workspaces/{self.workspace_id}/projects", params)

    def get_time_entries(
        self,
        start: datetime,
        end: datetime,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Get time entries for a user (default: the current user) within a date range.
        Follows pagination, so more than 500 entries are returned too.

        Args:
            start: Start datetime
            end: End datetime
            project_id: Optional project ID to filter by
            user_id: Optional user ID (needs admin rights for other users)

        Returns:
            List of time entry dictionaries
        """
        params = {
            "start": format_time(start),
            "end": format_time(end),
        }
        if project_id:
            params["project"] = project_id
        uid = user_id or self.user_id
        return self._get_paginated(f"/workspaces/{self.workspace_id}/user/{uid}/time-entries", params)

    def create_time_entry(
        self,
        start: datetime,
        end: datetime,
        project_id: str,
        description: str,
        billable: bool = True
    ) -> dict:
        """
        Create a new time entry.

        Args:
            start: Start datetime
            end: End datetime
            project_id: Project ID
            description: Entry description
            billable: Whether the entry is billable

        Returns:
            Created time entry dictionary
        """
        payload = self.build_time_entry_payload(start, end, project_id, description, billable)
        return self._request(
            "POST", f"{self.BASE_URL}/workspaces/{self.workspace_id}/time-entries", json=payload
        ).json()

    @staticmethod
    def build_time_entry_payload(start, end, project_id, description, billable=True) -> dict:
        return {
            "start": format_time(start),
            "end": format_time(end),
            "projectId": project_id,
            "description": description,
            "billable": billable,
            "type": "REGULAR"
        }

    def get_existing_entries_by_project_and_date(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> dict[str, set[str]]:
        """
        Get a mapping of project IDs to dates that already have entries.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dictionary mapping project_id -> set of date strings (YYYY-MM-DD)
        """
        entries = self.get_time_entries(start_date, end_date)
        existing: dict[str, set[str]] = {}

        for entry in entries:
            project_id = entry.get("projectId")
            if not project_id:
                continue

            # Extract date from start time
            start_str = entry.get("timeInterval", {}).get("start", "")
            if start_str:
                date_str = start_str[:10]  # YYYY-MM-DD
                if project_id not in existing:
                    existing[project_id] = set()
                existing[project_id].add(date_str)

        return existing

    # ── new: lookups ──────────────────────────────────────────────────────

    def get_workspaces(self) -> list[dict]:
        return self._get("/workspaces")

    def get_users(self, name: Optional[str] = None, status: str = "ACTIVE") -> list[dict]:
        """Workspace members. status: ACTIVE, PENDING, DECLINED, INACTIVE or ALL."""
        params: dict = {}
        if name:
            params["name"] = name
        if status and status != "ALL":
            params["status"] = status
        return self._get_paginated(f"/workspaces/{self.workspace_id}/users", params)

    def _cached(self, key: str, loader):
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    def get_all_projects(self) -> list[dict]:
        """Active and archived projects (cached per client)."""
        return self._cached("projects:all", lambda: self.get_projects(False) + self.get_projects(True))

    def project_names(self) -> dict:
        """{project_id: name} for active and archived projects."""
        return {p["id"]: p.get("name", "") for p in self.get_all_projects()}

    def find_project(self, query: str, include_archived: bool = False) -> dict:
        """Project by ID or (partial, case-insensitive) name."""
        if include_archived:
            projects = self.get_all_projects()
        else:
            projects = self._cached("projects:active", lambda: self.get_projects(archived=False))
        return match_by_name(projects, query, "project")

    def find_user(self, query: str) -> dict:
        """User by ID, 'me', name or email (partial, case-insensitive)."""
        if query.lower() == "me":
            return self.get_user()
        users = self._cached("users:ALL", lambda: self.get_users(status="ALL"))
        try:
            return match_by_name(users, query, "user")
        except LookupError as name_error:
            try:
                return match_by_name(users, query, "user", key="email")
            except LookupError:
                raise name_error

    # ── new: writes ───────────────────────────────────────────────────────

    def delete_time_entry(self, entry_id: str) -> None:
        self._request("DELETE", f"{self.BASE_URL}/workspaces/{self.workspace_id}/time-entries/{entry_id}")

    # ── new: reports ──────────────────────────────────────────────────────

    def detailed_report(
        self,
        start: datetime,
        end: datetime,
        user_ids: Optional[Iterable[str]] = None,
        project_ids: Optional[Iterable[str]] = None,
        page_size: int = 1000,
    ) -> list[dict]:
        """
        All time entries in the workspace (every user) from the Reports API,
        following pagination. Each entry has userId, userName, projectId,
        projectName, description and timeInterval.duration (seconds).
        """
        body: dict = {
            "dateRangeStart": format_time(start).replace("Z", ".000Z"),
            "dateRangeEnd": format_time(end).replace("Z", ".999Z"),
            "detailedFilter": {"page": 1, "pageSize": page_size, "sortColumn": "DATE"},
            "sortOrder": "ASCENDING",
            "exportType": "JSON",
        }
        if user_ids:
            body["users"] = {"ids": list(user_ids), "contains": "CONTAINS", "status": "ALL"}
        if project_ids:
            body["projects"] = {"ids": list(project_ids), "contains": "CONTAINS", "status": "ALL"}
        url = f"{self.REPORTS_URL}/workspaces/{self.workspace_id}/reports/detailed"
        entries: list = []
        while True:
            data = self._request("POST", url, json=body).json()
            batch = data.get("timeentries") or []
            entries.extend(batch)
            if len(batch) < page_size:
                return entries
            body["detailedFilter"]["page"] += 1
