#!/usr/bin/env python3
"""
research_update.py — Descubrimiento semanal de nuevas bases de datos / datasets.

Consulta APIs académicas y de repositorios que ofrecen acceso programático GRATUITO
y sin clave (OpenAlex, Zenodo, Europe PMC), recorriendo la matriz enfermedad x modalidad.
Deduplica contra data/databases.yml y escribe:
    - data/candidates.json   (estructurado, para revisión / merge)
    - data/candidates.md     (resumen legible para el cuerpo del Pull Request)

NO publica nada por sí mismo: el workflow de GitHub Actions abre un PR que un humano
(o Claude en el loop) revisa, cura y mergea. Así el repo mantiene un único contribuidor.

Uso:
    python scripts/research_update.py [--days 14] [--max-per-query 5]

Requiere solo la librería estándar + PyYAML.
Variable de entorno opcional: OPENALEX_MAILTO (email para el "polite pool" de OpenAlex).
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML. Instala con: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "databases.yml"
OUT_JSON = ROOT / "data" / "candidates.json"
OUT_MD = ROOT / "data" / "candidates.md"

MAILTO = os.environ.get("OPENALEX_MAILTO", "neurodatahub@example.org")
UA = f"NeuroDataHub-bot/1.0 (mailto:{MAILTO})"

# ------------------------------------------------------------------ #
# Matriz de búsqueda: enfermedad x modalidad
# ------------------------------------------------------------------ #
DISEASES = [
    "Parkinson disease", "epilepsy", "glioma glioblastoma", "ischemic stroke",
    "Alzheimer disease", "major depressive disorder", "schizophrenia",
    "traumatic brain injury", "multiple sclerosis", "autism spectrum disorder",
    "ADHD", "obsessive compulsive disorder", "deep brain stimulation",
]
MODALITIES = [
    "EEG dataset", "iEEG intracranial dataset", "MRI open dataset",
    "fMRI dataset", "GWAS summary statistics", "brain computer interface dataset",
    "electronic health record ICU database", "PET imaging dataset",
]
# Términos que refuerzan que se trata de un recurso de DATOS, no un estudio cualquiera.
DATA_TERMS = "(dataset OR database OR \"data descriptor\" OR benchmark OR \"open data\" OR cohort)"


def http_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ------------------------------------------------------------------ #
# Conjunto de "ya conocidos" para deduplicar
# ------------------------------------------------------------------ #
def load_known():
    known_urls, known_names = set(), set()
    if SRC.exists():
        for r in yaml.safe_load(SRC.read_text(encoding="utf-8")) or []:
            if r.get("url"):
                known_urls.add(normalize_url(r["url"]))
            if r.get("name"):
                known_names.add(r["name"].lower())
    return known_urls, known_names


def normalize_url(u):
    if not u:
        return ""
    u = u.strip().lower().rstrip("/")
    for pref in ("https://", "http://", "www."):
        if u.startswith(pref):
            u = u[len(pref):]
    return u


# ------------------------------------------------------------------ #
# Fuentes
# ------------------------------------------------------------------ #
def search_openalex(query, since, max_rows):
    """Trabajos de tipo dataset en OpenAlex, publicados desde `since`."""
    out = []
    flt = f"type:dataset,from_publication_date:{since}"
    params = urllib.parse.urlencode({
        "search": query,
        "filter": flt,
        "per-page": max_rows,
        "sort": "publication_date:desc",
        "mailto": MAILTO,
    })
    url = f"https://api.openalex.org/works?{params}"
    try:
        data = http_json(url)
    except Exception as e:
        print(f"  [openalex] error: {e}", file=sys.stderr)
        return out
    for w in data.get("results", []):
        loc = (w.get("primary_location") or {})
        landing = loc.get("landing_page_url") or w.get("id")
        out.append({
            "title": w.get("title") or "(sin título)",
            "url": landing,
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "date": w.get("publication_date"),
            "source": "OpenAlex",
            "query": query,
        })
    return out


def search_zenodo(query, since, max_rows):
    """Registros de tipo dataset en Zenodo."""
    out = []
    params = urllib.parse.urlencode({
        "q": query,
        "type": "dataset",
        "size": max_rows,
        "sort": "mostrecent",
    })
    url = f"https://zenodo.org/api/records?{params}"
    try:
        data = http_json(url)
    except Exception as e:
        print(f"  [zenodo] error: {e}", file=sys.stderr)
        return out
    for h in (data.get("hits", {}) or {}).get("hits", []):
        meta = h.get("metadata", {})
        pub = meta.get("publication_date", "")
        if pub and pub < since:
            continue
        out.append({
            "title": meta.get("title", "(sin título)"),
            "url": h.get("links", {}).get("self_html") or h.get("doi_url", ""),
            "doi": h.get("doi", ""),
            "date": pub,
            "source": "Zenodo",
            "query": query,
        })
    return out


def search_europepmc(query, since, max_rows):
    """Data descriptors / artículos de datos recientes en Europe PMC."""
    out = []
    q = f'({query}) AND {DATA_TERMS} AND (FIRST_PDATE:[{since} TO 3000])'
    params = urllib.parse.urlencode({
        "query": q, "format": "json", "pageSize": max_rows, "resultType": "lite",
    })
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?{params}"
    try:
        data = http_json(url)
    except Exception as e:
        print(f"  [europepmc] error: {e}", file=sys.stderr)
        return out
    for r in (data.get("resultList", {}) or {}).get("result", []):
        doi = r.get("doi", "")
        out.append({
            "title": r.get("title", "(sin título)"),
            "url": f"https://doi.org/{doi}" if doi else
                   f"https://europepmc.org/abstract/{r.get('source','')}/{r.get('id','')}",
            "doi": doi,
            "date": r.get("firstPublicationDate", ""),
            "source": "EuropePMC",
            "query": query,
        })
    return out


# ------------------------------------------------------------------ #
# Orquestación
# ------------------------------------------------------------------ #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="ventana hacia atrás (días)")
    ap.add_argument("--max-per-query", type=int, default=5)
    args = ap.parse_args()

    since = (date.today() - timedelta(days=args.days)).isoformat()
    known_urls, known_names = load_known()
    print(f"Ventana desde {since} · {len(known_urls)} bases ya en catálogo")

    queries = [f"{d} {m}" for d in DISEASES for m in MODALITIES]
    # No explotamos el producto completo cada semana: rotamos un subconjunto por día del año.
    day_index = (date.today() - date(date.today().year, 1, 1)).days
    rotate = 24  # nº de consultas por corrida
    start = (day_index * rotate) % max(len(queries), 1)
    selected = (queries + queries)[start:start + rotate]

    raw = []
    for q in selected:
        for fn in (search_openalex, search_zenodo, search_europepmc):
            raw.extend(fn(q, since, args.max_per_query))
            time.sleep(0.4)  # cortesía con las APIs

    # Deduplicar (contra catálogo y entre sí)
    seen, candidates = set(), []
    for c in raw:
        key = normalize_url(c["url"]) or (c.get("doi") or "").lower() or c["title"].lower()
        if not key or key in seen:
            continue
        if key in known_urls or c["title"].lower() in known_names:
            continue
        seen.add(key)
        candidates.append(c)

    candidates.sort(key=lambda c: c.get("date") or "", reverse=True)

    payload = {
        "scanned_at": date.today().isoformat(),
        "window_start": since,
        "queries_run": len(selected),
        "n_candidates": len(candidates),
        "candidates": candidates,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Resumen markdown para el cuerpo del PR
    lines = [
        f"# Weekly dataset scan — {payload['scanned_at']}",
        "",
        f"- Ventana: desde **{since}**",
        f"- Consultas ejecutadas: **{len(selected)}**",
        f"- Candidatos nuevos (tras deduplicar): **{len(candidates)}**",
        "",
    ]
    if not candidates:
        lines.append("_Sin candidatos nuevos esta semana._")
    else:
        lines.append("| # | Título | Fuente | Fecha | Enlace |")
        lines.append("|---|--------|--------|-------|--------|")
        for i, c in enumerate(candidates, 1):
            title = (c["title"][:90] + "…") if len(c["title"]) > 90 else c["title"]
            title = title.replace("|", "\\|")
            lines.append(f"| {i} | {title} | {c['source']} | {c.get('date','')} | {c['url']} |")
        lines += [
            "",
            "> Revisar cada candidato: si es una base relevante y estable, añadir un",
            "> registro completo a `data/databases.yml` (ver esquema) y cerrar este PR.",
        ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK: {len(candidates)} candidatos -> {OUT_JSON.name}, {OUT_MD.name}")


if __name__ == "__main__":
    main()
