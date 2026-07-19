FROM docker.io/library/python:3.14-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web

# Assets de déploiement embarqués -> déploiement « image seule » (sans cloner le repo).
# Deux variantes d'unit app, dérivées d'une source unique (pas de script de bascule) :
#   /srv/deploy/sonosregie.container        -> mode ouvert (:8095)
#   /srv/deploy/auth/sonosregie.container   -> mode SSO (app interne 127.0.0.1:8096)
# Le « mode » = quel fichier on extrait de l'image. Ex :
#   podman run --rm IMAGE cat /srv/deploy/sonosregie.container > ~/.config/containers/systemd/sonosregie.container
COPY sonosregie.container /srv/deploy/sonosregie.container
COPY auth/sonosregie-auth.container /srv/deploy/auth/sonosregie-auth.container
COPY auth/authentik_bootstrap.py /srv/deploy/auth/authentik_bootstrap.py
RUN sed '/^Network=host/a Environment=BIND_HOST=127.0.0.1\nEnvironment=BIND_PORT=8096' \
      /srv/deploy/sonosregie.container > /srv/deploy/auth/sonosregie.container

ENV SONOS_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8095

# Sonos se pilote en LAN : on tournera en réseau hôte côté Quadlet.
# BIND_HOST/BIND_PORT pilotables par env : permet de basculer l'app en interne
# (127.0.0.1:8096) quand oauth2-proxy prend la façade :8095, sans rebuild.
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"${BIND_HOST:-0.0.0.0}\" --port \"${BIND_PORT:-8095}\""]
