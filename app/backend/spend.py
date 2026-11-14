"""Spending limits (SPEC §9.1): what the AI and web search cost, and when to stop paying.

Every paid call is recorded at the point of spending (ai.chat_once, search.search), only when
it isn't served from the cache. Before each paid call, Meter.check() refuses it if:
  - AI_OFF=1 on this copy (emergency stop),
  - this device has used DEVICE_ASKS_PER_HOUR paid Asks in the last hour, or
  - this service's total has reached its budget (AI_BUDGET_USD, SEARCH_BUDGET_USD).
The refusal is a LimitReached exception; ask.py turns it into a blocked layer ("by": "limit")
whose label is the notice below. Cached replays never reach check(), so they always work.
"""
import os
from datetime import datetime, timedelta

import db

UNKNOWN_DEVICE = "unknown"  # requests without X-Device-Id all count as this one device

AI_OFF_NOTICE = "AI is switched off on this copy of Dialectic."
DEVICE_LIMIT_NOTICE = ("You've used this device's AI questions for the hour. "
                       "Classmates' answers and the course library still work.")
BUDGET_NOTICE = ("This copy of Dialectic has used up its AI budget. "
                 "Classmates' answers and the course library still work.")

# service name in the spend table -> the .env variable holding its budget in USD
BUDGET_VARS = {"ai": "AI_BUDGET_USD", "search": "SEARCH_BUDGET_USD"}


class LimitReached(Exception):
    """A paid call refused by a limit. str(e) is the notice shown to the student."""


class BudgetExceeded(LimitReached):
    pass


def env_number(name):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(f"{name} is not set: copy it from .env.example into .env (SPEC §9.1)")
    return float(value)


def ai_off():
    return os.environ.get("AI_OFF", "0").strip() == "1"


def service_total(conn, service):
    return conn.execute("SELECT COALESCE(SUM(usd), 0) FROM spend WHERE service = ?", (service,)).fetchone()[0]


def device_paid_asks(conn, device_id):
    """How many Asks from this device spent money in the last hour (cached replays spend nothing)."""
    since = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    return conn.execute(
        "SELECT COUNT(DISTINCT question_id) FROM spend WHERE device_id = ? AND at >= ?", (device_id, since),
    ).fetchone()[0]


class Meter:
    """One per Ask: checks the limits before each paid call and records what it cost."""

    def __init__(self, conn, device_id, question_id):
        self.conn = conn
        self.device_id = device_id or UNKNOWN_DEVICE
        self.question_id = question_id
        self.spent = False  # has this Ask paid for anything yet? (then it already counts for the device)

    def check(self, service):
        if ai_off():
            raise LimitReached(AI_OFF_NOTICE)
        per_hour = int(env_number("DEVICE_ASKS_PER_HOUR"))
        # An Ask that has already paid once may finish: the limit is on starting new paid Asks.
        if per_hour > 0 and not self.spent and device_paid_asks(self.conn, self.device_id) >= per_hour:
            raise LimitReached(DEVICE_LIMIT_NOTICE)
        if service_total(self.conn, service) >= env_number(BUDGET_VARS[service]):
            raise BudgetExceeded(BUDGET_NOTICE)

    def record(self, service, units, usd):
        self.conn.execute(
            "INSERT INTO spend (at, service, units, usd, device_id, question_id) VALUES (?, ?, ?, ?, ?, ?)",
            (db.now(), service, units, usd, self.device_id, self.question_id),
        )
        self.conn.commit()  # at once: what was spent stays recorded even if the Ask crashes later
        self.spent = True


def totals(conn):
    """For GET /api/spend: each service's total against its budget. Nothing per device."""
    out = {}
    for service, var in BUDGET_VARS.items():
        row = conn.execute(
            "SELECT COALESCE(SUM(usd), 0) AS usd, COUNT(*) AS calls FROM spend WHERE service = ?", (service,),
        ).fetchone()
        budget = os.environ.get(var)
        out[service] = {"usd": round(row["usd"], 4), "calls": row["calls"],
                        "budget_usd": float(budget) if budget else None}
    out["ai_off"] = ai_off()
    per_hour = os.environ.get("DEVICE_ASKS_PER_HOUR")
    out["device_asks_per_hour"] = int(per_hour) if per_hour else None
    return out
