# Clockify Weekly Scheduler

Automate your weekly Clockify time entries with configurable projects, durations, and description variations.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your environment:**
   ```bash
   cp .env.example .env
   cp config.example.yaml config.yaml
   ```

3. **Configure your API key:**
   Edit `.env` and add your Clockify API key (find it at [Clockify Profile Settings](https://app.clockify.me/user/settings)).

4. **Get your workspace and project IDs:**
   ```bash
   python fetch_projects.py
   ```

5. **Configure your schedule:**
   Edit `config.yaml` with your workspace ID, project IDs, and desired daily durations.

6. **Run a dry-run to preview:**
   ```bash
   python weekly_scheduler.py --dry-run --start-date 2026-01-12 --end-date 2026-01-15
   ```

7. **Create the entries:**
   ```bash
   python weekly_scheduler.py --start-date 2026-01-12 --end-date 2026-01-15
   ```

## macOS Quick Access

Double-click `Clockify Menu.command` for an interactive menu to run common operations.

## CLI Options

| Option | Description |
|--------|-------------|
| `--config, -c` | Path to config file (default: config.yaml) |
| `--start-date, -s` | Start date YYYY-MM-DD (default: this Monday) |
| `--end-date, -e` | End date YYYY-MM-DD (default: this Friday) |
| `--dry-run, -d` | Preview without creating entries |
| `--analyze-history` | Use past entries to enhance descriptions |

## Features

- ✅ **Duplicate detection** - Won't create entries if one already exists for that project/day
- 🎲 **Description variations** - Generates varied descriptions from templates
- 📅 **Flexible dates** - Specify any date range
- 🔍 **Dry-run mode** - Preview before committing
- 📊 **History analysis** - Learn from past entries for better descriptions
