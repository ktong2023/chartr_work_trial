"""Private rule engine for the follow-up induction prototype.

The clinic's standards are never published to the agent; they are demonstrated only through
past determinations. This module is the single source of truth for those standards, and it
also encodes plausible misconceptions so the builder can check that the precedents refute each
one and that every current case depends on getting several of them right.
"""
import datetime as dt
from calendar import monthrange

EVAL = dt.date(2026, 9, 24)
STATUSES = ("no_requirement", "not_due", "overdue", "completed", "unclear")
MISCONCEPTIONS = {
    "nurse": "Nurse-entered plans count as follow-up requirements",
    "implicit_later": "When clinician plans disagree without an explicit replacement, the later one governs",
    "implicit_earlier": "When clinician plans disagree without an explicit replacement, the earlier one governs",
    "explicit_ignored": "An explicit replacement does not remove the earlier plan",
    "retract": "Retracted documentation still counts",
    "first_dose": "'After completing treatment' is counted from the first dose",
    "count_all": "Every charted dose counts, including duplicates and doses not given",
    "no_restart": "A clinician's restart of the series is ignored",
    "booking": "A booked visit counts as completion",
    "selfreport": "A patient's report of outside testing counts as completion",
    "any_test": "Any laboratory result counts as completion",
    "rejected": "A result from a rejected specimen counts as completion",
    "outside_no": "Only clinic laboratory results count as completion",
    "late_no": "A test completed after the due date does not count",
    "days": "Month intervals are counted as 30-day blocks",
    "baseline": "A pre-treatment RPR counts as completion",
}


def parse(value):
    return dt.date.fromisoformat(value)


def add_months(day, months, mis):
    if "days" in mis:
        return day + dt.timedelta(days=30 * months)
    year, month = divmod(day.month - 1 + months, 12)
    year, month = day.year + year, month + 1
    return dt.date(year, month, min(day.day, monthrange(year, month)[1]))


def counted_doses(case, mis):
    doses = sorted(case["doses"], key=lambda d: d["date"])
    if "count_all" not in mis:
        doses = [d for d in doses if d["status"] == "given"]
    restarts = [] if "no_restart" in mis else [
        r for r in case.get("restarts", []) if "retract" in mis or not r.get("retracted")]
    if restarts:
        start = max(r["date"] for r in restarts)
        doses = [d for d in doses if d["date"] >= start]
    return doses


def anchor_date(case, anchor, mis):
    doses = counted_doses(case, mis)
    if not doses:
        return None
    if anchor == "treatment" or "first_dose" in mis:
        return parse(doses[0]["date"])
    needed = 1 if case["regimen"] == "single" else 3
    return parse(doses[needed - 1]["date"]) if len(doses) >= needed else None


def due_date(case, plan, mis):
    if plan.get("due"):
        return parse(plan["due"])
    anchor = anchor_date(case, plan["anchor"], mis)
    return add_months(anchor, plan["months"], mis) if anchor else None


def completion_records(case, due, mis):
    """Records that complete the governing requirement, earliest first."""
    treated = parse(min(d["date"] for d in case["doses"]))
    found = []
    for r in case.get("results", []):
        collected = parse(r["collected"])
        if r["test"] != "RPR" and "any_test" not in mis:
            continue
        if r.get("rejected") and "rejected" not in mis:
            continue
        if r["source"] == "outside" and "outside_no" in mis:
            continue
        if collected > EVAL:
            continue
        if r.get("baseline") and "baseline" not in mis:
            continue
        if not r.get("baseline") and collected < treated:
            continue
        if "late_no" in mis and due and collected > due:
            continue
        found.append((collected, r["key"]))
    if "booking" in mis:
        found += [(parse(b["booked"]), b["key"]) for b in case.get("bookings", [])]
    if "selfreport" in mis:
        found += [(parse(m["date"]), m["key"]) for m in case.get("selfreports", [])]
    return [key for _, key in sorted(found)]


def determine(case, mis=frozenset()):
    """The determination as of EVAL: status, governing plan key, due date, completion keys."""
    plans = [p for p in case["plans"] if (p["role"] == "treating-clinician" or "nurse" in mis)
             and ("retract" in mis or not p.get("retracted"))]
    if "explicit_ignored" not in mis:
        replaced = {key for p in plans for key in p.get("replaces", ())}
        plans = [p for p in plans if p["key"] not in replaced]
    if len(plans) > 1 and ("implicit_later" in mis or "implicit_earlier" in mis):
        plans = [sorted(plans, key=lambda p: p["date"])[-1 if "implicit_later" in mis else 0]]
    if not plans:
        return {"status": "no_requirement", "plan": None, "due": None, "completion": []}
    dues = [due_date(case, p, mis) for p in plans]
    if len(set(dues)) > 1:
        return {"status": "unclear", "plan": None, "due": None, "completion": []}
    plan = sorted(plans, key=lambda p: p["date"])[0]  # identical timing: one requirement
    due = dues[0]
    done = completion_records(case, due, mis)
    if done:
        status = "completed"
    elif due is None or due > EVAL:
        status = "not_due"
    else:
        status = "overdue"
    return {"status": status, "plan": plan["key"], "due": due.isoformat() if due else None,
            "completion": done if status == "completed" else []}


def answer(case, mis=frozenset()):
    """A single concrete determination: the earliest completion record is the one recorded."""
    result = determine(case, mis)
    return (result["status"], result["plan"], result["due"], (result["completion"] or [None])[0])


def passes(given, case):
    """Whether a concrete determination matches the standards (any valid completion record is accepted)."""
    expected = determine(case)
    status, plan, due, completion = given
    ok_completion = completion in expected["completion"] if expected["completion"] else completion is None
    return (status, plan, due) == (expected["status"], expected["plan"], expected["due"]) and ok_completion


def coverage(history, current):
    """For each misconception: which precedents refute it and which current cases it would fail."""
    report = {}
    for name in MISCONCEPTIONS:
        refuted = [h["pid"] for h in history if answer(h, {name}) != answer(h)]
        breaks = [c["pid"] for c in current if not passes(answer(c, {name}), c)]
        report[name] = {"refuted_by": refuted, "fails_current": breaks}
    return report
