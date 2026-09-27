"""Render a Task 3 independent-review packet (TASK_DESIGN_PRINCIPLES.md section 6) from the built fixture.

The packet holds only what an agent could see: the selected patients' charts, the charts of every patient linked to
them through a laboratory result, the accessioning entries for those results, their review requests, and the public
docs. The authored answers go to a separate key file that must not be given to the reviewer.

    python qa/task3_review_packet.py PACKET_DIR KEY_FILE SELECTOR [SELECTOR ...]

A selector is a patient key (p12, g170) or family:NAME (family:F3_stage_inference).
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_task3'
sys.path[:0] = [str(TASK / 'tests'), str(ROOT / 'qa')]
from grade import admissible, ext  # noqa: E402
from task3_cases import ISSUES  # noqa: E402
from task3_cohort import PATIENTS  # noqa: E402

SHORT = {'confirmed': 'C', 'not_an_issue': 'NI'}
CODES = {'RESULT_PENDING': 'RP', 'OUTSIDE_RECORD_NOT_RECEIVED': 'ORNR', 'UNRESOLVED_SOURCE_CONFLICT': 'USC'}


def when(r):
    return (ext(r, 'event-time') or '')[:10]


def line(r):
    t, i = r['resourceType'], r['id']
    if t == 'DocumentReference':
        return f"[{i}] {when(r)} {r['type']['text']} ({r['author'][0]['display']}, role {ext(r, 'author-role')}):\n    " + \
            r['description'].replace('\n', '\n    ')
    if t == 'Specimen':
        return (f"[{i}] {when(r)} SPECIMEN (collection record) accession={r['accessionIdentifier']['value']} "
                f"label={ext(r, 'label-name')} MRN {ext(r, 'label-mrn')} DOB {ext(r, 'label-dob')} "
                f"collected={r['collection']['collectedDateTime']} collector={r['collection']['collector']['display']}")
    if t == 'Observation':
        note = ' comment=' + repr(r['note'][0]['text']) if r.get('note') else ''
        return (f"[{i}] {when(r)} LAB {r['code']['text']}: status={r['status']} value={r.get('valueString', '-')} "
                f"issued={r.get('issued', '-')} accession={r['identifier'][0]['value']} specimen={r['specimen']['reference']}{note}")
    if t == 'MedicationAdministration':
        return (f"[{i}] {when(r)} ADMIN {r['medicationCodeableConcept']['text']} {r['dosage']['text']} status={r['status']} "
                f"by {r['performer'][0]['actor']['display']} note={r['note'][0]['text']!r}")
    if t == 'MedicationDispense':
        note = ' note=' + repr(r['note'][0]['text']) if r.get('note') else ''
        return (f"[{i}] {when(r)} DISPENSE {r['medicationCodeableConcept']['text']} qty={r['quantity']['value']} "
                f"daysSupply={r['daysSupply']['value']} sig={r['dosageInstruction'][0]['text']!r}{note}")
    if t == 'Condition':
        return f"[{i}] {when(r)} DIAGNOSIS LIST: {r['code']['text']} (recorded by {r['recorder']['display']})"
    if t == 'AllergyIntolerance':
        return f"[{i}] {when(r)} ALLERGY {r['code']['text']}: {r['reaction'][0]['manifestation'][0]['text']}"
    if t == 'Basic':
        return (f"[{i}] {when(r)} ACCESSIONING accession={ext(r, 'accession')} patient={ext(r, 'patient-name')} "
                f"MRN {ext(r, 'patient-mrn')} DOB {ext(r, 'patient-dob')} entered by {r['author']['display']} received={ext(r, 'received')}")
    if t == 'Task':
        return f"[{i}] {r['for']['reference']} {r['focus']['reference']} issue {r['code']['coding'][0]['code']}: {r['description']}"
    if t == 'EpisodeOfCare':
        return f"[{i}] EpisodeOfCare (diagnosis date {r['period']['start']})"
    raise ValueError(t)


def main():
    packet, key_file, selectors = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    fixture = json.loads((TASK / 'environment/service/fixture.json').read_text())
    expected = json.loads((TASK / 'tests/expected.json').read_text())['candidates']
    sources = fixture['sources']
    pid_of = {v['patient_key']: k.split('|')[0] for k, v in expected.items()}
    chosen = []
    for s in selectors:
        keys = [p['key'] for p in PATIENTS if p.get('family') == s.split(':', 1)[1]] if s.startswith('family:') else [s]
        chosen += [pid_of[k] for k in keys]
    allowed, _ = admissible(sources)
    pids = sorted({x for pid in chosen for x in [pid] + [y for y in allowed if y != pid and y in allowed[pid]]})
    by_subject = {}
    for r in sources:
        ref = (r.get('subject') or r.get('patient') or r.get('for') or {}).get('reference', '')
        by_subject.setdefault(ref[8:], []).append(r)
    accessions = {r['identifier'][0]['value'] for pid in pids for r in by_subject.get(pid, []) if r['resourceType'] == 'Observation'}
    patients = {r['id']: r for r in sources if r['resourceType'] == 'Patient'}
    out = [f"Evaluation time {fixture['evaluation_time']}. {len(pids)} patients.\n"]
    for pid in pids:
        p = patients[pid]
        chart = sorted((r for r in by_subject[pid] if r['resourceType'] != 'Task'), key=lambda r: (r['resourceType'] != 'EpisodeOfCare', when(r), r['id']))
        out.append(f"==== PATIENT {pid} {p['name'][0]['text']} ({p['gender']}, DOB {p['birthDate']}, MRN {p['identifier'][0]['value']})")
        out += [line(r) for r in chart] + ['']
    out.append('==== LABORATORY ACCESSIONING LOG (clinic-level; entries for the accessions above)')
    out += sorted(line(r) for r in sources if r['resourceType'] == 'Basic' and ext(r, 'accession') in accessions)
    out += ['', '==== REVIEW REQUESTS (for these patients)']
    out += [line(r) for pid in pids for r in by_subject.get(pid, []) if r['resourceType'] == 'Task']
    packet.mkdir(parents=True, exist_ok=True)
    (packet / 'charts.txt').write_text('\n'.join(out) + '\n')
    for doc in ('instruction.md', 'environment/public/policy.md', 'environment/public/tools.md'):
        shutil.copy(TASK / doc, packet / Path(doc).name)
    key = {}
    for k, v in expected.items():
        pid, _, issue = k.split('|')
        if pid in pids:
            d = SHORT.get(v['disposition']) or 'CD-' + CODES[v['code']]
            key.setdefault(pid, {'patient_key': v['patient_key'], 'answers': {}})['answers'][issue] = d
    key_file.write_text(json.dumps({'fixture_version': fixture['version'], 'issues': list(ISSUES), 'patients': key}, indent=2) + '\n')
    print(f'{len(pids)} patients -> {packet}; key -> {key_file}')


if __name__ == '__main__':
    main()
