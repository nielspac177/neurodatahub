#!/usr/bin/env python3
"""
prune_evidence.py — Recorta los paquetes de evidencia ya consumidos.

Cada corrida de enriquecimiento congela ~45 kB por candidato. A 20 por semana
eso son decenas de megabytes al año dentro del repositorio, lo que castiga a
todo el que clona para siempre.

Qué se conserva y por qué:
  - Registro PUBLICADO: el texto completo se sustituye por las frases que de
    verdad justificaron cada campo (guardadas en verification.quotes por
    ingest_records.py) más el sha256 y la URL. La cadena de custodia sigue
    intacta: se puede probar qué decía la fuente y de dónde salió, sin
    arrastrar 40 kB de HTML.
  - Registro BLOQUEADO o pendiente: NO se toca. Todavía hay que revisarlo a
    mano y quien lo revise necesita el contexto completo.

    python scripts/prune_evidence.py [--dry-run] [--keep-days 30]
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML.")

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
DB = ROOT / "data" / "databases.yml"

MARKER = "[pruned — see verification.quotes in data/databases.yml]"


def published_index():
    """{id_evidencia: registro} de todo lo ya publicado."""
    if not DB.exists():
        return {}
    out = {}
    for r in yaml.safe_load(DB.read_text(encoding="utf-8")) or []:
        out[r["id"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-days", type=int, default=30,
                    help="no tocar paquetes más recientes que esto")
    args = ap.parse_args()

    if not DRAFTS.exists():
        sys.exit("No hay drafts/.")

    published = published_index()
    cutoff = (date.today() - timedelta(days=args.keep_days)).isoformat()

    pruned = skipped = 0
    freed = 0

    for path in sorted(DRAFTS.glob("*.evidence.json")):
        rid = path.name[: -len(".evidence.json")]
        before = path.stat().st_size

        record = published.get(rid)
        if not record:
            skipped += 1
            continue                      # aún sin publicar: se conserva entero

        # Un paquete todavía en revisión humana no se toca.
        if (DRAFTS / "needs_human" / f"{rid}.record.json").exists():
            skipped += 1
            continue

        bundle = json.loads(path.read_text(encoding="utf-8"))
        if all(s.get("text") == MARKER for s in bundle.get("sources", [])):
            continue                      # ya recortado

        newest = max((s.get("fetched_at") or "") for s in bundle.get("sources", [])) or ""
        if newest > cutoff:
            skipped += 1
            continue

        quotes = ((record.get("verification") or {}).get("quotes")) or {}
        kept = sorted({q["quote"] for qs in quotes.values() for q in qs if q.get("quote")})

        # Sin citas retenidas, recortar no comprime: DESTRUYE la cadena de
        # custodia. Los registros ingeridos antes de que ingest_records.py
        # empezara a guardar verification.quotes caen aquí, y se dejan
        # enteros a propósito.
        if not kept:
            print(f"  ⚠ {rid:34s} sin verification.quotes — se conserva entero "
                  f"(re-ingerir para poder recortarlo)")
            skipped += 1
            continue

        for s in bundle.get("sources", []):
            s["text"] = MARKER            # sha256 y url se conservan intactos
        bundle["retained_quotes"] = kept
        bundle["pruned_at"] = date.today().isoformat()

        if not args.dry_run:
            path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        after = len(json.dumps(bundle, ensure_ascii=False, indent=2))
        freed += before - after
        pruned += 1
        print(f"  ✂ {rid:34s} {before // 1024:4d} kB -> {after // 1024:3d} kB "
              f"({len(kept)} citas conservadas)")

    print(f"\n  recortados {pruned} · intactos {skipped} · "
          f"liberados {freed // 1024} kB")
    if args.dry_run:
        print("  (dry-run: no se escribió nada)")


if __name__ == "__main__":
    main()
