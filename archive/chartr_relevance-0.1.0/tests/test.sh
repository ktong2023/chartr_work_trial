#!/bin/sh
set -eu
python /tests/grade.py /evidence/snapshot.json /evidence/attestation.json /logs/verifier
