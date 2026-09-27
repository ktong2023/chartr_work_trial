"""Private, independent deterministic grading of controller-collected evidence."""
import hashlib
import json
import sys
from pathlib import Path

BASELINE = json.loads((Path(__file__).parent / "baseline.json").read_text())
PREFIX = "https://chartr.example/fhir/"
OWNERS = {"treatment_review": "Organization/clinical-review", "follow_up": "Organization/follow-up-coordination"}
IMMUTABLE = ("for", "focus", "code", "reasonCode", "owner", "authoredOn")
# Opaque public record IDs under private role names (qa/build_fixture.py keys; checked by qa tests).
R = {"S02": "R186162", "S01": "R963338", "S03": "R957160", "S04": "R743999", "S05": "R843963", "D03": "R546612",
     "D01": "R426517", "D04": "R413407", "D02": "R977714", "D05": "R673514", "M02": "R357790", "M04": "R277410",
     "M01": "R320845", "M03": "R921741", "M05": "R778350", "P105.plan": "R747576", "P105.note": "R574649",
     "P105.rx": "R416751", "P105.dose": "R242510", "P105.rpr0": "R447145", "P105.recall": "R616015", "P105.msg1":
     "R798211", "P106.plan": "R338426", "P106.note": "R774543", "P106.rx": "R271652", "P106.dose": "R166509",
     "P106.rpr0": "R224923", "P106.nurse": "R555724", "P106.book": "R476096", "P106.visit": "R383971", "P107.planA":
     "R944637", "P107.planB": "R193590", "P107.note": "R248036", "P107.note2": "R371011", "P107.rx": "R209747",
     "P107.dose": "R258646", "P107.rpr0": "R942580", "P108.rpr1": "R853409", "P108.review": "R587067", "P108.note":
     "R220415", "P108.rx": "R932433", "P108.plan6": "R444747", "P108.plan12": "R948337", "P108.dose": "R224591",
     "P108.rpr0": "R269829", "P108.order": "R498283", "P109.plan": "R501006", "P109.note": "R196809", "P109.rx":
     "R713344", "P109.dose": "R179198", "P109.rpr0": "R284350", "P109.visit": "R752438", "P109.hivorder": "R441761",
     "P109.nurse": "R173760", "P109.hiv": "R487631", "P110.note2": "R108970", "P110.plan1": "R756689", "P110.plan2":
     "R502988", "P110.note": "R903446", "P110.rx1": "R536741", "P110.tel": "R387348", "P110.rx2": "R219883",
     "P110.rpr0": "R742002", "P112.addendum": "R315452", "P112.note": "R852956", "P112.rx": "R831915", "P112.plan":
     "R875522", "P112.dose": "R764195", "P112.rpr0": "R848090", "P112.hivorder": "R318030", "P112.hiv": "R732740",
     "P113.outside": "R677898", "P113.note": "R729385", "P113.rx": "R658105", "P113.plan": "R116410", "P113.dose":
     "R523594", "P113.rpr0": "R558925", "P113.msg1": "R901976", "P114.note": "R684245", "P114.rx": "R168071",
     "P114.hcgorder": "R297711", "P114.hcg": "R683370", "P114.nurse": "R790195", "P114.tel": "R580796", "P116.plan":
     "R519119", "P116.note": "R718523", "P116.rx": "R155694", "P116.dose": "R236153", "P116.rpr0": "R544467",
     "P116.misfiled": "R407207", "P116.nurse": "R178178", "P117.rxA": "R372129", "P117.rxB": "R695858",
     "P117.noteA": "R576398", "P117.noteB": "R380584", "P117.dose": "R401028", "P117.plan": "R475671", "P117.rpr0":
     "R220114", "P117.tel": "R721251", "P119.tel": "R120370", "P119.note": "R231490", "P119.rx": "R808600",
     "P119.note2": "R740125", "P121.rxA": "R393154", "P121.rxB": "R667065", "P121.noteA": "R805763", "P121.dose1":
     "R862283", "P121.noteB": "R616229", "P122.rxA": "R729369", "P122.rxB": "R312498", "P122.noteA": "R170588",
     "P122.noteB": "R537713", "P122.csf": "R324838", "P124.planA": "R119415", "P124.planB": "R562058", "P124.noteA":
     "R662626", "P124.noteB": "R514785", "P124.rx": "R923346", "P124.dose": "R684615", "P124.rpr0": "R191046",
     "P124.hiv": "R966298", "P124.hivorder": "R707619", "P126.planA": "R242049", "P126.noteA": "R979931", "P126.rx":
     "R370581", "P126.dose": "R902020", "P126.rpr0": "R409753", "P126.noteB": "R135728", "P126.planB": "R580190",
     "P126.retract": "R921566", "P128.rpr2": "R648216", "P128.corr": "R753315", "P128.note": "R784072", "P128.rx":
     "R200341", "P128.plan": "R703670", "P128.dose": "R526035", "P128.rpr0": "R910104", "P128.order1": "R805460",
     "P128.rpr1": "R662284", "P128.reject": "R670326", "P128.order2": "R320814", "P129.rxA": "R130390", "P129.rxB":
     "R401350", "P129.noteA": "R526194", "P129.nurse": "R382464", "P129.hold": "R550723", "P129.tel": "R786012",
     "P129.noteB": "R335030", "P129.d1": "R199012", "P129.d2": "R441083", "P130.noteA": "R366471", "P130.nurse":
     "R395663", "P130.rx": "R229531", "P130.clear": "R319245", "P130.retract": "R346027", "P132.plan": "R383303",
     "P132.note": "R233805", "P132.rx": "R261430", "P132.d1": "R385918", "P132.d2": "R118659", "P132.restart":
     "R235367", "P132.d3": "R963826", "P132.r2": "R930860", "P132.r3": "R274445", "P132.corr": "R447975",
     "P132.rpr0": "R661764"}


def ids(*keys):
    return {R[k] for k in keys}


def case(item, reason, status, required, allowed):
    """item: seeded ID that must be kept, or None for a new item. required: groups, one citation from each."""
    return {"item": item, "reason": reason, "status": status,
            "required": [ids(*group) for group in required], "allowed": ids(*allowed)}


# (patient, category) -> the single expected final item. Every other pair must have no item.
EXPECTED = {
    ("P101", "treatment_review"): case(None, "UNRESOLVED_TREATMENT_CONCERN", "open",
                                       [["S02"], ["S01", "S03"], ["S04"]], ["S01", "S02", "S03", "S04", "S05"]),
    ("P102", "treatment_review"): case("Q2146", "UNRESOLVED_TREATMENT_CONCERN", "resolved",
                                       [["D03"], ["D01", "D04"]], ["D01", "D02", "D03", "D04", "D05"]),
    ("P103", "treatment_review"): case(None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification",
                                       [["M02"], ["M04"]], ["M01", "M02", "M03", "M04", "M05"]),
    # Recall-list removal by staff and an unverified patient report do not complete or cancel the plan.
    ("P105", "follow_up"): case("Q2203", "OVERDUE_FOLLOW_UP", "open", [["P105.plan"]],
                                ["P105.note", "P105.rx", "P105.plan", "P105.dose", "P105.rpr0",
                                 "P105.recall", "P105.msg1"]),
    # Due date passed; a visit booked for after the due date is not completion.
    ("P106", "follow_up"): case(None, "OVERDUE_FOLLOW_UP", "open", [["P106.plan"]],
                                ["P106.note", "P106.rx", "P106.plan", "P106.dose", "P106.rpr0",
                                 "P106.nurse", "P106.book", "P106.visit"]),
    # Two current plans for the same test give incompatible due dates; neither revises the other.
    ("P107", "follow_up"): case(None, "FOLLOW_UP_TIMING_UNCLEAR", "needs_clarification",
                                [["P107.planA"], ["P107.planB"]],
                                ["P107.note", "P107.note2", "P107.rx", "P107.planA", "P107.planB",
                                 "P107.dose", "P107.rpr0"]),
    # Completed after its due date; the 12-month plan is not yet due.
    ("P108", "follow_up"): case("Q2217", "OVERDUE_FOLLOW_UP", "resolved", [["P108.rpr1", "P108.review"]],
                                ["P108.note", "P108.rx", "P108.plan6", "P108.plan12", "P108.dose", "P108.rpr0",
                                 "P108.order", "P108.rpr1", "P108.review"]),
    # A recent visit and HIV result are not the required RPR.
    ("P109", "follow_up"): case(None, "OVERDUE_FOLLOW_UP", "open", [["P109.plan"]],
                                ["P109.note", "P109.rx", "P109.plan", "P109.dose", "P109.rpr0", "P109.visit",
                                 "P109.hivorder", "P109.nurse", "P109.hiv"]),
    # A treating clinician replaced the overdue plan in prose (plan status left active); replacement not yet due.
    ("P110", "follow_up"): case("Q2081", "OVERDUE_FOLLOW_UP", "resolved", [["P110.note2"], ["P110.plan1", "P110.plan2"]],
                                ["P110.note", "P110.rx1", "P110.plan1", "P110.tel", "P110.note2", "P110.rx2",
                                 "P110.plan2", "P110.rpr0"]),
    # An addendum corrected the interval to 3 months; the plan record still says 6.
    ("P112", "follow_up"): case(None, "OVERDUE_FOLLOW_UP", "open", [["P112.addendum"]],
                                ["P112.note", "P112.rx", "P112.plan", "P112.dose", "P112.rpr0", "P112.hivorder",
                                 "P112.hiv", "P112.addendum"]),
    # A scanned outside RPR result is completion evidence; the earlier portal message is not.
    ("P113", "follow_up"): case("Q2119", "OVERDUE_FOLLOW_UP", "resolved", [["P113.outside"]],
                                ["P113.note", "P113.rx", "P113.plan", "P113.dose", "P113.rpr0", "P113.msg1",
                                 "P113.outside"]),
    # The pregnancy result arrived, but no clinician has recorded the treatment decision.
    ("P114", "treatment_review"): case(None, "UNRESOLVED_TREATMENT_CONCERN", "open", [["P114.note"], ["P114.rx"]],
                                       ["P114.note", "P114.rx", "P114.hcgorder", "P114.hcg", "P114.nurse", "P114.tel"]),
    # The only post-due RPR was another patient's result, corrected by later documentation.
    ("P116", "follow_up"): case("Q2187", "OVERDUE_FOLLOW_UP", "open", [["P116.plan"]],
                                ["P116.note", "P116.rx", "P116.plan", "P116.dose", "P116.rpr0", "P116.misfiled",
                                 "P116.nurse"]),
    # Unreconciled weekly-x3 and single-dose orders, plus an independent overdue RPR plan: two items.
    ("P117", "treatment_review"): case(None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", [["P117.rxA"], ["P117.rxB"]],
                                       ["P117.noteA", "P117.noteB", "P117.rxA", "P117.rxB", "P117.dose"]),
    ("P117", "follow_up"): case(None, "OVERDUE_FOLLOW_UP", "open", [["P117.plan"]],
                                ["P117.plan", "P117.noteA", "P117.noteB", "P117.rxA", "P117.rxB", "P117.dose",
                                 "P117.rpr0", "P117.tel"]),
    # The later clinician note addresses the penicillin allergy, not the isotretinoin interaction.
    ("P119", "treatment_review"): case("Q2209", "UNRESOLVED_TREATMENT_CONCERN", "open", [["P119.tel"]],
                                       ["P119.note", "P119.rx", "P119.tel", "P119.note2"]),
    # Later, well-reasoned plans that never cancel the earlier active order: still a conflict.
    ("P121", "treatment_review"): case(None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", [["P121.rxA"], ["P121.rxB"]],
                                       ["P121.noteA", "P121.rxA", "P121.dose1", "P121.noteB", "P121.rxB"]),
    ("P122", "treatment_review"): case(None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", [["P122.rxA"], ["P122.rxB"]],
                                       ["P122.noteA", "P122.rxA", "P122.noteB", "P122.rxB", "P122.csf"]),
    # A rationale for longer follow-up, but no explicit revision of the earlier plan: timing unclear.
    ("P124", "follow_up"): case(None, "FOLLOW_UP_TIMING_UNCLEAR", "needs_clarification", [["P124.planA"], ["P124.planB"]],
                                ["P124.noteA", "P124.noteB", "P124.planA", "P124.planB", "P124.rx", "P124.dose",
                                 "P124.rpr0", "P124.hiv", "P124.hivorder"]),
    # Event histories: the answer depends on reconstructing state at the evaluation time.
    ("P126", "follow_up"): case(None, "OVERDUE_FOLLOW_UP", "open", [["P126.planA"]],
                                ["P126.planA", "P126.noteA", "P126.rx", "P126.dose", "P126.rpr0", "P126.noteB",
                                 "P126.planB", "P126.retract"]),
    ("P128", "follow_up"): case("Q2131", "OVERDUE_FOLLOW_UP", "resolved", [["P128.rpr2", "P128.corr"]],
                                ["P128.note", "P128.rx", "P128.plan", "P128.dose", "P128.rpr0", "P128.order1",
                                 "P128.rpr1", "P128.reject", "P128.order2", "P128.rpr2", "P128.corr"]),
    ("P129", "treatment_review"): case(None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", [["P129.rxA"], ["P129.rxB"]],
                                       ["P129.noteA", "P129.rxA", "P129.nurse", "P129.hold", "P129.tel", "P129.noteB",
                                        "P129.rxB", "P129.d1", "P129.d2"]),
    ("P130", "treatment_review"): case("Q2104", "UNRESOLVED_TREATMENT_CONCERN", "open", [["P130.noteA", "P130.nurse"]],
                                       ["P130.noteA", "P130.rx", "P130.nurse", "P130.clear", "P130.retract"]),
    ("P132", "follow_up"): case(None, "OVERDUE_FOLLOW_UP", "open", [["P132.plan"]],
                                ["P132.note", "P132.rx", "P132.plan", "P132.d1", "P132.d2", "P132.restart", "P132.d3",
                                 "P132.r2", "P132.r3", "P132.corr", "P132.rpr0"]),
}


class EvaluationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def code(item, field, system):
    coding = item.get(field, {}).get("coding", [])
    return next((c.get("code") for c in coding if c.get("system") == PREFIX + "CodeSystem/" + system), None)


def check_evidence_integrity(snapshot, attestation):
    try:
        meta = snapshot["metadata"]
        for key in ("trial_id", "nonce", "initial_digest", "version", "evaluation_time"):
            if not meta[key] or meta[key] != attestation[key]:
                raise EvaluationError("Snapshot does not match controller attestation: " + key)
        for key in ("initial_digest", "version", "evaluation_time"):
            if meta[key] != BASELINE[key]:
                raise EvaluationError("Incorrect fixture baseline: " + key)
        if not meta["frozen"] or meta["faults"] != 0:
            raise EvaluationError("Snapshot was not frozen or service recorded an infrastructure fault")
        current = BASELINE["queue"]
        for seq, event in enumerate(snapshot["audit"], 1):
            if event["seq"] != seq or event["before"] != current:
                raise EvaluationError("Audit sequence/state continuity broken")
            if event["status"] >= 500:
                raise EvaluationError("Service failed during evaluation")
            if (event["method"] == "GET" or event["status"] != 200) and event["after"] != current:
                raise EvaluationError("Read/rejected operation changed state")
            current = event["after"]
        if snapshot["queue"] != current:
            raise EvaluationError("Final queue differs from service audit")
    except (KeyError, TypeError) as exc:
        raise EvaluationError("Missing or malformed trusted evidence") from exc


def grade_item(item, patient, expected, sources, seeded):
    refs = [i.get("valueReference", {}).get("reference", "") for i in item.get("input", [])]
    cited = {r.split("/")[-1] for r in refs}
    valid_refs = all(ref == sources.get(ref.split("/")[-1], {}).get("resourceType", "") + "/" + ref.split("/")[-1]
                     and sources.get(ref.split("/")[-1], {}).get("subject", {}).get("reference") == "Patient/" + patient
                     for ref in refs)
    episode = "EpisodeOfCare/E" + patient[1:]
    checks = {
        "identity": item["id"] == expected["item"] if expected["item"] else item["id"] not in seeded,
        "episode": item.get("focus", {}).get("reference") == episode
            and any(e.get("url") == PREFIX + "StructureDefinition/episode"
                    and e.get("valueReference", {}).get("reference") == episode for e in item.get("extension", [])),
        "reason": code(item, "reasonCode", "review-reason") == expected["reason"],
        "disposition": code(item, "businessStatus", "review-status") == expected["status"]
            and item.get("status") == ("completed" if expected["status"] == "resolved" else "requested"),
        "evidence": valid_refs and cited <= expected["allowed"] and all(cited & group for group in expected["required"]),
        "explanation": isinstance(item.get("description"), str) and bool(item["description"].strip()),
    }
    if expected["item"]:
        checks["original_creation"] = item.get("authoredOn") == seeded[expected["item"]]["authoredOn"]
    return checks


def grade(snapshot, attestation):
    check_evidence_integrity(snapshot, attestation)
    queue = snapshot["queue"]
    sources = {r["id"]: r for r in snapshot["sources"]}
    seeded = {r["id"]: r for r in BASELINE["queue"]}
    final = {r["id"]: r for r in queue}
    patients = sorted(r["id"] for r in snapshot["sources"] if r["resourceType"] == "Patient")
    expected_items = {k: v for k, v in EXPECTED.items() if k[0] in patients}
    checks = {"source_integrity": digest(snapshot["sources"]) == BASELINE["sources_digest"],
              "total_items": len(queue) == len(expected_items),
              "unique_ids": len(final) == len(queue),
              "seeded_items_preserved": all(i in final and all(final[i].get(k) == s.get(k) for k in IMMUTABLE)
                                            for i, s in seeded.items())}
    diagnostics = {}
    for patient in patients:
        for category, owner in OWNERS.items():
            items = [r for r in queue if r.get("for", {}).get("reference") == "Patient/" + patient
                     and code(r, "code", "category") == category]
            expected = expected_items.get((patient, category))
            if expected is None:
                diagnostics[patient + "/" + category] = {"no_item": not items}
                continue
            result = {"item_count": len(items) == 1}
            if len(items) == 1:
                result["destination"] = items[0].get("owner", {}).get("reference") == owner
                result.update(grade_item(items[0], patient, expected, sources, seeded))
            diagnostics[patient + "/" + category] = result
    passed = all(checks.values()) and all(all(c.values()) for c in diagnostics.values())
    return {"validity": "valid", "reward": int(passed), "global": checks, "cases": diagnostics,
            "narrative_limit": "Explanation is checked for nonempty text only; factual prose needs human QA."}


def main():
    snapshot_path, attestation_path, output = map(Path, sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    for name in ("reward.txt", "reward.json"):
        (output / name).unlink(missing_ok=True)
    try:
        termination_path = snapshot_path.parent / "termination.json"
        if termination_path.exists():
            termination = json.loads(termination_path.read_text())
            if termination["validity"] != "valid":
                raise EvaluationError("Adapter did not complete a valid attempt: " + termination["reason"])
        result = grade(json.loads(snapshot_path.read_text()), json.loads(attestation_path.read_text()))
    except Exception as exc:
        (output / "diagnostics.json").write_text(json.dumps({"validity": "evaluation_error", "error": str(exc)}, indent=2))
        # Never manufacture reward=0 for an invalid evaluation.
        raise SystemExit(2)
    (output / "diagnostics.json").write_text(json.dumps(result, indent=2))
    (output / "reward.txt").write_text(str(result["reward"]) + "\n")


if __name__ == "__main__":
    main()
