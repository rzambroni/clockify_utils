# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 1.0.0 - 2026-11-25

### Added

- `clockify_utils` package with shared resolution of API key, workspace and timezone.
- `clockify` CLI with `config`, `whoami`, `workspaces`, `projects`, `users`, `entries`, `log`, `week`, `report` and `gaps` commands.
- `--json` output on read commands, for use from other projects, bots and scripts.
- `bin/clockify` launcher and `pyproject.toml` for `pip install -e .`.
- Opt-in `local_time` option for the weekly scheduler.
- Offline unit tests, including payload parity with the original client.

### Changed

- API errors include the Clockify response body.
- `--json` commands emit a JSON error object for input errors too.
- The prefs file is created with `0600` permissions from the start.
- `weekly_scheduler.py`, `clockify_client.py` and `description_generator.py` are now compatibility shims with unchanged behavior.

### Fixed

- Project listing truncated at 50 items; API pagination is now followed.
- System timezone fallback uses the DST-aware IANA zone instead of a fixed offset.
- `bin/clockify` uses `python3` from PATH, like the menu does.
- `config` and `config init` ignoring the `--workspace` and `--api-key` flags.
- `log` ignoring `--to` without `--from`, crashing on ranges with no weekdays, and losing already-created entries when a later day fails.
- `gaps` reporting no gaps when `--all` and `--user` match no active member.
- `Retry-After` handling when the header is not a number.
