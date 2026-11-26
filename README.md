# Clockify Utils

Shared Clockify tooling for all projects: one API key, one Python client, and a
`clockify` CLI to log time, auto-fill the week, list entries, build reports and
find days without hours.

Everything that worked before still works the same way: `Clockify Menu.app`,
`Clockify Menu.command`, `weekly_scheduler.py`, `fetch_projects.py` and
`from clockify_client import ClockifyClient`.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   Or install the package in editable mode, which also puts a `clockify`
   command on your PATH:
   ```bash
   pip install -e .
   ```
   `requirements.txt` mirrors the dependencies in `pyproject.toml`; keep both in
   sync when adding one.

2. **Set up your environment:**
   ```bash
   cp .env.example .env
   cp config.example.yaml config.yaml
   ```

3. **Configure your API key:**
   Edit `.env` and add your Clockify API key (find it at [Clockify Profile Settings](https://app.clockify.me/user/settings)).

4. **Put the `clockify` command on your PATH** (no pip install needed):
   ```bash
   ln -s "$PWD/bin/clockify" ~/.local/bin/clockify
   clockify config          # shows where the key/workspace/timezone come from
   ```
   The launcher runs `python3` from your PATH. To use another interpreter (for
   example a virtualenv), set `CLOCKIFY_PYTHON`:
   ```bash
   export CLOCKIFY_PYTHON="$HOME/.venvs/clockify/bin/python"
   ```

5. **Get your workspace and project IDs:**
   ```bash
   clockify workspaces
   clockify projects -q "acme"            # or: python fetch_projects.py
   ```

6. **Configure your weekly schedule** in `config.yaml` and preview it:
   ```bash
   clockify week --range this-week --dry-run
   ```

## The `clockify` CLI

Projects and users can be given by ID or by partial, case-insensitive name.
Every read command accepts `--json`, so scripts, bots and Claude skills can use
the output directly.

| Command | What it does |
|---------|--------------|
| `clockify config [init]` | Show the resolved settings (key masked). `init` saves the key to the shared prefs file |
| `clockify whoami` / `workspaces` | Current user / available workspaces |
| `clockify projects [-q text] [--archived]` | List projects (all pages, not just the first 50) |
| `clockify users [-q text] [--all]` | Workspace members |
| `clockify entries [-u user] [-p project] [-r range]` | Time entries of a user (default: you) in local time |
| `clockify log "desc" -p project -s 09:00 -e 11:00 [-d date…\|-r range] [--dry-run]` | Create entries in **local time**. Skips days where the project already has an entry |
| `clockify week [-r range \| -s/-e] [--dry-run] [--analyze-history]` | Weekly auto-fill from `config.yaml` (same as `weekly_scheduler.py`) |
| `clockify report [-r range] [--by user,project,date,description] [-u …] [-p …]` | Hours summary for the whole workspace (Reports API) |
| `clockify gaps [-r range] [--hours 8] [-u user… \| --all]` | Weekdays with fewer hours than expected |

Ranges (`-r`): `today`, `yesterday`, `this-week`, `this-week-until-today`,
`last-week`, `this-month`, `last-month`. Use `--from YYYY-MM-DD --to YYYY-MM-DD`
for custom ranges.

Examples:
```bash
clockify log "sprint planning" -p "acme mobile" -s 10:00 --duration 1.5 --dry-run
clockify entries -u "jane" --from 2026-05-04 --to 2026-05-08 --json
clockify report -r last-month -p "acme web" --by user
clockify gaps -r last-week --all
```

## API key and settings (shared by every project)

The key is resolved in this order, and the first match wins:

1. `CLOCKIFY_API_KEY`, from the environment or a `.env` file. The current directory's `.env` is checked first, then this repo's `.env`.
2. `CLOCKIFY_API_KEY_FILE`, a file that contains only the key.
3. `api_key` in `${CLOCKIFY_PREFS_PATH:-~/.clockify-prefs.json}`. The `clockify-tracker` skill reads the same file.

The workspace comes from `CLOCKIFY_WORKSPACE_ID`, then from `workspace_id` in the prefs file, then from this repo's `config.yaml`, and finally from the only workspace the key can see.

The timezone used by `log`, `entries`, `report` and `gaps` comes from `CLOCKIFY_TZ` (an IANA name), then from the `timezone.offset` value in the prefs file, then from `CLOCKIFY_TZ_OFFSET`, and finally from the system timezone.

Run `clockify config init` once. It validates the current key and saves it to the prefs file with mode 600, so every project finds the same key without copying it.

## Using it from other projects

- **Shell, bots, skills:** call `clockify … --json`.
- **Python:** `pip install -e ~/Projects/clockify_utils`. Keep the `-e`, so the package can still find this repo's `.env` and `config.yaml`. Then:
  ```python
  from clockify_utils import ClockifyClient
  client = ClockifyClient.from_env()
  client.find_project("acme web")
  client.get_time_entries(start, end, user_id=client.find_user("jane")["id"])
  client.detailed_report(start, end, project_ids=[...])   # all users
  ```

## Weekly auto-fill (`weekly_scheduler.py` / `clockify week`)

| Option | Description |
|--------|-------------|
| `--config, -c` | Path to config file (default: config.yaml) |
| `--start-date, -s` | Start date YYYY-MM-DD (default: this Monday) |
| `--end-date, -e` | End date YYYY-MM-DD (default: this Friday) |
| `--dry-run, -d` | Preview without creating entries |
| `--analyze-history` | Use past entries to enhance descriptions |
| `--range, -r` | (`clockify week` only) preset range |

> **Times are sent as UTC.** `day_start_hour: 9` creates entries at 09:00 UTC,
> which is 06:00 in Argentina. This has always been the behavior and it is kept
> as the default. Add `local_time: true` to `config.yaml` to use your local time
> instead.

### macOS Quick Access

Double-click `Clockify Menu.app` (or `Clockify Menu.command`) for an interactive
menu with the common ranges and a preview mode.

## Features

- ✅ **Duplicate detection**: no entry is created if one already exists for that project and day (`week` and `log`)
- 🎲 **Description variations**: descriptions are generated from templates
- 📅 **Flexible dates**: presets or any custom range
- 🔍 **Dry-run mode**: preview before you commit
- 📊 **History analysis**: past entries are used to improve descriptions
- 👥 **Team views**: entries of any user, workspace reports, missing-hours detection
- 🔑 **One shared key** for every project and skill

## Development

```bash
python3 -m unittest discover tests     # offline, no API calls
```

## Contributing

1. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Make your changes** and commit them.
3. **Push your branch** to GitHub:
   ```bash
   git push origin feature/your-feature-name
   ```
4. **Open a Pull Request** on GitHub for review.

> [!IMPORTANT]
> Direct pushes to the `main` branch are restricted. Please use Pull Requests for all changes.
