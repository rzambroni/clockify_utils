"""
Shared settings resolution for every project that talks to Clockify.

One place decides where the API key, workspace and timezone come from, so
scripts, bots and skills stop each keeping their own copy of the key.

API key, first match wins:
  1. explicit argument
  2. CLOCKIFY_API_KEY (live environment, or a .env file: the current
     directory's first, then this repo's .env)
  3. CLOCKIFY_API_KEY_FILE, a file whose only content is the key
  4. "api_key" in the prefs file (${CLOCKIFY_PREFS_PATH:-~/.clockify-prefs.json})

Workspace ID, first match wins:
  1. explicit argument
  2. CLOCKIFY_WORKSPACE_ID
  3. "workspace_id" in the prefs file
  4. "workspace_id" in this repo's config.yaml
  5. the only workspace the key can see (resolved by the client)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone, tzinfo, datetime
from pathlib import Path
from typing import Optional

REPO_DIR = Path(__file__).resolve().parent.parent
REPO_ENV = REPO_DIR / ".env"
REPO_CONFIG = REPO_DIR / "config.yaml"

_env_loaded = False


def load_env_files() -> None:
    """Load .env files into os.environ without overriding values already set."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional for library use
        return
    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file():
        load_dotenv(cwd_env, override=False)
    if REPO_ENV.is_file():
        load_dotenv(REPO_ENV, override=False)


def prefs_path() -> Path:
    return Path(os.path.expanduser(os.environ.get("CLOCKIFY_PREFS_PATH", "~/.clockify-prefs.json")))


def load_prefs() -> dict:
    path = prefs_path()
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_prefs(updates: dict) -> Path:
    """Merge keys into the prefs file (never replaces it) and keep it private (0600)."""
    path = prefs_path()
    data = load_prefs()
    data.update({k: v for k, v in updates.items() if v is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    os.chmod(path, 0o600)
    return path


def _read_repo_config() -> dict:
    if not REPO_CONFIG.is_file():
        return {}
    try:
        import yaml

        return yaml.safe_load(REPO_CONFIG.read_text()) or {}
    except Exception:
        return {}


@dataclass
class Settings:
    api_key: str
    api_key_source: str
    workspace_id: Optional[str]
    workspace_source: Optional[str]
    tz: tzinfo
    tz_source: str
    prefs: dict = field(default_factory=dict)

    def masked_key(self) -> str:
        if not self.api_key:
            return "(none)"
        return self.api_key[:4] + "…" + self.api_key[-4:]


class SettingsError(RuntimeError):
    pass


def resolve_api_key(explicit: Optional[str] = None, prefs: Optional[dict] = None) -> tuple:
    """Return (key, source). key is "" when nothing was found."""
    if explicit:
        return explicit, "argument"
    load_env_files()
    if os.environ.get("CLOCKIFY_API_KEY"):
        return os.environ["CLOCKIFY_API_KEY"].strip(), "CLOCKIFY_API_KEY (env/.env)"
    key_file = os.environ.get("CLOCKIFY_API_KEY_FILE")
    if key_file:
        try:
            key = Path(os.path.expanduser(key_file)).read_text().strip()
            if key:
                return key, "CLOCKIFY_API_KEY_FILE"
        except OSError:
            pass
    prefs = load_prefs() if prefs is None else prefs
    if prefs.get("api_key"):
        return str(prefs["api_key"]).strip(), str(prefs_path())
    return "", ""


def resolve_workspace_id(explicit: Optional[str] = None, prefs: Optional[dict] = None) -> tuple:
    """Return (workspace_id, source), or (None, None) if not configured."""
    if explicit:
        return explicit, "argument"
    load_env_files()
    if os.environ.get("CLOCKIFY_WORKSPACE_ID"):
        return os.environ["CLOCKIFY_WORKSPACE_ID"].strip(), "CLOCKIFY_WORKSPACE_ID"
    prefs = load_prefs() if prefs is None else prefs
    if prefs.get("workspace_id"):
        return str(prefs["workspace_id"]), str(prefs_path())
    ws = _read_repo_config().get("workspace_id")
    if ws and not str(ws).startswith("your-"):
        return str(ws), str(REPO_CONFIG)
    return None, None


def resolve_timezone(prefs: Optional[dict] = None) -> tuple:
    """Local timezone used by the new commands (log, entries, report, gaps).

    CLOCKIFY_TZ (IANA name, e.g. America/Argentina/Buenos_Aires) >
    prefs timezone.offset > CLOCKIFY_TZ_OFFSET (whole hours) > system timezone.
    """
    load_env_files()
    name = os.environ.get("CLOCKIFY_TZ")
    if name:
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(name), "CLOCKIFY_TZ"
        except Exception:
            pass
    prefs = load_prefs() if prefs is None else prefs
    offset = (prefs.get("timezone") or {}).get("offset") if isinstance(prefs.get("timezone"), dict) else None
    source = str(prefs_path())
    if offset is None and os.environ.get("CLOCKIFY_TZ_OFFSET"):
        offset, source = os.environ["CLOCKIFY_TZ_OFFSET"], "CLOCKIFY_TZ_OFFSET"
    if offset is not None:
        try:
            return timezone(timedelta(hours=float(offset))), source
        except ValueError:
            pass
    return datetime.now().astimezone().tzinfo, "system"


def get_settings(api_key: Optional[str] = None, workspace_id: Optional[str] = None, require_key: bool = True) -> Settings:
    prefs = load_prefs()
    key, key_source = resolve_api_key(api_key, prefs)
    if require_key and not key:
        raise SettingsError(
            "Clockify API key not found. Set CLOCKIFY_API_KEY (env or "
            f"{REPO_ENV}), CLOCKIFY_API_KEY_FILE, or api_key in {prefs_path()}."
        )
    ws, ws_source = resolve_workspace_id(workspace_id, prefs)
    tz, tz_source = resolve_timezone(prefs)
    return Settings(key, key_source, ws, ws_source, tz, tz_source, prefs)
