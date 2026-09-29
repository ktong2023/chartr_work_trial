"""Controller-only Docker exec entry point; never exposed over HTTP."""
import json
import sys
import urllib.request
from pathlib import Path
from store import Store

store = Store("/state/clinic.sqlite")
if sys.argv[1] == "attest":
    with urllib.request.urlopen("http://localhost:8000/health", timeout=5) as response:
        assert json.load(response)["ready"]
    print(json.dumps(store.attest(sys.argv[2])))
elif sys.argv[1] == "collect":
    with urllib.request.urlopen("http://localhost:8000/health", timeout=15) as response:
        assert json.load(response)["ready"]
    snapshot = store.collect()
    directory = Path("/evidence")
    directory.mkdir(exist_ok=True)
    temporary = directory / "snapshot.tmp"
    temporary.write_text(json.dumps(snapshot, indent=2))
    temporary.replace(directory / "snapshot.json")
else:
    raise SystemExit("Unknown controller command")
