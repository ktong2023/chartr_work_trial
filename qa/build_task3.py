"""Render the Task 3 cohort (qa/task3_cases.py) as limited FHIR R4 records, plus private answers.

Writes environment/service/fixture.json (public through the API), tests/baseline.json and
tests/expected.json (private verifier) and solution/answers.json (oracle only). Truth comes from the
authored cases and must equal qa/task3_rules.py's recomputation; the build refuses otherwise.
"""
import base64
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_task3'
sys.path[:0] = [str(TASK / 'environment/service'), str(ROOT / 'qa')]
from fhir import BASE, NOW, VERSION, concept, digest, extension, validate  # noqa: E402
from task3_cases import EXTERNAL, ISSUES, PATIENTS  # noqa: E402
import task3_rules  # noqa: E402

SALT = 'task3-v1'
ROLE_TIME = {'clinician': 'Electronically signed: {}', 'nurse': 'Signed: {}', 'pharmacist': 'Verified: {}',
             'registration': 'Entered by: {}'}
RESULT_TIME = '1600'
COLLECTORS = ['Clinic phlebotomy', 'Ana Ruiz, RN', 'Jordan Lee, RN', 'Mina Cho, RN', 'Sam Okafor, LPN', 'T. Brandt, phlebotomist']


def h(*parts):
    return hashlib.sha256((SALT + ':' + ':'.join(parts)).encode()).hexdigest()


def rid(*parts):
    return 'R' + h(*parts)[:12]


def mrn(key):
    return str(int(h('mrn', key)[:10], 16) % 90000000 + 10000000)


def stamp(day, hhmm='0900'):
    return f'{day}T{hhmm[:2]}:{hhmm[2:]}:00Z'


def plus(day, n):
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


def label(name):
    first, last = name.split(' ', 1)
    return f'{last.upper()}, {first.upper()}'


def build():
    sources, episodes, charts, expected, answers = [], {}, {}, {}, []
    people = {p['key']: {'pid': 'P' + h('patient', p['key'])[:7], 'mrn': mrn(p['key']), 'dob': p['dob'],
                         'name': label(p['name'])} for p in PATIENTS}
    people['EXTERNAL'] = EXTERNAL
    linked = {}

    for p in PATIENTS:
        key, me = p['key'], people[p['key']]
        pid, eid = me['pid'], 'E' + h('episode', key)[:7]
        episodes[pid] = [eid]
        sources.append({'resourceType': 'Patient', 'id': pid, 'name': [{'text': p['name']}], 'gender': p['sex'],
                        'birthDate': p['dob'], 'identifier': [{'system': BASE + '/mrn', 'value': me['mrn']}]})
        sources.append({'resourceType': 'EpisodeOfCare', 'id': eid, 'status': 'active', 'patient': {'reference': 'Patient/' + pid},
                        'type': [{'text': 'Syphilis'}], 'period': {'start': p['dx']}})
        charts[key] = []

        def add(kind, n, day, chart_pid, hhmm='0900', **attrs):
            ref = 'patient' if kind == 'AllergyIntolerance' else 'subject'
            r = {'resourceType': kind, 'id': rid(key, str(n), kind), ref: {'reference': 'Patient/' + chart_pid},
                 'extension': [extension('event-time', 'DateTime', stamp(day, hhmm))], **attrs}
            sources.append(r)
            return r

        def lab(n, r, code, value, status='final', comment=None, owner=None, accession_owner=None, label_name=None, collector=None):
            """Observation in this chart; its specimen record goes to the chart of the patient it was labeled for."""
            day = r[1]
            owner = owner or key
            who = people[owner]
            accession = 'A' + day[2:4] + day[5:7] + '-' + str(int(h('acc', key, str(n))[:6], 16) % 9000 + 1000)
            spec = add('Specimen', f'{n}s', day, people[owner]['pid'], '1000',
                       accessionIdentifier={'value': accession}, type={'text': 'Serum' if 'hCG' not in code else 'Serum (hCG)'},
                       collection={'collectedDateTime': stamp(day, '1000'), 'collector': {'display': collector or COLLECTORS[int(h('col', key, str(n))[:4], 16) % len(COLLECTORS)]}})
            spec['extension'] += [extension('label-name', 'String', label_name or who['name']),
                                  extension('label-mrn', 'String', who['mrn']), extension('label-dob', 'Date', who['dob'])]
            acc_who = people[accession_owner or owner]
            acc = {'resourceType': 'Basic', 'id': rid(key, str(n), 'accession'), 'code': {'text': 'Laboratory accessioning'},
                   'created': plus(day, 0),
                   'extension': [extension('event-time', 'DateTime', stamp(day, '1300')),
                                 extension('accession', 'String', accession),
                                 extension('patient-name', 'String', label_name or acc_who['name']),
                                 extension('patient-mrn', 'String', acc_who['mrn']),
                                 extension('patient-dob', 'Date', acc_who['dob']),
                                 extension('received', 'DateTime', stamp(day, '1300'))]}
            sources.append(acc)
            obs = add('Observation', n, day, pid, RESULT_TIME, status=status, code={'text': code},
                      effectiveDateTime=stamp(day, '1000'), specimen={'reference': 'Specimen/' + spec['id']},
                      identifier=[{'system': BASE + '/accession', 'value': accession}])
            if status in ('final', 'corrected'):
                obs['issued'] = stamp(plus(day, 1), '0800')
                obs['valueString'] = value
            if comment:
                obs['note'] = [{'text': comment}]
            if owner != key:
                linked.setdefault(pid, []).extend([spec['id'], acc['id']])
                linked.setdefault(people[owner]['pid'], []).extend([obs['id'], acc['id']])
            if accession_owner:
                linked.setdefault(pid, []).append(acc['id'])
            return obs

        for n, r in enumerate(p['records']):
            kind, day = r[0], r[1]
            if kind == 'note':
                _, _, hhmm, role, author, doc_type, text = r
                text = text + '\n\n' + ROLE_TIME[role].format(author)
                d = add('DocumentReference', n, day, pid, hhmm, status='current', docStatus='final',
                        type={'text': doc_type}, date=stamp(day, hhmm), author=[{'display': author}],
                        authenticator={'display': author}, description=text,
                        content=[{'attachment': {'contentType': 'text/plain', 'data': base64.b64encode(text.encode()).decode()}}])
                d['extension'].append(extension('author-role', 'Code', role))
            elif kind == 'outside':
                _, _, facility, text = r
                d = add('DocumentReference', n, day, pid, '1400', status='current', docStatus='final',
                        type={'text': 'Outside records (scanned)'}, date=stamp(day, '1400'), author=[{'display': facility}],
                        description=text,
                        content=[{'attachment': {'contentType': 'text/plain', 'data': base64.b64encode(text.encode()).decode()}}])
                d['extension'].append(extension('author-role', 'Code', 'outside-facility'))
            elif kind == 'condition':
                _, _, text, recorder = r
                add('Condition', n, day, pid, '1200', code={'text': text}, recordedDate=stamp(day, '1200'),
                    recorder={'display': recorder}, category=[{'text': 'Diagnosis list'}])
            elif kind == 'allergy':
                _, _, substance, reaction = r
                add('AllergyIntolerance', n, day, pid, code={'text': substance}, recordedDate=stamp(day),
                    reaction=[{'manifestation': [{'text': reaction}]}])
            elif kind == 'rpr':
                opts = r[3]
                status = {'final': 'final', 'pending': 'registered', 'rejected': 'cancelled'}[opts.get('status', 'final')]
                if opts.get('status') is None and r[2] is None:
                    raise ValueError(r)
                value = None if r[2] is None else ('Nonreactive' if r[2] == 'NR' else 'Reactive ' + r[2])
                lab(n, r, 'RPR, quantitative', value, status, opts.get('comment'), opts.get('owner'),
                    opts.get('accession_owner'), opts.get('label_name'), opts.get('collector'))
            elif kind == 'trep':
                lab(n, r, 'Treponema pallidum antibody (TP-PA)', r[2].capitalize())
            elif kind == 'hcg':
                opts = r[3]
                if r[2] is None:
                    lab(n, r, 'hCG, serum quantitative', None, 'registered', opts.get('comment'))
                else:
                    lab(n, r, 'hCG, serum', r[2].capitalize())
            elif kind == 'lab':
                lab(n, r, r[2], r[3])
            elif kind == 'bpg':
                _, _, dose, performer, comment = r
                add('MedicationAdministration', n, day, pid, '1100', status='completed',
                    medicationCodeableConcept={'text': 'Bicillin L-A (benzathine penicillin G)'}, effectiveDateTime=stamp(day, '1100'),
                    performer=[{'actor': {'display': performer}}], dosage={'text': dose}, note=[{'text': comment}])
            elif kind == 'med':
                _, _, drug, dose, performer, comment, status = r
                add('MedicationAdministration', n, day, pid, '1100', status=status, medicationCodeableConcept={'text': drug},
                    effectiveDateTime=stamp(day, '1100'), performer=[{'actor': {'display': performer}}],
                    dosage={'text': dose}, note=[{'text': comment}])
            elif kind == 'dispense':
                _, _, drug, qty, days, sig, note = r
                d = add('MedicationDispense', n, day, pid, '1300', status='completed', medicationCodeableConcept={'text': drug},
                        quantity={'value': qty}, daysSupply={'value': days}, whenHandedOver=stamp(day, '1300'),
                        dosageInstruction=[{'text': sig}])
                if note:
                    d['note'] = [{'text': note}]
            else:
                raise ValueError(kind)

        for issue, text in p['requests'].items():
            sources.append({'resourceType': 'Task', 'id': rid(key, issue, 'request'), 'status': 'requested', 'intent': 'order',
                            'code': concept('audit-issue', issue), 'for': {'reference': 'Patient/' + pid},
                            'focus': {'reference': 'EpisodeOfCare/' + eid}, 'authoredOn': '2026-09-2' + str(int(h(key, issue)[:2], 16) % 3) + 'T09:00:00Z',
                            'description': text, 'requester': {'display': 'Quality & Safety Committee'}})

        truth = task3_rules.disposition(p)
        for issue in ISSUES:
            want = p['truth'].get(issue, ('not_an_issue', None))
            if truth[issue] != want:
                raise SystemExit(f'{key} {issue}: authored {want} but rules give {truth[issue]}')
            kind = p['kinds'].get(issue, 'control' if want[0] == 'not_an_issue' else 'real')
            expected[f'{pid}|{eid}|{issue}'] = {'patient_key': key, 'disposition': want[0], 'code': want[1],
                                                'kind': kind, 'requested': issue in p['requests']}

    sources.sort(key=lambda r: r['id'])
    for r in sources:
        validate(r)
    assert len(sources) == len({r['id'] for r in sources})
    by_id = {r['id']: r for r in sources}
    for r in sources:
        pid = (r.get('subject') or r.get('patient') or {}).get('reference', '/').split('/')[1]
        if pid:
            charts.setdefault(pid, []).append(r['id'])
    charts = {k: v for k, v in charts.items() if k.startswith('P')}

    # Oracle submissions: every non-silent candidate plus every requested one, citing chart records.
    evidence_kinds = {'INADEQUATE_TREATMENT': ('MedicationAdministration', 'MedicationDispense', 'Condition'),
                      'FOLLOW_UP_OVERDUE': ('Observation',), 'MISFILED_RESULT': ('Observation', 'Specimen'),
                      'PREGNANCY_TREATMENT_INADEQUATE': ('DocumentReference', 'MedicationAdministration')}
    for k, e in expected.items():
        if e['disposition'] == 'not_an_issue' and not e['requested']:
            continue
        pid, eid, issue = k.split('|')
        cited = [x for x in charts[pid] if by_id[x]['resourceType'] in evidence_kinds[issue]][:8] or charts[pid][:3]
        answers.append({'patient': pid, 'episode': eid, 'issue': issue, 'disposition': e['disposition'],
                        'missing_evidence': e['code'], 'evidence': cited, 'explanation': 'Reference determination.'})
    fixture = {'version': VERSION, 'evaluation_time': NOW, 'episodes': episodes, 'sources': sources}
    return fixture, {'candidates': expected, 'charts': charts, 'linked': linked}, answers


def main():
    fixture, expected, answers = build()
    (TASK / 'environment/service/fixture.json').write_text(json.dumps(fixture, indent=2) + '\n')
    (TASK / 'tests/expected.json').write_text(json.dumps(expected, indent=2) + '\n')
    (TASK / 'solution/answers.json').write_text(json.dumps(answers, indent=2) + '\n')
    (TASK / 'tests/baseline.json').write_text(json.dumps({
        'version': VERSION, 'evaluation_time': NOW, 'initial_digest': digest(fixture),
        'sources_digest': digest(fixture['sources'])}, indent=2) + '\n')
    c = expected['candidates'].values()
    print('Built', len(fixture['episodes']), 'patients;', len(fixture['sources']), 'resources;', len(expected['candidates']),
          'candidates;', sum(x['disposition'] == 'confirmed' for x in c), 'confirmed;',
          sum(x['disposition'] == 'cannot_determine' for x in c), 'cannot_determine;', sum(x['requested'] for x in c), 'requested')


if __name__ == '__main__':
    main()
