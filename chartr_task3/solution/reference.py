"""Private workflow oracle: reads through the public CLI, then saves the authored items through it.

Truth is authored (qa/task3_cases.py) and recomputed by qa/task3_rules.py; independent validation is a
separate reviewer pass, not this script.
"""
import json
import subprocess
from pathlib import Path

ANSWERS = json.loads((Path(__file__).parent / "answers.json").read_text())


def clinic(*args):
    result = subprocess.run(["clinic", *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main():
    patients = clinic("patients")["patients"]
    cohort = {p["patient"]["id"]: {e["id"] for e in p["episodes"]} for p in patients}
    clinic("export", "--dir", "/tmp/export")
    requests = clinic("requests")["requests"]
    for answer in ANSWERS:
        assert answer["episode"] in cohort[answer["patient"]]
        clinic("item", "--json", json.dumps(answer))
    saved = clinic("items")["items"]
    assert len(saved) == len(ANSWERS)
    assert all(any(a["patient"] == r["for"]["reference"].split("/")[1] and a["issue"] == r["code"]["coding"][0]["code"]
                   for a in ANSWERS) for r in requests)


if __name__ == "__main__":
    main()
