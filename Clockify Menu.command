#!/bin/bash
# Clockify Weekly Entry Creator - Interactive Menu
# Double-click this file to run

cd "$(dirname "$0")"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

# Colors for pretty output
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

while true; do
    # Get dates
    TODAY=$(date +%Y-%m-%d)
    THIS_MONDAY=$(date -v-$(date +%u)d -v+1d +%Y-%m-%d 2>/dev/null || date -d "last monday" +%Y-%m-%d)
    THIS_FRIDAY=$(date -j -v+fri -f "%Y-%m-%d" "$THIS_MONDAY" +%Y-%m-%d 2>/dev/null || date -d "$THIS_MONDAY + 4 days" +%Y-%m-%d)
    LAST_MONDAY=$(date -j -v-7d -f "%Y-%m-%d" "$THIS_MONDAY" +%Y-%m-%d 2>/dev/null || date -d "$THIS_MONDAY - 7 days" +%Y-%m-%d)
    LAST_FRIDAY=$(date -j -v-7d -f "%Y-%m-%d" "$THIS_FRIDAY" +%Y-%m-%d 2>/dev/null || date -d "$THIS_FRIDAY - 7 days" +%Y-%m-%d)
    MONTH_START=$(date +%Y-%m-01)
    MONTH_END=$(date -v+1m -v1d -v-1d +%Y-%m-%d 2>/dev/null || date -d "$(date +%Y-%m-01) +1 month -1 day" +%Y-%m-%d)
    MONTH_NAME=$(date +%B)

    clear
    echo -e "${BOLD}🕐 Clockify Weekly Entry Creator${NC}"
    echo "=================================="
    echo ""
    echo -e "${CYAN}Choose an option:${NC}"
    echo ""
    echo "  1) This week (Mon $THIS_MONDAY to Fri $THIS_FRIDAY)"
    echo "  2) This week until today ($THIS_MONDAY to $TODAY)"
    echo "  3) Last week ($LAST_MONDAY to $LAST_FRIDAY)"
    echo "  4) This month - $MONTH_NAME ($MONTH_START to $MONTH_END)"
    echo "  5) Custom date range"
    echo ""
    echo "  p) Preview only (dry-run)"
    echo "  q) Quit"
    echo ""
    echo -n "Enter choice [1-5, p, q]: "
    read choice

    case $choice in
        1)
            START_DATE="$THIS_MONDAY"
            END_DATE="$THIS_FRIDAY"
            DRY_RUN=""
            ;;
        2)
            START_DATE="$THIS_MONDAY"
            END_DATE="$TODAY"
            DRY_RUN=""
            ;;
        3)
            START_DATE="$LAST_MONDAY"
            END_DATE="$LAST_FRIDAY"
            DRY_RUN=""
            ;;
        4)
            START_DATE="$MONTH_START"
            END_DATE="$MONTH_END"
            DRY_RUN=""
            ;;
        5)
            echo ""
            echo -n "Enter start date (YYYY-MM-DD): "
            read START_DATE
            echo -n "Enter end date (YYYY-MM-DD): "
            read END_DATE
            DRY_RUN=""
            ;;
        p|P)
            echo ""
            echo -e "${CYAN}Preview mode - Choose date range:${NC}"
            echo "  1) This week"
            echo "  2) This week until today"
            echo "  3) Last week"
            echo "  4) This month"
            echo -n "Enter choice [1-4]: "
            read preview_choice
            case $preview_choice in
                1)
                    START_DATE="$THIS_MONDAY"
                    END_DATE="$THIS_FRIDAY"
                    ;;
                2)
                    START_DATE="$THIS_MONDAY"
                    END_DATE="$TODAY"
                    ;;
                3)
                    START_DATE="$LAST_MONDAY"
                    END_DATE="$LAST_FRIDAY"
                    ;;
                4)
                    START_DATE="$MONTH_START"
                    END_DATE="$MONTH_END"
                    ;;
                *)
                    START_DATE="$THIS_MONDAY"
                    END_DATE="$THIS_FRIDAY"
                    ;;
            esac
            DRY_RUN="--dry-run"
            ;;
        q|Q)
            echo "Bye!"
            exit 0
            ;;
        *)
            echo "Invalid choice. Returning to menu..."
            sleep 1
            continue
            ;;
    esac

    echo ""
    echo "=================================="
    if [ -n "$DRY_RUN" ]; then
        echo -e "${YELLOW}🔍 DRY RUN - Preview only${NC}"
    fi
    echo ""

    python3 weekly_scheduler.py --start-date "$START_DATE" --end-date "$END_DATE" $DRY_RUN

    echo ""
    echo "=================================="
    echo "Process completed."
    echo "Press any key to return to menu..."
    read -n 1
done

