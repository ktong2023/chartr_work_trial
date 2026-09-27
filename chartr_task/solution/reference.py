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
    ("P112", "follow_up"): (
        None, "OVERDUE_FOLLOW_UP", "open", ["R315452", "R875522"], ["R315452", "R732740", "R764195"],
        "An addendum corrected the RPR plan to 3 months after the April 10 dose, so it was due July 10. No result is on file."),
    ("P113", "follow_up"): (
        "Q2119", None, "resolved", ["R677898"], ["R677898", "R116410"],
        "A scanned outside report shows an RPR titer collected on 2026-08-28, so the required test was performed."),
    ("P114", "treatment_review"): (
        None, "UNRESOLVED_TREATMENT_CONCERN", "open", ["R684245", "R168071", "R683370"], ["R684245", "R168071", "R790195"],
        "Treatment selection was deferred until pregnancy status was known. The test is now negative, but no clinician has recorded a treatment decision and doxycycline remains an unreleased draft."),
    ("P116", "follow_up"): (
        "Q2187", None, "open", None, ["R519119", "R407207", "R178178"],
        "The only RPR filed after the due date belongs to another patient, as later documented. The repeat RPR is still outstanding."),
    ("P117", "treatment_review"): (
        None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", ["R576398", "R372129", "R380584", "R695858"], ["R695858", "R372129"],
        "A weekly three-dose order and a single-dose order are both active for this episode, with no reconciliation."),
    ("P117", "follow_up"): (
        None, "OVERDUE_FOLLOW_UP", "open", ["R475671", "R576398"], ["R475671"],
        "The repeat RPR was due by 2026-09-02 and no result is on file. This is separate from the unresolved regimen conflict."),
    ("P119", "treatment_review"): (
        "Q2209", None, "open", None, ["R120370", "R808600", "R740125"],
        "The later clinician note addresses the penicillin allergy referral, not the isotretinoin interaction. Pharmacy is still holding doxycycline."),
    ("P121", "treatment_review"): (
        None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", ["R805763", "R393154", "R616229", "R667065"], ["R667065", "R393154"],
        "A weekly three-dose order and a later single-dose order are both active. The later note reassesses the stage but does not cancel the weekly order."),
    ("P122", "treatment_review"): (
        None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", ["R729369", "R537713", "R312498"], ["R312498", "R729369", "R324838"],
        "The IV penicillin order remains active alongside a later single-dose benzathine order; the later note does not discontinue the IV plan."),
    ("P124", "follow_up"): (
        None, "FOLLOW_UP_TIMING_UNCLEAR", "needs_clarification", ["R119415", "R562058"], ["R562058", "R514785", "R119415"],
        "Two current RPR plans give 3-month and 6-month timing after the June 10 dose. The later note does not explicitly revise or replace the earlier plan."),
    ("P126", "follow_up"): (
        None, "OVERDUE_FOLLOW_UP", "open", ["R242049", "R921566"], ["R242049"],
        "The June revision was retracted, so the original plan governs: the repeat RPR was due by 2026-09-02 and no result is on file."),
    ("P128", "follow_up"): (
        "Q2131", None, "resolved", ["R648216", "R753315"], ["R320814", "R648216"],
        "The 8/18 specimen was rejected, but the recollected RPR on 9/2 produced a valid (later corrected) result."),
    ("P129", "treatment_review"): (
        None, "CONFLICTING_ACTIVE_PLANS", "needs_clarification", ["R130390", "R550723", "R786012", "R401350"], ["R401350", "R130390"],
        "Doxycycline was held and then resumed, and a benzathine penicillin series has since started. Both regimens are current and neither was stopped."),
    ("P130", "treatment_review"): (
        "Q2104", None, "open", ["R395663", "R366471", "R346027"], ["R395663"],
        "The 8/20 note that cleared IM injections was retracted as another patient's note, so the INR concern is again unresolved."),
    ("P132", "follow_up"): (
        None, "OVERDUE_FOLLOW_UP", "open", ["R383303", "R447975"], ["R383303"],
        "The restart was corrected as unnecessary; treatment completed on 3/15, so the repeat RPR was due 9/15 and no result is on file."),
}


def clinic(*args):
    return json.loads(subprocess.check_output(["clinic", *args], text=True))


def solve(order=None, alternative=False):
    cohort = [entry["patient"]["id"] for entry in clinic("patients")["patients"]]
    for patient in cohort:
        clinic("records", patient)
        clinic("reviews", "--patient", patient)
    for key in order or CASES:
        if key[0] not in cohort:
            continue
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
    cohort = {entry["patient"]["id"] for entry in clinic("patients")["patients"]}
    assert final["complete"] and len(final["items"]) == sum(key[0] in cohort for key in CASES)
    print(json.dumps(final, indent=2))
