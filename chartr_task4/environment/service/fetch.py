"""Download the pinned PhysioNet files (ODbL v1.0 open datasets) and verify every SHA-256 before use."""
import hashlib, sys, time, urllib.request
from pathlib import Path

BASE = 'https://physionet.org/files/'


def main(pinned, dest):
    dest = Path(dest)
    for line in Path(pinned).read_text().splitlines():
        digest, rel = line.split()
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(BASE + rel, timeout=120) as r:
                    data = r.read()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError('checksum mismatch for ' + rel)
                target.write_bytes(data)
                break
            except Exception as exc:
                if attempt == 4:
                    raise SystemExit(f'failed to fetch {rel}: {exc}')
                time.sleep(3 * (attempt + 1))


if __name__ == '__main__':
    main(*sys.argv[1:3])
