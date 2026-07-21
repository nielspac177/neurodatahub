#!/usr/bin/env python3
"""
http.py — Cliente HTTP con reintentos (sólo biblioteca estándar).

Todas las APIs que usa NeuroDataHub son gratuitas y sin clave. El correo del
"polite pool" de Crossref/OpenAlex se toma de la variable de entorno
OPENALEX_MAILTO; sin él las peticiones siguen funcionando pero con menos
prioridad.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAILTO = os.environ.get("OPENALEX_MAILTO", "neurodatahub@example.org")
UA = f"NeuroDataHub-bot/2.0 (+https://github.com/nielspac177/neurodatahub; mailto:{MAILTO})"

# Cortesía entre peticiones al mismo host.
POLITE_DELAY = 0.35
_last_call = {}


def _polite(host):
    prev = _last_call.get(host, 0)
    wait = POLITE_DELAY - (time.time() - prev)
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.time()


def get_json(url, timeout=30, retries=3, quiet=False):
    """GET que devuelve JSON, o None si falla tras los reintentos.

    Devolver None en vez de lanzar es deliberado: una corrida semanal que toca
    ocho fuentes no debe abortar porque una esté caída.
    """
    host = urllib.parse.urlparse(url).netloc
    backoff = 1.0
    for attempt in range(retries):
        _polite(host)
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 4xx (salvo 429) no mejora reintentando.
            if e.code != 429 and 400 <= e.code < 500:
                if not quiet:
                    print(f"  [http] {e.code} {url[:90]}", file=sys.stderr)
                return None
            time.sleep(backoff)
            backoff *= 2
        except Exception as e:
            if attempt == retries - 1 and not quiet:
                print(f"  [http] fallo {type(e).__name__} {url[:90]}", file=sys.stderr)
            time.sleep(backoff)
            backoff *= 2
    return None


def post_json(url, payload, timeout=30, retries=2):
    host = urllib.parse.urlparse(url).netloc
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        _polite(host)
        req = urllib.request.Request(
            url, data=body,
            headers={"User-Agent": UA, "Accept": "application/json",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [http] POST fallo {type(e).__name__} {url[:90]}", file=sys.stderr)
            time.sleep(1.5)
    return None


def head_status(url, timeout=20):
    """(código, url_final) para el chequeo de enlaces muertos.

    Algunos servidores rechazan HEAD; se cae a GET en ese caso porque un 405
    no significa que el enlace esté roto.
    """
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.url
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return e.code, url
        except Exception:
            if method == "GET":
                return 0, url
    return 0, url


def qs(**params):
    """Query string omitiendo valores None."""
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
