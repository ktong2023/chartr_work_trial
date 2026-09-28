#!/usr/local/bin/python
"""Public clinic CLI (JSON over HTTP). Never retries writes."""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = os.environ.get('CLINIC_URL', 'http://clinic:8000')


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise SystemExit(2 if 400 <= exc.code < 500 else 3)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f'Transport error ({type(exc).__name__}); outcome may be unknown. Inspect saved records before retrying a write.', file=sys.stderr)
        raise SystemExit(3)


def query(**params):
    params = {k: v for k, v in params.items() if v is not None}
    return ('?' + urllib.parse.urlencode(params)) if params else ''


def paged(path, params, every, out):
    page = params.pop('page', None) or 1
    written, first = 0, None
    handle = open(out, 'w') if out else None
    while True:
        result = call('GET', path + query(page=page, **params))
        first = first or result
        if handle:
            for r in result['resources']:
                handle.write(json.dumps(r) + '\n'); written += 1
        elif not every:
            print(json.dumps(result, indent=2)); return
        else:
            print(json.dumps(result, indent=2))
        if not every or result['complete']:
            break
        page += 1
    if handle:
        handle.close()
        print(json.dumps({'type': first['type'], 'total': first['total'], 'pages': first['pages'], 'written': written, 'file': out}))


def main():
    parser = argparse.ArgumentParser(description='Clinic records, clinic documents, ECGs, review items and ECG interpretations')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('patients'); p.add_argument('--page', type=int)
    s = sub.add_parser('search'); s.add_argument('type')
    for opt in ('--patient', '--since', '--until', '--code', '--out'):
        s.add_argument(opt)
    s.add_argument('--page', type=int); s.add_argument('--all', action='store_true')
    d = sub.add_parser('documents'); d.add_argument('--out')
    e = sub.add_parser('ecg'); esub = e.add_subparsers(dest='action', required=True)
    el = esub.add_parser('list'); el.add_argument('--patient')
    ef = esub.add_parser('fetch'); ef.add_argument('ecg'); ef.add_argument('--dir', required=True)
    for kind in ('items', 'interpretations'):
        k = sub.add_parser(kind); k.add_argument('--patient')
    for kind in ('item', 'interpretation'):
        k = sub.add_parser(kind); ksub = k.add_subparsers(dest='action', required=True)
        add = ksub.add_parser('add'); add.add_argument('--json', required=True)
        upd = ksub.add_parser('update'); upd.add_argument('id'); upd.add_argument('--json', required=True)
    a = parser.parse_args()
    if a.command == 'patients':
        print(json.dumps(call('GET', '/patients' + query(page=a.page)), indent=2))
    elif a.command == 'search':
        paged('/search', {'type': a.type, 'patient': a.patient, 'since': a.since, 'until': a.until, 'code': a.code, 'page': a.page}, a.all, a.out)
    elif a.command == 'documents':
        paged('/documents', {}, True, a.out)
    elif a.command == 'ecg' and a.action == 'list':
        print(json.dumps(call('GET', '/ecg' + query(patient=a.patient)), indent=2))
    elif a.command == 'ecg':
        result = call('GET', '/ecg/' + urllib.parse.quote(a.ecg))
        target = Path(a.dir); target.mkdir(parents=True, exist_ok=True)
        for name, data in result['files'].items():
            (target / name).write_bytes(base64.b64decode(data))
        print(json.dumps({'ecg': result['ecg'], 'patient': result['patient'], 'time': result['time'],
                          'files': sorted(str(target / n) for n in result['files'])}))
    elif a.command in ('items', 'interpretations'):
        print(json.dumps(call('GET', '/' + a.command + query(patient=a.patient)), indent=2))
    else:
        try:
            body = json.loads(a.json)
        except ValueError as exc:
            parser.error(str(exc))
        path = '/' + a.command + 's'
        if a.action == 'update':
            print(json.dumps(call('PATCH', path + '/' + urllib.parse.quote(a.id), body), indent=2))
        else:
            print(json.dumps(call('POST', path, body), indent=2))


if __name__ == '__main__':
    main()
