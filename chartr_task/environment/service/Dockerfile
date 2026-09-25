FROM python:3.13.7-slim-bookworm@sha256:adafcc17694d715c905b4c7bebd96907a1fd5cf183395f0ebc4d3428bd22d92d
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY fhir.py store.py server.py control.py fixture.json /app/
COPY schema/fhir.schema.json /app/schema/fhir.schema.json
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
CMD ["python", "/app/server.py"]
