#!/usr/local/bin/python
"""Public JSON CLI. Never retries writes."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Clinic records and persistent treatment-review queue")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("patients")
    commands.add_parser("records").add_argument("patient")
    commands.add_parser("reviews").add_argument("--patient")
    commands.add_parser("create").add_argument("--json", required=True)
    update = commands.add_parser("update")
    update.add_argument("item")
    update.add_argument("--json", required=True)
    args = parser.parse_args()
    method, body = "GET", None
    path = {"patients": "/patients", "records": "/records/" + (getattr(args, "patient", "") or ""),
            "reviews": "/reviews"}.get(args.command, "/reviews")
    if args.command == "reviews" and args.patient:
        path += "/" + args.patient
    if args.command in {"create", "update"}:
        try:
            body = json.dumps(json.loads(args.json)).encode()
        except ValueError as exc:
            parser.error(str(exc))
        method = "POST" if args.command == "create" else "PATCH"
        if args.command == "update":
            path += "/" + args.item
    request = urllib.request.Request(os.environ.get("CLINIC_URL", "http://clinic:8000") + path,
                                     data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(json.dumps(json.load(response), indent=2))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise SystemExit(2 if 400 <= exc.code < 500 else 3)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"Transport error ({type(exc).__name__}); outcome may be unknown. Inspect queue before retrying a write.", file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
