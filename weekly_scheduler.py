#!/usr/bin/env python3
"""
Weekly Scheduler for Clockify Time Entries

Same flags and behavior as always (the menu uses this file). The logic now
lives in clockify_utils/scheduler.py and is also available as `clockify week`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clockify_utils.scheduler import (  # noqa: E402,F401
    calculate_time_slots,
    get_week_dates,
    load_config,
    main,
)

if __name__ == "__main__":
    main()
