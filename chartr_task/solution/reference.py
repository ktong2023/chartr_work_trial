"""Private deterministic reference; exclusively uses the public clinic CLI."""
import json
import subprocess

DESTINATIONS = {"treatment_review": "clinical_review", "follow_up": "follow_up_coordination"}
# (patient, category): (existing item or None, reason, status, evidence, alternative evidence, explanation).
# Evidence None means the item is already correct and is left unchanged.
CASES = {
    ("P101", "treatment_review"): (
        None, "UNRESOLVED_TREATMENT_CONCERN", "open", ["R963338", "R186162", "R743999"], ["R743999", "R957160", "R186162"],
        "Treatment selection awaits assessment. The plan is draft and the pregnancy test remains uncollected without a result."),
    ("P102", "treatment_review"): (
        "Q2146", None, "resolved", ["R546612", "R413407", "R673514"], ["R426517", "R546612"],
        "The clinician addressed the reported reaction and replaced the penicillin order with doxycycline. The plan concern is resolved; the allergy history remains."),
    ("P103", "treatment_review"): (
        None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", ["R320845", "R357790", "R921741", "R277410"], ["R277410", "R357790"],
        "Both the three-dose and single-dose instructions remain active for this episode. No replacement or clinician reconciliation is documented."),
    ("P105", "follow_up"): (
        "Q2203", None, "open", None, ["R747576", "R616015", "R798211"],
        "Repeat RPR was due 6 months after the March 1 dose. Staff recall removal does not cancel the plan and no result is on file."),
    ("P106", "follow_up"): (
        None, "OVERDUE_FOLLOW_UP", "open", ["R338426"], ["R338426", "R476096", "R383971"],
        "Repeat RPR was due by 2026-09-05. The booked October visit has not occurred and no result is on file."),
    ("P107", "follow_up"): (
        None, "FOLLOW_UP_TIMING_UNCLEAR", "needs_clarification", ["R944637", "R193590"], ["R248036", "R944637", "R193590", "R371011"],
        "Two current RPR plans give 3-month and 6-month timing after the June 2 dose. Neither revises the other."),
    ("P108", "follow_up"): (
        "Q2217", None, "resolved", ["R853409"], ["R498283", "R587067"],
        "The repeat RPR was collected on 2026-09-15 and resulted. The 12-month plan is not yet due."),
    ("P109", "follow_up"): (
        None, "OVERDUE_FOLLOW_UP", "open", ["R501006", "R179198"], ["R501006", "R487631", "R173760"],
        "Repeat RPR was due 6 months after the February 10 dose. The September visit and HIV test did not include it."),
    ("P110", "follow_up"): (
        "Q2081", None, "resolved", ["R108970", "R756689"], ["R108970", "R502988"],
        "The treating clinician replaced the July RPR plan after re-treatment; the replacement is due in March 2027."),
}


def clinic(*args):
    return json.loads(subprocess.check_output(["clinic", *args], text=True))


def solve(order=None, alternative=False):
    for entry in clinic("patients")["patients"]:
        clinic("records", entry["patient"]["id"])
        clinic("reviews", "--patient", entry["patient"]["id"])
    for key in order or CASES:
        item, reason, status, evidence, alternative_evidence, explanation = CASES[key]
        evidence = alternative_evidence if alternative else evidence
        if evidence is None:
            continue
        if item:
            clinic("update", item, "--json", json.dumps({"status": status, "evidence": evidence, "explanation": explanation}))
            continue
        patient, category = key
        clinic("create", "--json", json.dumps({
            "patient": patient, "episode": "E" + patient[1:], "category": category, "reason": reason,
            "destination": DESTINATIONS[category], "status": status, "evidence": evidence, "explanation": explanation}))
    return clinic("reviews")


if __name__ == "__main__":
    final = solve()
    assert final["complete"] and len(final["items"]) == len(CASES)
    print(json.dumps(final, indent=2))
