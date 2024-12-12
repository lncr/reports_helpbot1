from calendar import monthrange
from datetime import UTC, datetime, timedelta
from typing import Annotated
from dateutil.utils import today
from pydantic import Field


def get_start_and_end_dates_for_request(
    month: Annotated[int, Field(ge=1, le=12)],
    year: int | None = None,
) -> tuple[datetime, datetime]:
    """
    return first and last days for the month.
    if year is not provided, it will return first and last days for the month of the current year
    """
    now = today(UTC)
    if not year:
        year = now.year

    start_date = datetime(year, month, 1, tzinfo=UTC)
    if month == now.month and year == now.year:
        end_date = now
    else:
        end_date = (
            datetime(year, month, monthrange(year, month)[1], tzinfo=UTC) + timedelta(days=1) - timedelta(seconds=1)
        )

    return start_date, end_date


def generate_whole_report(
    year: int | None = None,
    month: int = 1,
):
    """
    Generate report for all given wallets for specified time period:
     1. balances
     2. transfers
     3. prices
     4. TVL & APY
    """
    now = today(UTC)
    year = year or now.year
    balance_target_date = None
    if year == now.year and month > now.month:
        month = now.month


    start_date, end_date = get_start_and_end_dates_for_request(month, year)
    if month != now.month or year != now.year:
        balance_target_date = end_date
    
    return month, year
