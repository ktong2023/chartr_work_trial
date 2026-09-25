"""Private deterministic reference; exclusively uses the public clinic CLI."""
import json
import subprocess


def clinic(*args):
    return json.loads(subprocess.check_output(["clinic", *args], text=True))


def solve(order=("P101", "P102", "P103"), alternative=False):
    patients = clinic("patients")
    for entry in patients["patients"]:
        clinic("records", entry["patient"]["id"])
        clinic("reviews", "--patient", entry["patient"]["id"])
    for patient in order:
        if patient == "P102":
            clinic("update", "Q102", "--json", json.dumps({
                "status": "resolved", "evidence": ["D01", "D03"] if alternative else ["D03", "D04", "D05"],
                "explanation": "D03 addresses the reported reaction and explicitly replaces D01 with D04. The plan concern is resolved; the allergy history remains."}))
            continue
        fields = {"patient": patient, "episode": "E101" if patient == "P101" else "E103",
                  "category": "treatment_review", "destination": "clinical_review"}
        if patient == "P101":
            fields.update(reason="UNRESOLVED_TREATMENT_CONCERN", status="open",
                          evidence=["S04", "S03", "S02"] if alternative else ["S01", "S02", "S04"],
                          explanation="Treatment selection awaits assessment. The plan is draft and the pregnancy test remains uncollected without a result.")
        else:
            fields.update(reason="CONFLICTING_ACTIVE_PLANS", status="needs_clarification",
                          evidence=["M04", "M02"] if alternative else ["M01", "M02", "M03", "M04"],
                          explanation="Both the three-dose and single-dose instructions remain active for this episode. No replacement or clinician reconciliation is documented.")
        clinic("create", "--json", json.dumps(fields))
    final = clinic("reviews")
    assert final["complete"] and len(final["items"]) == 3
    return final


if __name__ == "__main__":
    print(json.dumps(solve(), indent=2))
