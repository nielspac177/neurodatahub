#!/usr/bin/env python3
"""
calibrate_triage.py — Control positivo del léxico de triaje.

Puntúa los registros YA publicados como si acabaran de ser descubiertos. Todos
deberían superar el umbral de candidato: si una base que sabemos buena puntúa
por debajo, el léxico está mal calibrado, no el registro.

Sin esto, el triaje puede estar tirando silenciosamente el 80% de lo bueno y
nadie se entera, porque los rechazos no se revisan.

    python scripts/calibrate_triage.py [-v]

Sale con 1 si algún registro publicado queda por debajo del umbral.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML.")

from scripts.lib import lexicon

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "databases.yml"


def as_candidate(record):
    """Convierte un registro publicado en la forma que ve el triaje.

    Sólo se le pasan los campos que un harvester tendría de verdad (título,
    descripción, proveedor). Pasarle 'diseases' o 'modality_primary' ya
    resueltos sería hacer trampa: el triaje nunca los tiene.
    """
    return {
        "title": record.get("name", ""),
        "abstract": " ".join(filter(None, [
            record.get("short_desc_en"), record.get("short_desc_es"),
            " ".join(record.get("data_types") or []),
        ])),
        "venue": record.get("provider", ""),
        "source": "calibration",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    records = yaml.safe_load(DB.read_text(encoding="utf-8")) or []
    rows, failures = [], []

    for r in records:
        points, detail = lexicon.score(as_candidate(r))
        bucket = lexicon.route(points)
        rows.append((points, r["id"], bucket, detail))
        # La condición de fallo es 'rejected', no 'no llegó a candidato'.
        # Que un conocido-bueno caiga en 'borderline' es aceptable: ahí lo ve
        # el triaje LLM. Que caiga en 'rejected' es un fallo silencioso, y eso
        # es lo único que este control existe para atrapar.
        if bucket == "rejected":
            failures.append((points, r["id"], bucket, detail))

    rows.sort()
    print(f"Umbral candidato = {lexicon.THRESHOLD_CANDIDATE}, "
          f"dudoso = {lexicon.THRESHOLD_BORDERLINE}\n")
    for points, rid, bucket, detail in rows:
        mark = "✅" if points >= lexicon.THRESHOLD_CANDIDATE else (
            "⚠️ " if bucket == "borderline" else "❌")
        print(f"  {mark} {points:4d}  {rid:24s} {bucket}")
        if args.verbose:
            print(f"          enfermedad={detail.get('disease')} "
                  f"modalidad={detail.get('modality')} "
                  f"dataness={detail.get('dataness')} "
                  f"coincidencias={detail.get('matched', [])[:6]}")

    n = len(rows)
    passed = n - len(failures)
    as_cand = sum(1 for p_, _, b, _d in rows if b == "candidates")
    print(f"\n{as_cand}/{n} llegan directo a 'candidates'")
    print(f"{passed}/{n} evitan 'rejected' (ninguno se pierde en silencio)")

    if failures:
        print("\nEl léxico dejaría fuera estos registros conocidos-buenos:", file=sys.stderr)
        for points, rid, bucket, detail in failures:
            print(f"  - {rid} ({points}, {bucket}) "
                  f"coincidencias={detail.get('matched', [])[:6]}", file=sys.stderr)
        sys.exit(1)

    print("Léxico calibrado: ningún conocido-bueno cae en rejected.")


if __name__ == "__main__":
    main()
