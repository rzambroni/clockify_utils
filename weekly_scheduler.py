#!/usr/bin/env python3
"""
Weekly Scheduler for Clockify Time Entries

Main script to automate creating weekly time entries in Clockify.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

from clockify_client import ClockifyClient
from description_generator import DescriptionGenerator


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Resolve environment variables in config
    if config.get("api_key", "").startswith("${"):
        env_var = config["api_key"][2:-1]  # Extract VAR from ${VAR}
        config["api_key"] = os.environ.get(env_var, "")
    
    return config


def get_week_dates(start_date: datetime, end_date: datetime) -> list[datetime]:
    """Get business days (Mon-Fri) within the date range."""
    dates = []
    current = start_date
    while current <= end_date:
        # Only include weekdays (0=Monday, 4=Friday)
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def calculate_time_slots(
    date: datetime,
    schedule: list[dict],
    start_hour: int = 9
) -> list[dict]:
    """
    Calculate time slots for a single day based on the schedule.
    
    Args:
        date: The date to create entries for
        schedule: List of project configurations
        start_hour: Hour to start the workday (24h format)
        
    Returns:
        List of dicts with start, end, project_id, and description
    """
    slots = []
    current_time = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    
    for project in schedule:
        duration_minutes = project.get("daily_minutes", 60)
        end_time = current_time + timedelta(minutes=duration_minutes)
        
        slots.append({
            "start": current_time,
            "end": end_time,
            "project_id": project["project_id"],
            "project_name": project.get("name", "Unknown"),
            "templates": project.get("description_templates", [])
        })
        
        current_time = end_time
    
    return slots


def main():
    parser = argparse.ArgumentParser(
        description="Create weekly time entries in Clockify"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--start-date", "-s",
        type=str,
        help="Start date in YYYY-MM-DD format (default: this Monday)"
    )
    parser.add_argument(
        "--end-date", "-e",
        type=str,
        help="End date in YYYY-MM-DD format (default: this Friday)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Preview what would be created without making API calls"
    )
    parser.add_argument(
        "--analyze-history",
        action="store_true",
        help="Analyze past entries to enhance descriptions"
    )
    
    args = parser.parse_args()
    
    # Load environment variables from .env if present
    load_dotenv()
    
    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        print("   Run with --help for usage information")
        sys.exit(1)
    
    config = load_config(str(config_path))
    
    # Validate required config
    if not config.get("api_key"):
        print("❌ API key not found. Set CLOCKIFY_API_KEY environment variable")
        print("   or add api_key to your config file")
        sys.exit(1)
    
    if not config.get("workspace_id"):
        print("❌ Workspace ID not found in config file")
        sys.exit(1)
    
    # Calculate date range
    today = datetime.now()
    
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    else:
        # Default to this week's Monday
        start_date = today - timedelta(days=today.weekday())
    
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        # Default to Friday of the same week
        end_date = start_date + timedelta(days=4)
    
    print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print()
    
    # Initialize client
    client = ClockifyClient(
        api_key=config["api_key"],
        workspace_id=config["workspace_id"]
    )
    
    # Get existing entries for duplicate detection
    print("🔍 Checking for existing entries...")
    existing = client.get_existing_entries_by_project_and_date(
        start_date.replace(hour=0, minute=0, second=0),
        end_date.replace(hour=23, minute=59, second=59)
    )
    
    # Optionally analyze history for better descriptions
    history_entries = []
    if args.analyze_history:
        print("📊 Analyzing entry history for description patterns...")
        history_start = start_date - timedelta(days=60)
        history_entries = client.get_time_entries(history_start, start_date)
    
    # Get the schedule from config
    schedule = config.get("schedule", [])
    start_hour = config.get("day_start_hour", 9)
    
    # Process each day
    dates = get_week_dates(start_date, end_date)
    entries_created = 0
    entries_skipped = 0
    
    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        day_name = date.strftime("%A")
        print(f"\n📆 {day_name}, {date_str}")
        print("-" * 40)
        
        slots = calculate_time_slots(date, schedule, start_hour)
        
        for slot in slots:
            project_id = slot["project_id"]
            project_name = slot["project_name"]
            
            # Check for existing entry
            project_dates = existing.get(project_id, set())
            if date_str in project_dates:
                print(f"  ⏭️  {project_name}: already has entry, skipping")
                entries_skipped += 1
                continue
            
            # Generate description
            if args.analyze_history and history_entries:
                generator = DescriptionGenerator.from_history(history_entries, project_id)
                if slot["templates"]:
                    generator.add_templates(slot["templates"])
            else:
                generator = DescriptionGenerator(templates=slot["templates"])
            
            description = generator.generate()
            
            time_range = f"{slot['start'].strftime('%H:%M')} - {slot['end'].strftime('%H:%M')}"
            
            if args.dry_run:
                print(f"  📝 {project_name} ({time_range})")
                print(f"      \"{description}\"")
            else:
                try:
                    client.create_time_entry(
                        start=slot["start"],
                        end=slot["end"],
                        project_id=project_id,
                        description=description
                    )
                    print(f"  ✅ {project_name} ({time_range})")
                    print(f"      \"{description}\"")
                    entries_created += 1
                except Exception as e:
                    print(f"  ❌ {project_name}: Failed - {e}")
    
    # Summary
    print()
    print("=" * 40)
    if args.dry_run:
        print(f"🔎 DRY RUN COMPLETE")
        print(f"   Would create: {len(dates) * len(schedule) - entries_skipped} entries")
        print(f"   Would skip: {entries_skipped} entries (already exist)")
    else:
        print(f"✨ COMPLETE")
        print(f"   Created: {entries_created} entries")
        print(f"   Skipped: {entries_skipped} entries (already existed)")


if __name__ == "__main__":
    main()
