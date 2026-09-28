"""Private, independent deterministic grading of controller-collected evidence (Task 4).

Components (all required for reward 1; each reported separately):
  1. identification  - exactly the expected set of (patient, category, reason) review items, no extras or duplicates
  2. item_fields     - every structured basis field of every expected item (explanations are not graded)
  3. ecg_findings    - exactly the expected (ECG, finding) set on patients' most recent ECGs, with values in range
  4. ecg_linkage     - diagnostic view: item fields that depend on reading an ECG (subset of 2)
  5. chart_rules     - diagnostic view: follow-up items driven by clinic documents (subset of 1 and 2)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
BASELINE = json.loads((HERE / 'baseline.json').read_text())
EXPECTED = json.loads((HERE / 'expected.json').read_text())


class EvaluationError(ValueError):
    pass


def check_integrity(snapshot, attestation):
    try:
        meta = snapshot['metadata']
        for key in ('trial_id', 'nonce', 'version', 'evaluation_time', 'sources_digest'):
            if not meta[key] or meta[key] != attestation[key]:
                raise EvaluationError('Snapshot does not match controller attestation: ' + key)
        for key in ('version', 'evaluation_time', 'sources_digest'):
            if meta[key] != BASELINE[key]:
                raise EvaluationError('Incorrect source baseline: ' + key)
        if not meta['frozen'] or meta['faults'] != 0:
            raise EvaluationError('Snapshot was not frozen or the service recorded an infrastructure fault')
        state = {'items': [], 'findings': []}
        for seq, event in enumerate(snapshot['audit'], 1):
            if event['seq'] != seq:
                raise EvaluationError('Audit sequence broken')
            if event['status'] >= 500:
                raise EvaluationError('Service failed during evaluation')
            if event['method'] != 'GET':
                if event['before'] != state:
                    raise EvaluationError('Audit state continuity broken')
                if event['status'] != 200 and event['after'] != state:
                    raise EvaluationError('Rejected write changed state')
                state = event['after']
        if {'items': snapshot['items'], 'findings': snapshot['findings']} != state:
            raise EvaluationError('Final state differs from service audit')
    except (KeyError, TypeError) as exc:
        raise EvaluationError('Missing or malformed trusted evidence') from exc


def field_ok(spec, value):
    if 'exact' in spec:
        return value == spec['exact']
    if 'null' in spec:
        return value in (None, [], '')
    if 'one_of' in spec:
        return value in spec['one_of']
    if 'subset_of' in spec:
        return isinstance(value, list) and bool(value) and len(value) == len(set(value)) and set(value) <= set(spec['subset_of'])
    if 'set' in spec:
        return isinstance(value, list) and len(value) == len(set(value)) and set(value) == set(spec['set'])
    if 'range' in spec:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and spec['range'][0] <= value <= spec['range'][1]
    if 'set_one_of' in spec:
        return isinstance(value, list) and len(value) == len(set(value)) and any(set(value) == set(o) for o in spec['set_one_of'])
    if 'cover' in spec:
        allowed = {r for group in spec['cover'] for r in group} | set(spec.get('also', []))
        return (isinstance(value, list) and bool(value) and len(value) == len(set(value)) and set(value) <= allowed
                and all(set(value) & set(group) for group in spec['cover']))
    raise ValueError(spec)


def grade(snapshot, attestation):
    check_integrity(snapshot, attestation)
    items, findings = snapshot['items'], snapshot['findings']
    key = lambda x: (x['patient'], x['category'], x['reason'])
    submitted = [key(i) for i in items]
    expected_keys = [key(i) for i in EXPECTED['items']]
    missing = sorted(set(expected_keys) - set(submitted))
    extra = sorted(set(submitted) - set(expected_keys))
    duplicates = sorted({k for k in submitted if submitted.count(k) > 1})
    per_item, linkage, rules = {}, {}, {}
    for exp in EXPECTED['items']:
        k = key(exp); label = '|'.join(k)
        got = next((i for i in items if key(i) == k), None)
        checks = {'present': got is not None}
        if got is not None:
            for f, spec in exp['fields'].items():
                checks[f] = field_ok(spec, got.get(f))
        per_item[label] = checks
        ecg_dependent = exp.get('ecg_fields', [])
        if ecg_dependent:
            linkage[label] = all(checks.get(f, False) for f in ecg_dependent) and checks['present']
        if exp['category'] == 'FOLLOW_UP':
            rules[label] = all(checks.values())
    fkey = lambda f: (f['ecg'], f['finding'])
    got_f = [fkey(f) for f in findings]
    exp_f = {fkey(f): f for f in EXPECTED['ecg_findings']}
    finding_checks = {}
    for k, exp in exp_f.items():
        got = next((f for f in findings if fkey(f) == k), None)
        c = {'present': got is not None}
        if got is not None:
            c['heart_rate'] = field_ok({'range': exp['heart_rate']}, got.get('heart_rate')) if exp.get('heart_rate') else True
            if exp['finding'] == 'QTC_PROLONGED':
                c['qtc_ms'] = field_ok({'range': exp['qtc_ms']}, got.get('qtc_ms'))
        finding_checks['|'.join(k)] = c
    extra_f = sorted(set(got_f) - set(exp_f))
    dup_f = sorted({k for k in got_f if got_f.count(k) > 1})
    components = {
        'identification': not missing and not extra and not duplicates,
        'item_fields': all(all(c.values()) for c in per_item.values()),
        'ecg_findings': all(all(c.values()) for c in finding_checks.values()) and not extra_f and not dup_f,
        'ecg_linkage': all(linkage.values()),
        'chart_rules': all(rules.values()) and not [e for e in extra if e[1] == 'FOLLOW_UP'],
    }
    reward = int(all(components.values()))
    return {'validity': 'valid', 'reward': reward, 'components': components,
            'identification': {'missing': missing, 'extra': extra, 'duplicates': duplicates},
            'items': per_item, 'ecg_findings': {'checks': finding_checks, 'extra': extra_f, 'duplicates': dup_f},
            'ecg_linkage': linkage, 'chart_rules': rules,
            'narrative_limit': 'Explanations are not graded; structured basis fields carry the reasoning.'}


def main():
    snapshot_path, attestation_path, output = map(Path, sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    for name in ('reward.txt', 'reward.json'):
        (output / name).unlink(missing_ok=True)
    try:
        termination_path = snapshot_path.parent / 'termination.json'
        if termination_path.exists():
            termination = json.loads(termination_path.read_text())
            if termination['validity'] != 'valid':
                raise EvaluationError('Adapter did not complete a valid attempt: ' + termination['reason'])
        result = grade(json.loads(snapshot_path.read_text()), json.loads(attestation_path.read_text()))
    except Exception as exc:
        (output / 'diagnostics.json').write_text(json.dumps({'validity': 'evaluation_error', 'error': str(exc)}, indent=2))
        raise SystemExit(2)  # Never manufacture reward=0 for an invalid evaluation.
    (output / 'diagnostics.json').write_text(json.dumps(result, indent=2))
    (output / 'reward.txt').write_text(str(result['reward']) + '\n')


if __name__ == '__main__':
    main()
