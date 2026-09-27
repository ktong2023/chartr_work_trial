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
R = {"S01": "R963338", "S02": "R186162", "S03": "R957160", "S04": "R743999", "S05": "R843963", "D01": "R426517",
     "D02": "R977714", "D03": "R546612", "D04": "R413407", "D05": "R673514", "M01": "R320845", "M02": "R357790",
     "M03": "R921741", "M04": "R277410", "M05": "R778350", "P105.note": "R574649", "P105.rx": "R416751",
     "P105.plan": "R747576", "P105.dose": "R242510", "P105.rpr0": "R447145", "P105.recall": "R616015",
     "P105.msg1": "R798211", "P106.note": "R774543", "P106.rx": "R271652", "P106.plan": "R338426",
     "P106.dose": "R166509", "P106.rpr0": "R224923", "P106.nurse": "R555724", "P106.book": "R476096",
     "P106.visit": "R383971", "P107.note": "R248036", "P107.note2": "R371011", "P107.rx": "R209747",
     "P107.planA": "R944637", "P107.planB": "R193590", "P107.dose": "R258646", "P107.rpr0": "R942580",
     "P108.note": "R220415", "P108.rx": "R932433", "P108.plan6": "R444747", "P108.plan12": "R948337",
     "P108.dose": "R224591", "P108.rpr0": "R269829", "P108.order": "R498283", "P108.rpr1": "R853409",
     "P108.review": "R587067", "P109.note": "R196809", "P109.rx": "R713344", "P109.plan": "R501006",
     "P109.dose": "R179198", "P109.rpr0": "R284350", "P109.visit": "R752438", "P109.hivorder": "R441761",
     "P109.nurse": "R173760", "P109.hiv": "R487631", "P110.note": "R903446", "P110.rx1": "R536741",
     "P110.plan1": "R756689", "P110.tel": "R387348", "P110.note2": "R108970", "P110.rx2": "R219883",
     "P110.plan2": "R502988", "P110.rpr0": "R742002"}


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
    # A treating clinician explicitly replaced the overdue plan; the replacement is not yet due.
    ("P110", "follow_up"): case("Q2081", "OVERDUE_FOLLOW_UP", "resolved", [["P110.note2"], ["P110.plan1", "P110.plan2"]],
                                ["P110.note", "P110.rx1", "P110.plan1", "P110.tel", "P110.note2", "P110.rx2",
                                 "P110.plan2", "P110.rpr0"]),
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
    checks = {"source_integrity": digest(snapshot["sources"]) == BASELINE["sources_digest"],
              "total_items": len(queue) == len(EXPECTED),
              "unique_ids": len(final) == len(queue),
              "seeded_items_preserved": all(i in final and all(final[i].get(k) == s.get(k) for k in IMMUTABLE)
                                            for i, s in seeded.items())}
    diagnostics = {}
    patients = sorted(r["id"] for r in snapshot["sources"] if r["resourceType"] == "Patient")
    for patient in patients:
        for category, owner in OWNERS.items():
            items = [r for r in queue if r.get("for", {}).get("reference") == "Patient/" + patient
                     and code(r, "code", "category") == category]
            expected = EXPECTED.get((patient, category))
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
