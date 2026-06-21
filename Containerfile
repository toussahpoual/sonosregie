FROM docker.io/library/python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web

ENV SONOS_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8095

# Sonos se pilote en LAN : on tournera en réseau hôte côté Quadlet.
# BIND_HOST/BIND_PORT pilotables par env : permet de basculer l'app en interne
# (127.0.0.1:8096) quand oauth2-proxy prend la façade :8095, sans rebuild.
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"${BIND_HOST:-0.0.0.0}\" --port \"${BIND_PORT:-8095}\""]
