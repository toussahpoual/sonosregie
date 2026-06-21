#!/usr/bin/env python3
"""Bootstrap an Authentik provider to protect Sonosregie behind oauth2-proxy.

Idempotent. Creates/updates:
  - 1 confidential OAuth2/OIDC Provider (redirect = oauth2-proxy callback)
  - 1 Application (slug: sonosregie)
  - 1 dedicated Group (default: sonos-users)
  - 1 policy binding Group -> Application (access restricted to the group)
Then writes the oauth2-proxy EnvironmentFile (client id/secret + cookie secret +
issuer + redirect), mode 0600, WITHOUT ever printing the secrets.

Designed to run inside the app container (Python + network OK; a non-default
User-Agent is forced so it isn't blocked by a WAF in front of Authentik).

Environment:
  AUTHENTIK_TOKEN  (required)  admin API token (Settings > Tokens & App passwords)
  AUTHENTIK_URL    (required)  e.g. https://auth.example.com
  REDIRECT_URL     (default http://localhost:8095/oauth2/callback)
  PUBLIC_HOST      shortcut: if set, REDIRECT_URL defaults to http://$PUBLIC_HOST:8095/oauth2/callback
  APP_SLUG, APP_NAME, GROUP_NAME, ENV_OUT (see defaults below)
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

URL = (os.environ.get("AUTHENTIK_URL") or "").rstrip("/")
if not URL:
    sys.exit("AUTHENTIK_URL is required (e.g. https://auth.example.com)")
TOKEN = os.environ.get("AUTHENTIK_TOKEN") or sys.exit("AUTHENTIK_TOKEN is required")
APP_SLUG = os.environ.get("APP_SLUG", "sonosregie")
APP_NAME = os.environ.get("APP_NAME", "Sonosregie")
GROUP = os.environ.get("GROUP_NAME", "sonos-users")
_PUBLIC_HOST = os.environ.get("PUBLIC_HOST")
REDIRECT = os.environ.get(
    "REDIRECT_URL",
    f"http://{_PUBLIC_HOST}:8095/oauth2/callback" if _PUBLIC_HOST else "http://localhost:8095/oauth2/callback",
)
OUT = os.environ.get("ENV_OUT", "/out/oauth2-proxy.env")
ISSUER = f"{URL}/application/o/{APP_SLUG}/"
UA = "Mozilla/5.0 (sonosregie-bootstrap)"
API = URL + "/api/v3"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + TOKEN, "User-Agent": UA,
                 "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"  ! HTTP {e.code} {method} {path}: {e.read().decode()[:400]}\n")
        raise


def first(results, **match):
    for it in results:
        if all(it.get(k) == v for k, v in match.items()):
            return it
    return None


def scope_pk(name):
    res = req("GET", f"/propertymappings/provider/scope/?scope_name={name}&page_size=100")["results"]
    it = first(res, scope_name=name) or (res[0] if res else None)
    if not it:
        sys.exit(f"scope mapping not found: {name}")
    return it["pk"]


def find_signing_key():
    """Discover a certificate usable to sign JWTs (prefers Authentik's default
    self-signed cert). PKs are not stable across instances -> never hardcode."""
    res = req("GET", "/crypto/certificatekeypairs/?page_size=100")["results"]
    usable = [c for c in res if c.get("private_key_available") or c.get("private_key_type")] or res
    if not usable:
        sys.exit("no certificate keypair available for JWT signing")
    return (first(usable, name="authentik Self-signed Certificate") or usable[0])["pk"]


def find_flow(slug, designation):
    res = req("GET", f"/flows/instances/?slug={slug}")["results"]
    if res:
        return res[0]["pk"]
    res = req("GET", f"/flows/instances/?designation={designation}&page_size=100")["results"]
    if not res:
        sys.exit(f"flow not found: {designation}")
    return res[0]["pk"]


print(f"==> Authentik {URL}")
print("==> scopes openid/profile/email")
pm = [scope_pk("openid"), scope_pk("profile"), scope_pk("email")]

print("==> signing key + flows")
signing = find_signing_key()
auth_flow = find_flow("default-provider-authorization-implicit-consent", "authorization")
inval_flow = find_flow("default-provider-invalidation-flow", "invalidation")

print("==> OIDC provider")
prov_body = {
    "name": APP_SLUG, "client_type": "confidential", "client_id": APP_SLUG,
    "authorization_flow": auth_flow, "invalidation_flow": inval_flow,
    "signing_key": signing, "include_claims_in_id_token": True,
    "issuer_mode": "per_provider", "sub_mode": "hashed_user_id",
    "redirect_uris": [{"matching_mode": "strict", "url": REDIRECT}],
    "property_mappings": pm,
}
existing = req("GET", f"/providers/oauth2/?search={APP_SLUG}&page_size=100")["results"]
prov = first(existing, name=APP_SLUG)
if prov:
    prov = req("PATCH", f"/providers/oauth2/{prov['pk']}/", prov_body)
else:
    prov = req("POST", "/providers/oauth2/", prov_body)
pk = prov["pk"]
print(f"    {'updated' if existing else 'created'} (pk={pk})")
detail = req("GET", f"/providers/oauth2/{pk}/")
client_id, client_secret = detail["client_id"], detail["client_secret"]

print("==> application")
apps = req("GET", f"/core/applications/?search={APP_SLUG}&page_size=100")["results"]
app = first(apps, slug=APP_SLUG)
app_body = {"name": APP_NAME, "slug": APP_SLUG, "provider": pk}
app = (req("PATCH", f"/core/applications/{APP_SLUG}/", app_body) if app
       else req("POST", "/core/applications/", app_body))
app_uuid = app["pk"]
print(f"    slug={APP_SLUG} (pk={app_uuid})")

print(f"==> group {GROUP}")
groups = req("GET", f"/core/groups/?search={GROUP}&page_size=100")["results"]
grp = first(groups, name=GROUP) or req("POST", "/core/groups/", {"name": GROUP})
gpk = grp["pk"]
print(f"    pk={gpk}")

print("==> access restriction (group -> application binding)")
binds = req("GET", f"/policies/bindings/?target={app_uuid}&page_size=100")["results"]
if first(binds, group=gpk):
    print("    already present")
else:
    req("POST", "/policies/bindings/", {"target": app_uuid, "group": gpk, "order": 0, "enabled": True})
    print("    created")

print(f"==> writing {OUT} (0600)")
content = (
    f"OAUTH2_PROXY_CLIENT_ID={client_id}\n"
    f"OAUTH2_PROXY_CLIENT_SECRET={client_secret}\n"
    # 24 bytes -> 32 url-safe chars without padding = 32 raw bytes (valid AES key;
    # b64encode(32) would be 44 chars and oauth2-proxy rejects it).
    f"OAUTH2_PROXY_COOKIE_SECRET={base64.urlsafe_b64encode(os.urandom(24)).decode()}\n"
    f"OAUTH2_PROXY_OIDC_ISSUER_URL={ISSUER}\n"
    f"OAUTH2_PROXY_REDIRECT_URL={REDIRECT}\n"
)
fd = os.open(OUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.write(fd, content.encode())
os.close(fd)

print("\nOK. Provider/application/group configured; oauth2-proxy env written (secrets not shown).")
print(f"   issuer:   {ISSUER}")
print(f"   redirect: {REDIRECT}")
print(f"   NOTE: add your user to the '{GROUP}' group in Authentik, otherwise access is denied.")
