#!/usr/local/bin/python
"""Public JSON CLI. Never retries writes."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def call(method, path, body=None):
    request = urllib.request.Request(os.environ.get("CLINIC_URL", "http://clinic:8000") + path, data=body,
                                     method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise SystemExit(2 if 400 <= exc.code < 500 else 3)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"Transport error ({type(exc).__name__}); outcome may be unknown. Inspect items before retrying a write.", file=sys.stderr)
        raise SystemExit(3)


def main():
    parser = argparse.ArgumentParser(description="Clinic records and audit items")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("patients")
    commands.add_parser("records").add_argument("patient")
    commands.add_parser("export").add_argument("--dir", default="export")
    commands.add_parser("requests")
    commands.add_parser("items").add_argument("--patient")
    commands.add_parser("item").add_argument("--json", required=True)
    update = commands.add_parser("update-item")
    update.add_argument("item")
    update.add_argument("--json", required=True)
    args = parser.parse_args()
    body = None
    if args.command in {"item", "update-item"}:
        try:
            body = json.dumps(json.loads(args.json)).encode()
        except ValueError as exc:
            parser.error(str(exc))
    if args.command == "export":
        data = call("GET", "/export")
        out = Path(args.dir)
        out.mkdir(parents=True, exist_ok=True)
        counts = {}
        for resource in data["resources"]:
            counts[resource["resourceType"]] = counts.get(resource["resourceType"], 0) + 1
        for kind in counts:
            with (out / f"{kind}.ndjson").open("w") as handle:
                for resource in data["resources"]:
                    if resource["resourceType"] == kind:
                        handle.write(json.dumps(resource) + "\n")
        manifest = {"complete": data["complete"], "evaluation_time": data["evaluation_time"], "counts": counts}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps({"directory": str(out.resolve()), **manifest}, indent=2))
        return
    method, path = {"patients": ("GET", "/patients"), "requests": ("GET", "/requests"),
                    "item": ("POST", "/items")}.get(args.command, ("GET", ""))
    if args.command == "records":
        path = "/records/" + args.patient
    elif args.command == "items":
        path = "/items" + ("/" + args.patient if args.patient else "")
    elif args.command == "update-item":
        method, path = "PATCH", "/items/" + args.item
    print(json.dumps(call(method, path, body), indent=2))


if __name__ == "__main__":
    main()
