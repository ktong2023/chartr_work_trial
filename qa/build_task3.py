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
from task3_cases import ISSUES  # noqa: E402
from task3_cohort import EXTERNALS, PATIENTS  # noqa: E402
import task3_rules  # noqa: E402

SALT = 'task3-v1'
ROLE_TIME = {'clinician': 'Electronically signed: {}', 'nurse': 'Signed: {}', 'pharmacist': 'Verified: {}',
             'registration': 'Entered by: {}', 'laboratory': 'Released by: {}'}
LABTECH = ['R. Chen, MLS', 'M. Ortiz, MLS', 'K. Dube, MLT', 'S. Walsh, MLS', 'J. Ferris, MLT']
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
    people.update(EXTERNALS)
    assert len({v['mrn'] for v in people.values()}) == len(people), 'MRN collision'
    accessions = set()

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

        def lab(n, r, code, value, status='final', comment=None, owner=None, accession_owner=None, label_name=None, collector=None,
                accessioner=None):
            """Observation in this chart; its specimen record goes to the chart of the patient it was labeled for."""
            day = r[1]
            owner = owner or key
            who = people[owner]
            # One accession number per specimen: a repeated number would join unrelated specimens (0.2.0 defect).
            for i in range(1000):
                salt = (str(i),) if i else ()
                accession = 'A' + day[2:4] + day[5:7] + '-' + str(int(h('acc', key, str(n), *salt)[:6], 16) % 9000 + 1000)
                if accession not in accessions:
                    break
            accessions.add(accession)
            spec = add('Specimen', f'{n}s', day, people[owner]['pid'], '1000',
                       accessionIdentifier={'value': accession}, type={'text': 'Serum' if 'hCG' not in code else 'Serum (hCG)'},
                       collection={'collectedDateTime': stamp(day, '1000'), 'collector': {'display': collector or COLLECTORS[int(h('col', key, str(n))[:4], 16) % len(COLLECTORS)]}})
            spec['extension'] += [extension('label-name', 'String', label_name or who['name']),
                                  extension('label-mrn', 'String', who['mrn']), extension('label-dob', 'Date', who['dob'])]
            acc_who = people[accession_owner or owner]
            acc = {'resourceType': 'Basic', 'id': rid(key, str(n), 'accession'), 'code': {'text': 'Laboratory accessioning'},
                   'created': plus(day, 0),
                   'author': {'display': accessioner or LABTECH[int(h('acc-by', key, str(n))[:4], 16) % len(LABTECH)]},
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
                    opts.get('accession_owner'), opts.get('label_name'), opts.get('collector'), opts.get('accessioner'))
            elif kind == 'trep':
                lab(n, r, 'Treponema pallidum antibody (TP-PA)', r[2].capitalize())
            elif kind == 'hcg':
                opts = r[3]
                ident = (opts.get('owner'), opts.get('accession_owner'), opts.get('label_name'), opts.get('collector'), opts.get('accessioner'))
                if r[2] is None:
                    lab(n, r, 'hCG, serum quantitative', None, 'registered', opts.get('comment'), *ident)
                else:
                    lab(n, r, 'hCG, serum', r[2].capitalize(), 'final', None, *ident)
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

    check_follow_up_after_seroreversion()
    sources.sort(key=lambda r: r['id'])
    for r in sources:
        validate(r)
        when = next((e['valueDateTime'] for e in r.get('extension', []) if e['url'].endswith('/event-time')), NOW)
        assert when <= NOW, ('record dated after the evaluation time', r['id'], when)
    assert len(sources) == len({r['id'] for r in sources})
    by_id = {r['id']: r for r in sources}
    for r in sources:
        pid = (r.get('subject') or r.get('patient') or {}).get('reference', '/').split('/')[1]
        if pid:
            charts.setdefault(pid, []).append(r['id'])
    charts = {k: v for k, v in charts.items() if k.startswith('P')}
    check_rendered_identity(sources, people)

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
    return fixture, {'candidates': expected, 'charts': charts}, answers


def check_follow_up_after_seroreversion():
    """No answer may depend on a missed follow-up window that comes after a nonreactive follow-up RPR: CDC 2021 has no
    seroreversion exception, but some clinicians stop testing once the RPR is nonreactive (independent review, 0.2.1)."""
    for p in PATIENTS:
        own = [r for r in p['records'] if r[0] == 'rpr' and r[3].get('owner', p['key']) == p['key']] + task3_rules.CROSS.get(p['key'], [])
        for world in (p['unknown']['options'].values() if p.get('unknown') else [{}]):
            f = task3_rules.facts(p, 'full', [world])
            anchor, missed = task3_rules.missed_windows(f)
            for m, start, _ in missed:
                earlier = [r[1] for r in own if r[2] == 'NR' and r[3].get('status', 'final') == 'final'
                           and r[1] not in f['fu_drop'] and anchor <= dt.date.fromisoformat(r[1]) < start]
                assert not earlier, (p['key'], f'{m}-month window missed after nonreactive follow-up', earlier)


def ext(r, name):
    return next(v for e in r.get('extension', []) if e['url'].endswith('/' + name) for k, v in e.items() if k.startswith('value'))


def check_rendered_identity(sources, people):
    """Rebuild every laboratory result's identity from the rendered records alone, the way tools.md and policy.md
    describe it (accession number -> the specimen's collection record and the accessioning entry, each naming a
    patient by MRN and DOB), and refuse to build unless it matches the facts the rules engine reads. The engine
    reads generator facts, so it cannot see rendering defects such as the 0.2.0 accession-number collisions."""
    who = {(v['mrn'], v['dob']): k for k, v in people.items()}
    key_of = {v['pid']: k for k, v in people.items() if 'pid' in v}
    registration = {}
    for r in sources:
        if r['resourceType'] == 'DocumentReference' and r['type']['text'] == 'Registration update':
            registration.setdefault(key_of[r['subject']['reference'][8:]], []).append(r['description'])
    groups = {}
    for r in sources:
        kind = r['resourceType']
        if kind in ('Observation', 'Specimen', 'Basic'):
            accession = (r['identifier'][0]['value'] if kind == 'Observation' else
                         r['accessionIdentifier']['value'] if kind == 'Specimen' else ext(r, 'accession'))
            groups.setdefault(accession, {}).setdefault(kind, []).append(r)
    results = []    # (filed, label, accessioned, code, date, status, value)
    for accession, group in groups.items():
        assert {k: len(v) for k, v in group.items()} == {'Observation': 1, 'Specimen': 1, 'Basic': 1}, ('accession not unique', accession)
        obs, spec, entry = group['Observation'][0], group['Specimen'][0], group['Basic'][0]
        assert obs['specimen']['reference'] == 'Specimen/' + spec['id'], accession
        label = who[(ext(spec, 'label-mrn'), ext(spec, 'label-dob'))]
        accessioned = who[(ext(entry, 'patient-mrn'), ext(entry, 'patient-dob'))]
        assert spec['subject']['reference'] == 'Patient/' + people[label]['pid'], ('specimen filed away from its label', accession)
        for name, person in ((ext(spec, 'label-name'), label), (ext(entry, 'patient-name'), accessioned)):
            former = name.split(',')[0].title()
            assert name == people[person]['name'] or any(former in t for t in registration.get(person, [])), ('undocumented name', accession)
        status = {'final': 'final', 'registered': 'pending', 'cancelled': 'rejected'}[obs['status']]
        results.append((key_of[obs['subject']['reference'][8:]], label, accessioned, obs['code']['text'],
                        obs['effectiveDateTime'][:10], status, obs.get('valueString')))
    for p in PATIENTS:
        key, f = p['key'], task3_rules.derived(p)
        # A result filed here that both identifiers give to someone else is misfiled.
        assert any(x[0] == key and x[1] == x[2] != key for x in results) == f['misfiled'], (key, 'misfiled')
        # Follow-up candidates are the RPR specimens labeled for this patient, wherever they are filed.
        assert sorted(x[4:6] for x in results if x[1] == key and x[3].startswith('RPR')) == sorted(f['fu']), (key, 'follow-up specimens')
        # Every identity conflict naming this patient is a modeled uncertainty (or resolved by a correction).
        if any(key in x[1:3] and x[1] != x[2] for x in results):
            assert 'conflict' in p['gaps'], (key, 'unmodeled identity conflict')
        # A positive pregnancy test that is unambiguously this patient's means she was pregnant.
        if any(x[1] == x[2] == key and x[3].startswith('hCG') and x[6] == 'Positive' for x in results):
            assert p['facts'].get('pregnant') is True, (key, 'positive hCG but not pregnant')


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
