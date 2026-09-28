"""Private, independent deterministic grading of controller-collected evidence (Task 4).

Components (all required for reward 1; each reported separately):
  1. identification  - exactly the expected set of (patient, category, reason) review items, no extras or duplicates
  2. item_fields     - every structured basis field of every expected item (explanations are not graded)
  3. ecg_interpretation - one interpretation per living patient, of that patient's most recent ECG (deceased patients'
                          latest ECGs are optional); rhythm, rate, intervals,
                          axis and conduction within the reader-agreement specs (fields where readers disagree accept any value)
  4. ecg_comparison  - each interpretation's prior ECG and change list
  5. ecg_linkage     - diagnostic view: item fields that depend on reading an ECG (subset of 2)
  6. chart_rules     - diagnostic view: follow-up items driven by clinic documents (subset of 1 and 2)
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
        state = {'items': [], 'interpretations': []}
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
        if {'items': snapshot['items'], 'interpretations': snapshot['interpretations']} != state:
            raise EvaluationError('Final state differs from service audit')
    except (KeyError, TypeError) as exc:
        raise EvaluationError('Missing or malformed trusted evidence') from exc


def field_ok(spec, value):
    if 'any' in spec:
        return True
    if 'required' in spec:   # list containing every required value and nothing outside required + allowed
        return (isinstance(value, list) and len(value) == len(set(value)) and set(spec['required']) <= set(value)
                <= set(spec['required']) | set(spec['allowed']))
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
    items = snapshot['items']
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
    interps = snapshot['interpretations']
    exp_i = {e['ecg']: e for e in EXPECTED['interpretations']}
    got_ecgs = [i['ecg'] for i in interps]
    interp_checks, comparison_checks = {}, {}
    for ecg, exp in exp_i.items():
        got = next((i for i in interps if i['ecg'] == ecg), None)
        c = {'present': got is not None}
        if got is not None:
            for f, spec in exp['fields'].items():
                c[f] = field_ok(spec, got.get(f))
            comparison_checks[exp['subject'] + '|' + ecg] = {'prior_ecg': got.get('prior_ecg') == exp['prior_ecg'],
                                                             'changes': field_ok(exp['changes'], got.get('changes'))}
        else:
            comparison_checks[exp['subject'] + '|' + ecg] = {'present': False}
        interp_checks[exp['subject'] + '|' + ecg] = c
    extra_i = sorted(set(got_ecgs) - set(exp_i) - set(EXPECTED.get('optional_interpretations', [])))
    dup_i = sorted({e for e in got_ecgs if got_ecgs.count(e) > 1})
    components = {
        'identification': not missing and not extra and not duplicates,
        'item_fields': all(all(c.values()) for c in per_item.values()),
        'ecg_interpretation': all(all(c.values()) for c in interp_checks.values()) and not extra_i and not dup_i,
        'ecg_comparison': all(all(c.values()) for c in comparison_checks.values()),
        'ecg_linkage': all(linkage.values()),
        'chart_rules': all(rules.values()) and not [e for e in extra if e[1] == 'FOLLOW_UP'],
    }
    reward = int(all(components.values()))
    return {'validity': 'valid', 'reward': reward, 'components': components,
            'identification': {'missing': missing, 'extra': extra, 'duplicates': duplicates},
            'items': per_item, 'ecg_interpretation': {'checks': interp_checks, 'extra': extra_i, 'duplicates': dup_i},
            'ecg_comparison': comparison_checks,
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
