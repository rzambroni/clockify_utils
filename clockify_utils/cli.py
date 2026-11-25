"""
`clockify` command line tool.

Every read command accepts --json so scripts, bots and Claude skills can use
the output directly. Write commands (log, week) support --dry-run.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, time, timedelta
from typing import Optional

from . import __version__
from .client import ClockifyClient, parse_api_time, parse_duration
from .dates import RANGE_PRESETS, days_between, parse_date, resolve_range
from .settings import SettingsError, get_settings, load_prefs, prefs_path, save_prefs


# ── helpers ───────────────────────────────────────────────────────────────

def _client(args) -> tuple:
    s = get_settings(getattr(args, "api_key", None), getattr(args, "workspace", None))
    return ClockifyClient(s.api_key, s.workspace_id), s


def _emit_json(data) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def _hours(seconds: float) -> str:
    return f"{seconds / 3600:.2f}"


def _hm(seconds: float) -> str:
    m = int(round(seconds / 60))
    return f"{m // 60}h{m % 60:02d}"


def _table(rows: list, headers: list) -> None:
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    print("  ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))


def _local_bounds(start, end, tz) -> tuple:
    return (datetime.combine(start, time.min, tzinfo=tz), datetime.combine(end, time(23, 59, 59), tzinfo=tz))


def _add_range_args(p: argparse.ArgumentParser, default: str) -> None:
    p.add_argument("--range", "-r", choices=RANGE_PRESETS, help=f"preset date range (default: {default})")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="start date")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="end date (inclusive)")


def _normalize_entry(e: dict, tz, project_names: Optional[dict] = None, user_name: Optional[str] = None) -> dict:
    """Same shape for /time-entries and Reports API entries."""
    ti = e.get("timeInterval") or {}
    start = parse_api_time(ti["start"]).astimezone(tz) if ti.get("start") else None
    end = parse_api_time(ti["end"]).astimezone(tz) if ti.get("end") else None
    seconds = parse_duration(ti.get("duration"))
    if not seconds and start and end:
        seconds = int((end - start).total_seconds())
    pid = e.get("projectId")
    return {
        "id": e.get("id") or e.get("_id"),
        "date": start.strftime("%Y-%m-%d") if start else None,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "hours": round(seconds / 3600, 2),
        "seconds": seconds,
        "project_id": pid,
        "project": e.get("projectName") or (project_names or {}).get(pid, ""),
        "user_id": e.get("userId"),
        "user": e.get("userName") or user_name or "",
        "description": e.get("description", ""),
        "billable": e.get("billable"),
    }


# ── commands ──────────────────────────────────────────────────────────────

def cmd_config_init(args) -> int:
    """Copy the currently resolved key/workspace into the shared prefs file."""
    s = get_settings(require_key=True)
    prefs = load_prefs()
    if prefs.get("api_key") and prefs["api_key"] != s.api_key and not args.force:
        print(f"❌ {prefs_path()} already has a different api_key. Use --force to overwrite it.", file=sys.stderr)
        return 1
    ClockifyClient(s.api_key, s.workspace_id).get_user()  # validate before saving
    path = save_prefs({"api_key": s.api_key, "workspace_id": s.workspace_id})
    print(f"✅ Saved api_key ({s.masked_key()}, from {s.api_key_source}) and workspace_id to {path} (mode 600).")
    print("   Any project, the clockify-tracker skill, and pip-installed copies will now find them.")
    return 0


def cmd_config(args) -> int:
    if getattr(args, "action", None) == "init":
        return cmd_config_init(args)
    s = get_settings(require_key=False)
    info = {
        "api_key": s.masked_key(),
        "api_key_source": s.api_key_source or None,
        "workspace_id": s.workspace_id,
        "workspace_source": s.workspace_source,
        "timezone": str(s.tz),
        "timezone_source": s.tz_source,
        "prefs_file": str(prefs_path()),
    }
    if args.json:
        _emit_json(info)
    else:
        for k, v in info.items():
            print(f"{k:17} {v if v is not None else '(not set)'}")
    return 0


def cmd_whoami(args) -> int:
    client, _ = _client(args)
    u = client.get_user()
    if args.json:
        _emit_json({k: u.get(k) for k in ("id", "name", "email", "activeWorkspace", "defaultWorkspace")})
    else:
        print(f"{u.get('name')} <{u.get('email')}>  id={u.get('id')}")
    return 0


def cmd_workspaces(args) -> int:
    client, _ = _client(args)
    ws = client.get_workspaces()
    if args.json:
        _emit_json([{"id": w["id"], "name": w["name"]} for w in ws])
    else:
        _table([(w["name"], w["id"]) for w in ws], ["NAME", "ID"])
    return 0


def cmd_projects(args) -> int:
    client, _ = _client(args)
    projects = client.get_projects(archived=args.archived)
    if args.search:
        q = args.search.lower()
        projects = [p for p in projects if q in p.get("name", "").lower() or q in (p.get("clientName") or "").lower()]
    projects.sort(key=lambda p: p.get("name", "").lower())
    if args.json:
        _emit_json([{"id": p["id"], "name": p.get("name"), "client": p.get("clientName") or None,
                     "billable": p.get("billable"), "archived": p.get("archived")} for p in projects])
    else:
        _table([(p.get("name"), p.get("clientName") or "", p["id"]) for p in projects], ["NAME", "CLIENT", "ID"])
        print(f"\n{len(projects)} projects")
    return 0


def cmd_users(args) -> int:
    client, _ = _client(args)
    users = client.get_users(status="ALL" if args.all else "ACTIVE")
    if args.search:
        q = args.search.lower()
        users = [u for u in users if q in u.get("name", "").lower() or q in u.get("email", "").lower()]
    users.sort(key=lambda u: u.get("name", "").lower())
    if args.json:
        _emit_json([{"id": u["id"], "name": u.get("name"), "email": u.get("email"), "status": u.get("status")} for u in users])
    else:
        _table([(u.get("name"), u.get("email"), u.get("status"), u["id"]) for u in users], ["NAME", "EMAIL", "STATUS", "ID"])
        print(f"\n{len(users)} users")
    return 0


def cmd_entries(args) -> int:
    client, s = _client(args)
    start, end = resolve_range(args.range, args.date_from, args.date_to, default="this-week")
    lo, hi = _local_bounds(start, end, s.tz)
    user = client.find_user(args.user) if args.user else client.get_user()
    project = client.find_project(args.project, include_archived=True) if args.project else None
    raw = client.get_time_entries(lo, hi, project_id=project["id"] if project else None, user_id=user["id"])
    names = client.project_names()
    entries = sorted((_normalize_entry(e, s.tz, names, user.get("name")) for e in raw), key=lambda e: e["start"] or "")
    if args.json:
        _emit_json(entries)
        return 0
    print(f"{user.get('name')} · {start} → {end} · {len(entries)} entries\n")
    _table([(e["date"], e["start"][11:16] if e["start"] else "", e["end"][11:16] if e["end"] else "…",
             _hm(e["seconds"]), e["project"], (e["description"] or "")[:60]) for e in entries],
           ["DATE", "START", "END", "TIME", "PROJECT", "DESCRIPTION"])
    print(f"\nTotal: {_hm(sum(e['seconds'] for e in entries))}")
    return 0


def _parse_hhmm(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise ValueError(f"Invalid time '{value}', expected HH:MM")


def cmd_log(args) -> int:
    client, s = _client(args)
    project = client.find_project(args.project)
    t_start = _parse_hhmm(args.start)
    if args.end:
        t_end = _parse_hhmm(args.end)
    elif args.duration:
        t_end = None
    else:
        raise ValueError("Pass --end HH:MM or --duration (e.g. 1.5 hours)")
    if args.date:
        days = [parse_date(d) for d in args.date]
    elif args.range or args.date_from:
        a, b = resolve_range(args.range, args.date_from, args.date_to)
        days = days_between(a, b, weekdays_only=not args.include_weekends)
    else:
        days = [datetime.now(s.tz).date()]

    existing: dict = defaultdict(list)
    if not args.allow_duplicates:
        lo, hi = _local_bounds(min(days), max(days), s.tz)
        for e in client.get_time_entries(lo, hi, project_id=project["id"]):
            n = _normalize_entry(e, s.tz)
            existing[n["date"]].append(n)

    created, skipped, out = 0, 0, []
    for day in days:
        start = datetime.combine(day, t_start, tzinfo=s.tz)
        end = datetime.combine(day, t_end, tzinfo=s.tz) if t_end else start + timedelta(hours=args.duration)
        if end <= start:
            raise ValueError("End time must be after start time")
        label = f"{day} {start:%H:%M}-{end:%H:%M} {project['name']}"
        if existing.get(str(day)):
            skipped += 1
            out.append({"date": str(day), "status": "skipped", "reason": "project already has an entry that day"})
            if not args.json:
                print(f"⏭️  {label}: already has an entry (use --allow-duplicates to add anyway)")
            continue
        if args.dry_run:
            payload = client.build_time_entry_payload(start, end, project["id"], args.description, args.billable)
            out.append({"date": str(day), "status": "dry-run", "payload": payload})
            if not args.json:
                print(f"📝 {label}  \"{args.description}\"  (UTC {payload['start']} → {payload['end']})")
            continue
        entry = client.create_time_entry(start, end, project["id"], args.description, billable=args.billable)
        created += 1
        out.append({"date": str(day), "status": "created", "id": entry.get("id")})
        if not args.json:
            print(f"✅ {label}  \"{args.description}\"")
    if args.json:
        _emit_json(out)
    else:
        verb = "Would create" if args.dry_run else "Created"
        print(f"\n{verb}: {len(days) - skipped if args.dry_run else created} · Skipped: {skipped}")
    return 0


def cmd_week(args) -> int:
    from . import scheduler

    if args.range:
        a, b = resolve_range(args.range, None, None)
        args.start_date, args.end_date = str(a), str(b)
    if args.config is None:
        args.config = scheduler.default_config_path()
    return scheduler.run(args)


def _report_entries(client, s, args) -> tuple:
    start, end = resolve_range(args.range, args.date_from, args.date_to, default="this-week")
    lo, hi = _local_bounds(start, end, s.tz)
    user_ids = [client.find_user(u)["id"] for u in (args.user or [])] or None
    project_ids = [client.find_project(p, include_archived=True)["id"] for p in (args.project or [])] or None
    raw = client.detailed_report(lo, hi, user_ids=user_ids, project_ids=project_ids)
    return start, end, [_normalize_entry(e, s.tz) for e in raw]


def cmd_report(args) -> int:
    client, s = _client(args)
    start, end, entries = _report_entries(client, s, args)
    keys = [k.strip() for k in args.by.split(",") if k.strip()]
    valid = {"user", "project", "date", "description"}
    bad = [k for k in keys if k not in valid]
    if bad:
        raise ValueError(f"--by accepts {', '.join(sorted(valid))}")
    totals: dict = defaultdict(lambda: [0, 0])
    for e in entries:
        k = tuple(e[x] or "(none)" for x in keys)
        totals[k][0] += e["seconds"]
        totals[k][1] += 1
    rows = sorted(totals.items(), key=lambda kv: (-kv[1][0],) if args.sort == "hours" else kv[0])
    if args.json:
        _emit_json({"from": str(start), "to": str(end), "group_by": keys,
                    "total_hours": round(sum(e["seconds"] for e in entries) / 3600, 2),
                    "rows": [dict(zip(keys, k), hours=round(v[0] / 3600, 2), entries=v[1]) for k, v in rows]})
        return 0
    print(f"Report {start} → {end} · grouped by {', '.join(keys)}\n")
    _table([(*k, _hours(v[0]), v[1]) for k, v in rows], [*(x.upper() for x in keys), "HOURS", "ENTRIES"])
    print(f"\nTotal: {_hours(sum(e['seconds'] for e in entries))} h in {len(entries)} entries")
    return 0


def cmd_gaps(args) -> int:
    client, s = _client(args)
    start, end = resolve_range(args.range, args.date_from, args.date_to, default="this-week-until-today")
    days = [d for d in days_between(start, end, weekdays_only=not args.include_weekends)]
    if args.all:
        users = client.get_users(status="ACTIVE")
        if args.user:
            wanted = {client.find_user(u)["id"] for u in args.user}
            users = [u for u in users if u["id"] in wanted]
    elif args.user:
        users = [client.find_user(u) for u in args.user]
    else:
        users = [client.get_user()]
    lo, hi = _local_bounds(start, end, s.tz)
    logged: dict = defaultdict(float)
    if args.all or len(users) > 1:
        for e in client.detailed_report(lo, hi, user_ids=[u["id"] for u in users]):
            n = _normalize_entry(e, s.tz)
            logged[(n["user_id"], n["date"])] += n["seconds"]
    else:
        for e in client.get_time_entries(lo, hi, user_id=users[0]["id"]):
            n = _normalize_entry(e, s.tz)
            logged[(users[0]["id"], n["date"])] += n["seconds"]
    target = args.hours * 3600
    gaps = []
    for u in sorted(users, key=lambda u: u.get("name", "").lower()):
        for d in days:
            have = logged.get((u["id"], str(d)), 0)
            if have + 60 < target:  # 1 minute tolerance
                gaps.append({"user": u.get("name"), "user_id": u["id"], "date": str(d),
                             "logged_hours": round(have / 3600, 2), "missing_hours": round((target - have) / 3600, 2)})
    if args.json:
        _emit_json(gaps)
        return 0
    if not gaps:
        print(f"✅ No gaps: every day {start} → {end} has at least {args.hours:g}h logged.")
        return 0
    print(f"Days under {args.hours:g}h · {start} → {end}\n")
    _table([(g["user"], g["date"], datetime.strptime(g["date"], "%Y-%m-%d").strftime("%a"),
             f"{g['logged_hours']:.2f}", f"{g['missing_hours']:.2f}") for g in gaps],
           ["USER", "DATE", "DAY", "LOGGED", "MISSING"])
    return 0


# ── parser ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("--workspace", "-w", metavar="ID", help="workspace ID (overrides settings)")
    common.add_argument("--api-key", help=argparse.SUPPRESS)

    p = argparse.ArgumentParser(
        prog="clockify",
        description="Shared Clockify utilities: log time, weekly auto-fill, entries, reports and gaps.",
        epilog="Names can be partial and case-insensitive (projects, users); IDs also work. "
               "Run `clockify config` to see where the API key and workspace come from.",
    )
    p.add_argument("--version", action="version", version=f"clockify-utils {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    sp = sub.add_parser("config", parents=[common], help="show resolved settings; `config init` saves them to the shared prefs file",
                        description="`clockify config` shows where the key/workspace/timezone come from. "
                                    "`clockify config init` validates the current key and saves it to "
                                    "${CLOCKIFY_PREFS_PATH:-~/.clockify-prefs.json} so every project finds it.")
    sp.add_argument("action", nargs="?", choices=("show", "init"), default="show")
    sp.add_argument("--force", action="store_true", help="with init: overwrite a different saved key")
    sp.set_defaults(func=cmd_config)

    sp = sub.add_parser("whoami", parents=[common], help="current user")
    sp.set_defaults(func=cmd_whoami)

    sp = sub.add_parser("workspaces", parents=[common], help="list workspaces")
    sp.set_defaults(func=cmd_workspaces)

    sp = sub.add_parser("projects", parents=[common], help="list projects (replaces fetch_projects.py)")
    sp.add_argument("--search", "-q", help="filter by project or client name")
    sp.add_argument("--archived", action="store_true", help="list archived projects instead")
    sp.set_defaults(func=cmd_projects)

    sp = sub.add_parser("users", parents=[common], help="list workspace members")
    sp.add_argument("--search", "-q", help="filter by name or email")
    sp.add_argument("--all", action="store_true", help="include inactive/pending users")
    sp.set_defaults(func=cmd_users)

    sp = sub.add_parser("entries", parents=[common], help="time entries of a user (default: you)")
    sp.add_argument("--user", "-u", help="name, email, ID or 'me' (other users need admin rights)")
    sp.add_argument("--project", "-p", help="filter by project name or ID")
    _add_range_args(sp, "this-week")
    sp.set_defaults(func=cmd_entries)

    sp = sub.add_parser("log", parents=[common], help="create time entries (local time)",
                        description="Create one entry per day. Times are your local time "
                                    "(see `clockify config`). Skips days where the project already has an entry.")
    sp.add_argument("description")
    sp.add_argument("--project", "-p", required=True, help="project name or ID")
    sp.add_argument("--start", "-s", default="09:00", help="HH:MM local (default 09:00)")
    sp.add_argument("--end", "-e", help="HH:MM local")
    sp.add_argument("--duration", type=float, metavar="HOURS", help="instead of --end, e.g. 1.5")
    sp.add_argument("--date", "-d", action="append", metavar="YYYY-MM-DD", help="day to log (repeatable; default today)")
    _add_range_args(sp, "today")
    sp.add_argument("--include-weekends", action="store_true", help="with --range/--from, include Sat/Sun")
    sp.add_argument("--no-billable", dest="billable", action="store_false", help="mark as non-billable")
    sp.add_argument("--allow-duplicates", action="store_true", help="create even if the project already has an entry that day")
    sp.add_argument("--dry-run", action="store_true", help="show what would be created")
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("week", help="weekly auto-fill from config.yaml (same as weekly_scheduler.py)",
                        description="Same behavior and flags as weekly_scheduler.py, plus --range. "
                                    "Config: --config > $CLOCKIFY_CONFIG > ./config.yaml > clockify_utils repo config.yaml.")
    from .scheduler import build_parser as week_parser
    week_parser(parser=sp)
    sp.set_defaults(config=None)
    sp.add_argument("--range", "-r", choices=("this-week", "this-week-until-today", "last-week", "this-month", "last-month"),
                    help="preset range instead of --start-date/--end-date")
    sp.set_defaults(func=cmd_week)

    sp = sub.add_parser("report", parents=[common], help="hours summary for the whole workspace (Reports API)")
    _add_range_args(sp, "this-week")
    sp.add_argument("--by", default="user,project", help="group by user, project, date, description (default user,project)")
    sp.add_argument("--user", "-u", action="append", help="limit to user (repeatable)")
    sp.add_argument("--project", "-p", action="append", help="limit to project (repeatable)")
    sp.add_argument("--sort", choices=("hours", "name"), default="hours")
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("gaps", parents=[common], help="weekdays with fewer hours than expected")
    _add_range_args(sp, "this-week-until-today")
    sp.add_argument("--hours", type=float, default=8, help="expected hours per day (default 8)")
    sp.add_argument("--user", "-u", action="append", help="user to check (repeatable; default: you)")
    sp.add_argument("--all", action="store_true", help="check every active workspace member")
    sp.add_argument("--include-weekends", action="store_true")
    sp.set_defaults(func=cmd_gaps)

    return p


def main(argv: Optional[list] = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        code = args.func(args)
    except (SettingsError, LookupError, ValueError) as e:
        print(f"❌ {e}", file=sys.stderr)
        code = 2
    except Exception as e:  # API errors etc.
        if getattr(args, "json", False):
            _emit_json({"error": str(e)})
        else:
            print(f"❌ {e}", file=sys.stderr)
        code = 1
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
