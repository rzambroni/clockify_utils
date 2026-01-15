# Clockify Weekly Scheduler

Automate your weekly Clockify time entries with configurable projects, durations, and description variations.

## Quick Start

1. **Install dependencies:**
   ```bash
   cd /Users/renzozambroni/Projects/clockify_utils
   pip install -r requirements.txt
   ```

2. **Set up your API key:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Clockify API key
   ```

3. **Get your project IDs:**
   ```bash
   python fetch_projects.py
   ```

4. **Configure your schedule:**
   Edit `config.yaml` with your workspace ID and project IDs.

5. **Run a dry-run to preview:**
   ```bash
   python weekly_scheduler.py --dry-run --start-date 2026-01-12 --end-date 2026-01-15
   ```

6. **Create the entries:**
   ```bash
   python weekly_scheduler.py --start-date 2026-01-12 --end-date 2026-01-15
   ```

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
