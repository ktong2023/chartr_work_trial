#!/usr/local/bin/python
"""Public JSON CLI. Never retries writes."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Clinic records and follow-up determinations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("patients")
    commands.add_parser("records").add_argument("patient")
    commands.add_parser("history")
    commands.add_parser("determinations").add_argument("--patient")
    commands.add_parser("determine").add_argument("--json", required=True)
    update = commands.add_parser("redetermine")
    update.add_argument("determination")
    update.add_argument("--json", required=True)
    args = parser.parse_args()
    method, body = "GET", None
    path = {"patients": "/patients", "records": "/records/" + (getattr(args, "patient", "") or ""),
            "history": "/history"}.get(args.command, "/determinations")
    if args.command == "determinations" and args.patient:
        path += "/" + args.patient
    if args.command in {"determine", "redetermine"}:
        try:
            body = json.dumps(json.loads(args.json)).encode()
        except ValueError as exc:
            parser.error(str(exc))
        method = "POST" if args.command == "determine" else "PATCH"
        if args.command == "redetermine":
            path += "/" + args.determination
    request = urllib.request.Request(os.environ.get("CLINIC_URL", "http://clinic:8000") + path,
                                     data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(json.dumps(json.load(response), indent=2))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise SystemExit(2 if 400 <= exc.code < 500 else 3)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"Transport error ({type(exc).__name__}); outcome may be unknown. Inspect determinations before retrying a write.", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
