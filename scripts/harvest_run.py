#!/usr/bin/env python3
"""
harvest_run.py — Orquestador de descubrimiento semanal.

Corre en GitHub Actions sin claves de API. Enumera las fuentes conocidas-buenas,
deduplica contra el libro mayor, tría con el léxico determinista y reparte los
candidatos en tres colas. No escribe nunca en databases.yml.

    python scripts/harvest_run.py                     # incremental, todas las fuentes
    python scripts/harvest_run.py --sources crossref  # sólo una
    python scripts/harvest_run.py --backfill --limit 300 --min-score 75
    python scripts/harvest_run.py --dry-run           # sin escribir estado ni colas

El estado se guarda SÓLO al final, después de persistir las colas: si la
corrida muere a la mitad, la próxima vuelve a traer en vez de saltarse.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML. Instala con: pip install pyyaml")

from scripts import harvest
from scripts.lib import keys as K
from scripts.lib import lexicon, state

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "databases.yml"
REPORTS = ROOT / "reports"


def catalog_dois():
    """DOIs de descriptores ya catalogados, semilla del harvester de citas."""
    if not DB.exists():
        return []
    out = []
    for r in yaml.safe_load(DB.read_text(encoding="utf-8")) or []:
        for field in ("descriptor_doi", "doi"):
            if r.get(field):
                out.append(r[field])
                break
    return out


def catalog_keys():
    """Claves de todo lo ya publicado, para no re-proponer lo que ya tenemos."""
    known = set()
    if not DB.exists():
        return known
    for r in yaml.safe_load(DB.read_text(encoding="utf-8")) or []:
        for v in K.authoritative(K.all_keys(r)):
            known.add(v)
    return known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", help="lista separada por comas; por defecto todas")
    ap.add_argument("--limit", type=int, help="máximo de items por fuente")
    ap.add_argument("--backfill", action="store_true", help="recorrido histórico")
    ap.add_argument("--min-score", type=int, default=lexicon.THRESHOLD_CANDIDATE,
                    help="umbral para la cola de candidatos")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    names = (args.sources.split(",") if args.sources
             else harvest.ENUMERATING + harvest.SAMPLING)

    hstate = state.load_harvest_state()
    ledger = state.Ledger()
    published = catalog_keys()

    print(f"Libro mayor: {len(ledger)} claves · catálogo: {len(published)} claves publicadas")

    buckets = {"candidates": [], "borderline": [], "rejected": []}
    per_source = {}
    dupes = 0
    today = date.today().isoformat()

    for name in names:
        cls = harvest.REGISTRY.get(name)
        if not cls:
            print(f"  fuente desconocida: {name}", file=sys.stderr)
            continue

        h = cls(hstate)
        kwargs = {"limit": args.limit}
        if name == "citedby":
            kwargs["seed_dois"] = catalog_dois()

        fetched = kept = 0
        try:
            stream = h.backfill(**kwargs) if args.backfill else h.incremental(**kwargs)
            for item in stream:
                fetched += 1
                item_keys = K.all_keys(item)
                auth = K.authoritative(item_keys)

                # Ya publicado o ya visto (incluidos los rechazos previos).
                if any(a in published for a in auth) or ledger.seen(item_keys):
                    dupes += 1
                    continue

                points, detail = lexicon.score(item)
                bucket = ("candidates" if points >= args.min_score
                          else lexicon.route(points))

                collision = ledger.title_collision(item_keys)
                enriched = dict(item)
                enriched["score"] = points
                enriched["score_detail"] = detail
                enriched["discovered_by"] = name
                enriched["discovered_at"] = today
                if collision:
                    # Nunca descarta: es una bandera para el crítico C5.
                    enriched["possible_duplicate"] = True

                buckets[bucket].append(enriched)
                ledger.record(item_keys, bucket, today, score=points)
                kept += 1
        except Exception as e:
            print(f"  [{name}] error: {type(e).__name__}: {e}", file=sys.stderr)

        per_source[name] = {"fetched": fetched, "new": kept}
        print(f"  {name:12s} traídos={fetched:5d} nuevos={kept:4d}")

    print(f"\nDuplicados descartados: {dupes}")
    for b, rows in buckets.items():
        print(f"  {b:12s} {len(rows)}")

    if args.dry_run:
        print("\n(dry-run: no se escribió estado ni colas)")
        return

    for b, rows in buckets.items():
        state.append_jsonl(b, rows)
    compact_queues()
    ledger.save()
    state.save_harvest_state(hstate)

    write_report(buckets, per_source, dupes)
    print(f"\nInforme -> reports/scan-{today}.md")


# Con enriquecimiento mensual y escaneo semanal, las colas crecen cuatro veces
# más rápido de lo que se consumen. Sin compactar, el PR semanal llega a cientos
# de miles de líneas y deja de ser revisable.
KEEP_CANDIDATES = 500
KEEP_BORDERLINE = 500


def compact_queues():
    """Recorta las colas dejando lo mejor puntuado.

    `rejected` se vacía del todo: el libro mayor (state/seen.json) ya recuerda
    cada rechazo con su puntaje, que es lo único que hace falta para no
    volver a triarlo. Conservar además el JSON completo sólo infla el diff.
    """
    for name, keep in (("candidates", KEEP_CANDIDATES), ("borderline", KEEP_BORDERLINE)):
        rows = state.read_jsonl(name)
        if len(rows) <= keep:
            continue
        rows.sort(key=lambda r: -(r.get("score") or 0))
        path = state.QUEUE_DIR / f"{name}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                for r in rows[:keep]), encoding="utf-8")
        print(f"  cola {name}: {len(rows)} -> {keep} (se conservan los mejor puntuados)")

    rejected = state.QUEUE_DIR / "rejected.jsonl"
    if rejected.exists() and rejected.stat().st_size:
        n = sum(1 for _ in rejected.open(encoding="utf-8"))
        rejected.write_text("", encoding="utf-8")
        print(f"  cola rejected: {n} descartados -> 0 (ya están en el libro mayor)")


def write_report(buckets, per_source, dupes):
    today = date.today().isoformat()
    REPORTS.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Weekly dataset scan — {today}", "",
        f"- Candidatos nuevos: **{len(buckets['candidates'])}**",
        f"- Dudosos (requieren triaje LLM): **{len(buckets['borderline'])}**",
        f"- Rechazados: **{len(buckets['rejected'])}**",
        f"- Duplicados colapsados: **{dupes}**", "",
        "## Por fuente", "",
        "| Fuente | Traídos | Nuevos |", "|---|---:|---:|",
    ]
    for name, s in per_source.items():
        lines.append(f"| {name} | {s['fetched']} | {s['new']} |")

    if buckets["candidates"]:
        lines += ["", "## Candidatos a enriquecer", "",
                  "| Puntaje | Título | Fuente | Enlace |", "|---:|---|---|---|"]
        for c in sorted(buckets["candidates"], key=lambda x: -x["score"])[:40]:
            t = c["title"][:80].replace("|", r"\|")
            lines.append(f"| {c['score']} | {t} | {c['source']} | {c['url']} |")

    lines += ["", "---", "",
              "> Siguiente paso (local): `node workflows/enrich.mjs --limit 20`",
              "> Nada entra a `data/databases.yml` sin pasar por los críticos y por tu revisión."]

    (REPORTS / f"scan-{today}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (REPORTS / "latest-scan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
