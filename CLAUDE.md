# CLAUDE.md

Shared Clockify tooling: one API key, one Python client (`clockify_utils`) and a
`clockify` CLI to log time, auto-fill the week, list entries, build reports and
find days without hours. Python >= 3.9, dependencies in `pyproject.toml`
(mirrored in `requirements.txt`).

## Layout

- `clockify_utils/` - the package
  - `cli.py` - `clockify` CLI (argparse subcommands: config, whoami, workspaces, projects, users, entries, log, week, report, gaps)
  - `client.py` - `ClockifyClient` and API errors
  - `settings.py` - resolution of API key, workspace and timezone (env, `.env`, prefs file, `config.yaml`)
  - `scheduler.py` - weekly auto-fill from `config.yaml` (`clockify week`)
  - `descriptions.py`, `dates.py` - description templates and date ranges
  - `__main__.py` - enables `python -m clockify_utils`
- `bin/clockify` - launcher that runs the CLI without a pip install
- `tests/` - offline unit tests (no API calls)
- `weekly_scheduler.py`, `clockify_client.py`, `description_generator.py` - legacy entry points, now shims
- `fetch_projects.py`, `Clockify Menu.command` - legacy helper and macOS menu
- `config.example.yaml`, `.env.example` - templates for the gitignored `config.yaml` and `.env`

## Commands

```bash
pip install -e .                      # or: pip install -r requirements.txt
python -m clockify_utils --help       # run the CLI from the repo
bin/clockify config                   # same CLI through the launcher
python -m unittest discover tests     # run the tests
```

## Rules

- Legacy scripts (`weekly_scheduler.py`, `clockify_client.py`,
  `description_generator.py`) are compatibility shims. Put new logic in
  `clockify_utils/` and keep the shims' imports and behavior unchanged.
- Never commit `.env`, `config.yaml` or real API keys.
- Commits follow Conventional Commits with a scope, e.g.
  `feat(cli): ...`, `fix(cli): ...`, `docs(readme): ...`.
- Run the tests before opening a PR. Changes go through PRs, not direct pushes to `main`.
