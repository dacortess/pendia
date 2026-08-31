"""Business logic for the dashboard endpoint."""
from __future__ import annotations

import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.dashboard import repository as repo
from app.obligations.service import _ensure_periods_generated_for_group

BOGOTA = ZoneInfo("America/Bogota")

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def get_dashboard(
    db: Session, group_id: int, month_str: str | None
) -> dict:
    """Return dashboard data for the given group and month.

    Args:
        db: Database session.
        group_id: Target group.
        month_str: Optional 'YYYY-MM' string. Defaults to current month in Bogotá.
    """
    # --- Resolve month ---
    if month_str is None:
        today_bog = date.today()
        # Use actual today in Bogota
        from datetime import datetime as _dt
        today_bog = _dt.now(BOGOTA).date()
        month_date = date(today_bog.year, today_bog.month, 1)
    else:
        if not _MONTH_RE.match(month_str):
            raise ValueError("Formato de mes inválido. Use YYYY-MM.")
        year_str, mon_str = month_str.split("-")
        year, month = int(year_str), int(mon_str)
        if month < 1 or month > 12:
            raise ValueError("Formato de mes inválido. Use YYYY-MM.")
        month_date = date(year, month, 1)

    # --- Ensure periods exist ---
    _ensure_periods_generated_for_group(db, group_id)
    db.flush()

    # --- Totals ---
    totals_raw = repo.get_totals_by_currency(db, group_id, month_date)
    paid_raw = repo.get_paid_by_currency(db, group_id, month_date)

    paid_map = {r["currency"]: r["paid_cents"] for r in paid_raw}

    totals = []
    for t in totals_raw:
        paid = paid_map.get(t["currency"], 0)
        totals.append({
            "currency": t["currency"],
            "total_cents": t["total_cents"],
            "paid_cents": paid,
            "pending_cents": t["total_cents"] - paid,
        })

    # --- Upcoming periods (next 7 days from today in Bogota) ---
    from datetime import datetime as _dt
    today = _dt.now(BOGOTA).date()
    week_end = today + timedelta(days=6)

    upcoming = repo.get_upcoming_periods(db, group_id, today, week_end)

    return {
        "month": month_date.strftime("%Y-%m"),
        "totals": totals,
        "vencen_esta_semana": upcoming,
    }
