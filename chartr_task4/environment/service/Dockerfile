FROM python:3.13.7-slim-bookworm@sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d AS data
# Build-time data: pinned PhysioNet files (checksum-verified) + the task overlay, assembled into a read-only database.
RUN pip install --no-cache-dir tzdata==2026.4
COPY fetch.py overlay/pinned.sha256 /build/
RUN python /build/fetch.py /build/pinned.sha256 /src
COPY assemble.py /build/
COPY overlay /build/overlay
RUN python /build/assemble.py /src/mimic-iv-fhir-demo/2.1.0/fhir /src/mimic-iv-ecg-demo/0.1 /build/overlay /data/sources.sqlite /data/ecg \
 && chmod -R a-w /data

FROM python:3.13.7-slim-bookworm@sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d
RUN pip install --no-cache-dir tzdata==2026.4
COPY --from=data /data /data
COPY store.py server.py control.py /app/
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
CMD ["python", "/app/server.py"]
