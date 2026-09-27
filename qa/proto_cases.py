"""Private case facts for the follow-up induction prototype (history precedents and current cohort).

History cases (H2xx) are shown to the agent with their determinations; current cases (P3xx) must
be determined by the agent. Each current case combines several standards in a way no single
history case shows, so copying the nearest precedent is not enough.
"""
import datetime as dt


def given(*dates):
    return [{"date": d, "status": "given"} for d in dates]


def doses(*items):
    return [{"date": d, "status": s} for d, s in items]


def plan(key, date, due=None, months=None, anchor=None, role="treating-clinician", replaces=(), retracted=False):
    return {"key": key, "date": date, "due": due, "months": months, "anchor": anchor, "role": role,
            "replaces": tuple(replaces), "retracted": retracted}


def rpr(key, collected, source="clinic", rejected=False, test="RPR"):
    return {"key": key, "collected": collected, "source": source, "rejected": rejected, "test": test}


def case(pid, regimen, dose_list, plans, results=(), restarts=(), bookings=(), selfreports=()):
    # Every chart has a diagnostic (pre-treatment) RPR collected the day before the first dose.
    first = min(d["date"] for d in dose_list)
    baseline = dict(rpr("rpr0", str(dt.date.fromisoformat(first) - dt.timedelta(days=1))), baseline=True)
    return {"pid": pid, "regimen": regimen, "doses": dose_list, "plans": list(plans),
            "results": [baseline, *results], "restarts": list(restarts), "bookings": list(bookings),
            "selfreports": list(selfreports)}


HISTORY = [
    case("H201", "single", given("2026-02-10"), [plan("planA", "2026-02-10", months=6, anchor="treatment")]),
    case("H202", "single", given("2026-04-20"), [plan("planA", "2026-04-20", due="2026-10-20")]),
    case("H203", "single", given("2026-03-03"), [plan("planA", "2026-03-03", months=6, anchor="treatment")],
         results=[rpr("rpr1", "2026-09-01")]),
    case("H204", "weekly3", given("2026-03-05", "2026-03-12", "2026-03-19"),
         [plan("planA", "2026-03-05", months=6, anchor="completion")]),
    case("H205", "weekly3", given("2026-03-25", "2026-04-01", "2026-04-08"),
         [plan("planA", "2026-03-25", months=6, anchor="completion")]),
    case("H206", "weekly3", doses(("2026-03-16", "given"), ("2026-03-23", "given"), ("2026-03-23", "duplicate"),
                                  ("2026-03-30", "given")),
         [plan("planA", "2026-03-16", months=6, anchor="completion")]),
    case("H207", "weekly3", doses(("2026-03-01", "given"), ("2026-03-08", "given"), ("2026-03-15", "not_given"),
                                  ("2026-03-20", "given")),
         [plan("planA", "2026-03-01", months=6, anchor="completion")]),
    case("H208", "weekly3", given("2026-09-08", "2026-09-15"),
         [plan("planA", "2026-09-08", months=6, anchor="completion")]),
    case("H209", "weekly3", given("2026-02-02", "2026-02-09", "2026-03-02", "2026-03-09", "2026-03-16"),
         [plan("planA", "2026-02-02", months=6, anchor="completion")], restarts=[{"date": "2026-03-02"}]),
    case("H210", "weekly3", given("2026-02-23", "2026-03-02", "2026-03-15", "2026-03-22", "2026-03-29"),
         [plan("planA", "2026-02-23", months=6, anchor="completion")],
         restarts=[{"date": "2026-03-15", "retracted": True}]),
    case("H211", "single", given("2026-02-27"), [plan("planN", "2026-03-01", due="2026-08-01", role="nurse")]),
    case("H212", "single", given("2026-05-05"), [plan("planA", "2026-05-05", months=6, anchor="treatment"),
                                                 plan("planN", "2026-05-05", months=3, anchor="treatment", role="nurse")]),
    case("H213", "single", given("2026-02-15"), [plan("planA", "2026-02-15", due="2026-08-15"),
                                                 plan("planB", "2026-06-10", due="2027-02-15", replaces=["planA"])]),
    case("H214", "single", given("2026-06-02"), [plan("planA", "2026-06-02", months=3, anchor="treatment"),
                                                 plan("planB", "2026-07-15", months=6, anchor="treatment")]),
    case("H215", "single", given("2026-03-02"), [plan("planA", "2026-03-02", due="2026-09-02"),
                                                 plan("planB", "2026-06-15", due="2026-12-15", replaces=["planA"],
                                                      retracted=True)]),
    case("H216", "single", given("2026-01-12"), [plan("planA", "2026-01-12", months=6, anchor="treatment"),
                                                 plan("planB", "2026-05-12", months=12, anchor="treatment",
                                                      replaces=["planA"]),
                                                 plan("planN", "2026-07-20", due="2026-08-15", role="nurse",
                                                      replaces=["planB"])]),
    case("H217", "single", given("2026-03-01"), [plan("planA", "2026-03-01", due="2026-09-01")],
         bookings=[{"key": "book", "booked": "2026-09-18", "visit": "2026-10-01"}]),
    case("H218", "single", given("2026-02-27"), [plan("planA", "2026-02-27", months=6, anchor="treatment")],
         selfreports=[{"key": "self", "date": "2026-09-10"}]),
    case("H219", "single", given("2026-02-12"), [plan("planA", "2026-02-12", months=6, anchor="treatment")],
         results=[rpr("hiv", "2026-09-08", test="HIV")]),
    case("H220", "single", given("2026-02-20"), [plan("planA", "2026-02-20", due="2026-08-20")],
         results=[rpr("rpr1", "2026-08-18", rejected=True)]),
    case("H221", "single", given("2026-02-21"), [plan("planA", "2026-02-21", due="2026-08-21")],
         results=[rpr("rpr1", "2026-08-19", rejected=True), rpr("rpr2", "2026-09-02")]),
    case("H222", "single", given("2026-02-16"), [plan("planA", "2026-02-16", due="2026-08-16")],
         results=[rpr("outside", "2026-08-28", source="outside")]),
    case("H223", "single", given("2026-03-04"), [plan("planA", "2026-03-04", due="2026-09-04")],
         results=[rpr("rpr1", "2026-09-15")]),
    case("H224", "single", given("2026-02-09"), [plan("planA", "2026-02-09", months=6, anchor="treatment")]),
    case("H225", "weekly3", given("2026-01-05", "2026-01-12", "2026-01-19"),
         [plan("planA", "2026-01-05", months=6, anchor="completion")],
         results=[rpr("outside", "2026-07-25", source="outside")]),
    case("H226", "single", given("2026-06-10"), [plan("planA", "2026-06-10", months=3, anchor="treatment"),
                                                 plan("planB", "2026-07-01", months=6, anchor="treatment",
                                                      replaces=["planA"])]),
    case("H227", "single", given("2026-04-07"), [plan("planN", "2026-04-07", months=3, anchor="treatment",
                                                      role="nurse")]),
    case("H228", "single", given("2026-04-14"), [plan("planA", "2026-04-14", months=3, anchor="treatment"),
                                                 plan("planB", "2026-05-20", due="2026-10-14")]),
    case("H229", "single", given("2026-03-10"), [plan("planA", "2026-03-10", due="2026-09-10")],
         bookings=[{"key": "book", "booked": "2026-09-14", "visit": "2026-10-06"}]),
    case("H230", "single", given("2026-02-24"), [plan("planA", "2026-02-24", months=6, anchor="treatment")],
         results=[rpr("hiv", "2026-09-03", test="HIV")], selfreports=[{"key": "self", "date": "2026-09-05"}]),
    case("H231", "weekly3", given("2026-01-13", "2026-01-20", "2026-02-09", "2026-02-16", "2026-02-23"),
         [plan("planA", "2026-01-13", months=6, anchor="completion")], restarts=[{"date": "2026-02-09"}]),
]

CURRENT = [
    case("P301", "weekly3", doses(("2026-03-09", "given"), ("2026-03-16", "given"), ("2026-03-16", "duplicate"),
                                  ("2026-03-23", "not_given"), ("2026-03-30", "given")),
         [plan("planA", "2026-03-09", months=6, anchor="completion"),
          plan("planN", "2026-03-30", due="2026-09-20", role="nurse")],
         bookings=[{"key": "book", "booked": "2026-09-17", "visit": "2026-09-29"}]),
    case("P302", "single", given("2026-03-02"),
         [plan("planA", "2026-03-02", due="2026-09-02"),
          plan("planB", "2026-06-15", due="2026-12-15", replaces=["planA"], retracted=True)],
         results=[rpr("hiv", "2026-09-08", test="HIV")], selfreports=[{"key": "self", "date": "2026-09-10"}]),
    case("P303", "weekly3", given("2026-02-23", "2026-03-02", "2026-03-20", "2026-03-27", "2026-04-03"),
         [plan("planA", "2026-02-23", months=3, anchor="completion"),
          plan("planB", "2026-04-20", months=6, anchor="completion", replaces=["planA"])],
         restarts=[{"date": "2026-03-20"}]),
    case("P304", "single", given("2026-02-20"), [plan("planA", "2026-02-20", due="2026-08-20")],
         results=[rpr("rpr1", "2026-08-18", rejected=True), rpr("outside", "2026-09-03", source="outside")]),
    case("P305", "single", given("2026-06-09"),
         [plan("planA", "2026-06-09", months=3, anchor="treatment"),
          plan("planB", "2026-07-10", months=6, anchor="treatment"),
          plan("planC", "2026-08-05", months=6, anchor="treatment", replaces=["planA"], retracted=True)]),
    case("P306", "weekly3", doses(("2026-09-01", "given"), ("2026-09-08", "given"), ("2026-09-15", "not_given")),
         [plan("planA", "2026-09-01", months=6, anchor="completion"),
          plan("planN", "2026-09-02", due="2026-09-20", role="nurse")]),
]
