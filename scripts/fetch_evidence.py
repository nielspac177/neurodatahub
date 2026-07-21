#!/usr/bin/env python3
"""
fetch_evidence.py — Etapa 1 del pipeline: recolección de evidencia.

Deterministic ON PURPOSE: aquí no interviene ningún modelo. Se descargan y se
CONGELAN las fuentes antes de que nada genere texto:

    - página de aterrizaje del dataset
    - metadatos de Crossref por DOI
    - registro de la API del repositorio (OpenNeuro / DANDI / Zenodo)

Cada fuente se guarda con su sha256 y su fecha en drafts/<id>.evidence.json.

Por qué congelar: convierte la comprobación de fundamentación en una búsqueda
de subcadena en vez de en la opinión de un segundo modelo. Si el redactor cita
una frase que no aparece literalmente en la evidencia, se detecta con
str.find(), gratis y con certeza. Además cualquier crítico puede re-ejecutarse
meses después contra exactamente lo que el redactor vio.

    python scripts/fetch_evidence.py --limit 10
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from scripts.lib import keys as K
from scripts.lib import state
from scripts.lib.http import get_json, qs, UA

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"

MAX_TEXT = 20_000        # por fuente; suficiente para licencia + descripción
SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}


class TextExtractor(HTMLParser):
    """HTML -> texto plano. Sólo biblioteca estándar, sin dependencias."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.parts.append(t)

    def text(self):
        return re.sub(r"\s+", " ", " ".join(self.parts))


def fetch_html(url, timeout=25):
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read(2_000_000)
            if "json" in ctype:
                return raw.decode("utf-8", "replace")[:MAX_TEXT], resp.url
            charset = "utf-8"
            m = re.search(r"charset=([\w-]+)", ctype)
            if m:
                charset = m.group(1)
            p = TextExtractor()
            p.feed(raw.decode(charset, "replace"))
            return p.text()[:MAX_TEXT], resp.url
    except Exception as e:
        return f"[fetch failed: {type(e).__name__}]", url


ONEURO_QUERY = """
query($id: ID!) {
  dataset(id: $id) {
    id created
    latestSnapshot {
      tag readme
      description { Name Authors License Acknowledgements DatasetDOI Funding ReferencesAndLinks }
      summary { subjects modalities tasks sessions totalFiles size dataProcessed }
    }
  }
}
"""


def openneuro_record(ds_id):
    """Texto de evidencia de OpenNeuro vía GraphQL (la SPA no sirve HTML)."""
    from scripts.lib.http import post_json
    data = post_json("https://openneuro.org/crn/graphql",
                     {"query": ONEURO_QUERY, "variables": {"id": ds_id}})
    ds = ((data or {}).get("data") or {}).get("dataset")
    if not ds:
        return ""
    snap = ds.get("latestSnapshot") or {}
    desc = snap.get("description") or {}
    summ = snap.get("summary") or {}
    subjects = summ.get("subjects") or []

    # Se aplana a texto legible en vez de JSON crudo: el redactor debe poder
    # citar una frase literal, y las citas se verifican por subcadena.
    lines = [
        f"OpenNeuro dataset {ds_id} (snapshot {snap.get('tag')})",
        f"Name: {desc.get('Name')}",
        f"Authors: {', '.join(desc.get('Authors') or [])}",
        f"License: {desc.get('License')}",
        f"DatasetDOI: {desc.get('DatasetDOI')}",
        f"Number of subjects: {len(subjects)}",
        f"Modalities: {', '.join(summ.get('modalities') or [])}",
        f"Tasks: {', '.join(summ.get('tasks') or [])}",
        f"Sessions: {', '.join(map(str, summ.get('sessions') or []))}",
        f"Total files: {summ.get('totalFiles')}",
        f"Size bytes: {summ.get('size')}",
        f"Created: {ds.get('created')}",
        "",
        "README:",
        snap.get("readme") or "(no README)",
    ]
    return "\n".join(str(x) for x in lines)


def source(src_id, kind, url, text):
    return {
        "src_id": src_id,
        "kind": kind,
        "url": url,
        "fetched_at": date.today().isoformat(),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "chars": len(text),
        "text": text,
    }


def slug(candidate):
    """Id estable a partir del accession, del DOI o del título."""
    acc = K.accession_key(candidate.get("url"), candidate.get("doi"),
                          candidate.get("title"), candidate.get("raw_id"))
    if acc:
        return acc.replace(":", "-")
    d = K.doi_key(candidate.get("doi"))
    if d:
        return re.sub(r"[^a-z0-9]+", "-", d).strip("-")[:60]
    return re.sub(r"[^a-z0-9]+", "-",
                  K.title_fingerprint(candidate.get("title"), 50)).strip("-")[:60]


def gather(candidate):
    """Paquete de evidencia de un candidato."""
    sources, n = [], 0

    landing = candidate.get("url")
    if landing:
        text, final = fetch_html(landing)
        n += 1
        sources.append(source(f"e{n}", "landing_page", final, text))

    doi = K.doi_key(candidate.get("doi"))
    if doi:
        meta = get_json(f"https://api.crossref.org/works/{doi}", quiet=True)
        if meta:
            n += 1
            sources.append(source(f"e{n}", "crossref_metadata",
                                  f"https://api.crossref.org/works/{doi}",
                                  json.dumps(meta.get("message", {}),
                                             ensure_ascii=False)[:MAX_TEXT]))

    acc = K.accession_key(candidate.get("url"), candidate.get("doi"),
                          candidate.get("title"), candidate.get("raw_id"))
    if acc.startswith("openneuro:"):
        ds = acc.split(":", 1)[1]
        # La página de OpenNeuro es una SPA de React y no trae contenido en el
        # HTML: descargarla da 0 caracteres. La API GraphQL sí devuelve README,
        # licencia, DOI, sujetos, modalidades y tareas — que es justo lo que
        # necesitan el crítico de acceso (licencia) y el de viabilidad (qué
        # variables existen de verdad).
        meta = openneuro_record(ds)
        if meta:
            n += 1
            sources.append(source(f"e{n}", "repository_record",
                                  f"https://openneuro.org/datasets/{ds}",
                                  meta[:MAX_TEXT]))
    elif acc.startswith("dandi:"):
        ident = acc.split(":", 1)[1]
        meta = get_json(f"https://api.dandiarchive.org/api/dandisets/{ident}/", quiet=True)
        if meta:
            n += 1
            sources.append(source(f"e{n}", "repository_record",
                                  f"https://dandiarchive.org/dandiset/{ident}",
                                  json.dumps(meta, ensure_ascii=False)[:MAX_TEXT]))

    return sources


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--min-score", type=int, default=0)
    args = ap.parse_args()

    candidates = state.read_jsonl("candidates")
    if not candidates:
        sys.exit("No hay candidatos. Corre primero: python scripts/harvest_run.py")

    # La cola es append-only, así que sigue listando lo ya publicado. Se filtra
    # contra el catálogo por claves autoritativas; fiarse de que exista el
    # archivo de evidencia funcionaba por accidente, no por diseño.
    db = ROOT / "data" / "databases.yml"
    published = set()
    if db.exists():
        for r in yaml.safe_load(db.read_text(encoding="utf-8")) or []:
            published.update(K.authoritative(K.all_keys(r)))
            published.add(r["id"])

    def already(c):
        if any(k in published for k in K.authoritative(K.all_keys(c))):
            return True
        return slug(c) in published

    before = len(candidates)
    candidates = [c for c in candidates if not already(c)]
    if before != len(candidates):
        print(f"  {before - len(candidates)} candidatos ya publicados, omitidos")

    candidates.sort(key=lambda c: -c.get("score", 0))
    DRAFTS.mkdir(parents=True, exist_ok=True)

    done = 0
    for c in candidates:
        if done >= args.limit:
            break
        if c.get("score", 0) < args.min_score:
            continue

        sid = slug(c)
        if not sid:
            continue
        out = DRAFTS / f"{sid}.evidence.json"
        if out.exists():
            continue          # ya reclamado; reanudable

        # Sólo se conservan las fuentes con contenido real. Una página vacía
        # (las SPA de React devuelven 0 caracteres) no es evidencia, y darle
        # al redactor una fuente vacía sólo le invita a rellenar el hueco.
        sources = [s for s in gather(c)
                   if s["chars"] > 0 and not s["text"].startswith("[fetch failed")]
        usable = sources
        if not usable:
            print(f"  sin evidencia utilizable: {c['title'][:60]}", file=sys.stderr)
            continue

        out.write_text(json.dumps({
            "id": sid,
            "candidate": {k: c.get(k) for k in
                          ("title", "url", "doi", "date", "venue", "source",
                           "score", "discovered_by", "discovered_at",
                           "possible_duplicate")},
            "sources": sources,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        done += 1
        chars = sum(s["chars"] for s in usable)
        print(f"  ✓ {sid:38s} {len(usable)} fuentes, {chars:6d} chars")

    print(f"\n{done} paquetes de evidencia -> drafts/")
    if done:
        print("Siguiente: node workflows/enrich.mjs   (o el Workflow de Claude Code)")


if __name__ == "__main__":
    main()
