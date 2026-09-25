"""Create an unrelated minimal task; exercise real Harbor sidecar transfer."""
import pathlib
import subprocess
import tempfile
import os
import json
import time

BASE = "python:3.13.7-slim-bookworm@sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d"
ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="chartr-transfer-") as directory:
        task = pathlib.Path(directory)
        files = {
            "instruction.md": "Set the counter to 7 through the service.",
            "task.toml": '''schema_version = "1.4"
artifacts = [{source="/evidence/snapshot.json",service="clinic"}]
[task]
name = "chartr/transfer-smoke"
version = "0.1.0"
[environment]
network_mode = "public"
[agent]
timeout_sec = 60
[verifier]
environment_mode = "separate"
timeout_sec = 60
[[verifier.collect]]
service = "clinic"
command = "mkdir -p /evidence && cp /state.json /evidence/snapshot.json"
[verifier.environment]
network_mode = "public"
''',
            "environment/Dockerfile": f"FROM {BASE}\nWORKDIR /app\n",
            "environment/docker-compose.yaml": f'''services:
  main:
    networks: [clinic]
    depends_on: [clinic]
  clinic:
    build:
      context: .
      dockerfile: Service.Dockerfile
    networks: [clinic]
networks:
  clinic:
    internal: true
''',
            "environment/Service.Dockerfile": f"FROM {BASE}\nCOPY server.py /server.py\nCMD [\"python\", \"/server.py\"]\n",
            "environment/server.py": '''from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
Path('/state.json').write_text('{"counter":0}')
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        Path('/state.json').write_text('{"counter":7}')
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
HTTPServer(('0.0.0.0',8000),H).serve_forever()
''',
            "solution/solve.sh": '''#!/bin/sh
set -eu
mkdir -p /evidence
echo '{"counter":999}' > /evidence/snapshot.json
python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://clinic:8000',data=b''))"
''',
            "tests/Dockerfile": f"FROM {BASE}\nCOPY test.sh /tests/test.sh\n",
            "tests/test.sh": '''#!/bin/sh
set -eu
python -c 'import json; assert json.load(open("/evidence/snapshot.json")) == {"counter":7}'
echo 1 > /logs/verifier/reward.txt
''',
        }
        for name, content in files.items():
            path = task / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        job_name = f"transfer-smoke-{time.time_ns()}"
        jobs_dir = ROOT / "jobs/chartr"
        subprocess.run([str(ROOT / ".venv/bin/harbor"), "run", "-p", directory,
                        "-a", "oracle", "-e", "chartr_environment:ChartREnvironment",
                        "--job-name", job_name, "--jobs-dir", str(jobs_dir), "--debug"],
                       cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, check=True)
        result = json.loads(next((jobs_dir / job_name).glob("*/result.json")).read_text())
        assert result["exception_info"] is None, result
        assert result["verifier_result"]["rewards"]["reward"] == 1, result
        print("Trusted counter 7 reached separate verifier; agent forgery 999 ignored.")


if __name__ == "__main__":
    main()
