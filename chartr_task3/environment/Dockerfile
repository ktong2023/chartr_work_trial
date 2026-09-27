FROM python:3.13.7-slim-bookworm@sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d
COPY public/clinic.py /usr/local/bin/clinic
COPY public/tools.md public/policy.md /app/
RUN chmod 755 /usr/local/bin/clinic && chmod 644 /app/*.md
WORKDIR /app
