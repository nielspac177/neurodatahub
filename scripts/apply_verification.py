#!/usr/bin/env python3
"""
apply_verification.py — Aplica los veredictos de verify-questions.mjs.

Lee drafts/verify-parts/*.json y actualiza data/databases.yml EN SITIO:
  - superviviente        -> unverified: false, con dificultad pesimista
  - IRRELEVANT/INFEASIBLE -> se elimina la pregunta
  - PUBLISHED            -> status: closed + closed_by_doi (sigue visible)
  - PARTIAL sin delta     -> se elimina

No se fía del workflow: vuelve a aplicar las reglas de veto en Python.

    python scripts/apply_verification.py [--dry-run]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML.")

from scripts.lib import schema

ROOT = Path(__file__).resolve().parent.parent
PARTS = ROOT / "drafts" / "verify-parts"
DB = ROOT / "data" / "databases.yml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not PARTS.exists() or not any(PARTS.glob("*.json")):
        sys.exit("No hay drafts/verify-parts/. Corre antes workflows/verify-questions.mjs")

    verdicts = {}
    for f in PARTS.glob("*.json"):
        try:
            v = json.loads(f.read_text(encoding="utf-8"))
            verdicts[v["id"]] = v
        except (json.JSONDecodeError, KeyError):
            print(f"  ✗ {f.name} ilegible", file=sys.stderr)

    records = yaml.safe_load(DB.read_text(encoding="utf-8")) or []
    promoted = removed = closed = untouched = 0

    for r in records:
        keep = []
        for p in r.get("projects") or []:
            v = verdicts.get(p.get("id"))
            if not v:
                keep.append(p)
                untouched += 1
                continue

            if v.get("clinical") == "IRRELEVANT" or v.get("feasible") == "INFEASIBLE":
                removed += 1
                continue  # se elimina la pregunta
            if v.get("novelty") == "PUBLISHED":
                p["status"] = "closed"
                if v.get("novelty_prior_doi"):
                    p["closed_by_doi"] = v["novelty_prior_doi"]
                p["unverified"] = False
                keep.append(p)
                closed += 1
                continue
            if v.get("novelty") == "PARTIAL" and not (v.get("novelty_still_open") or "").strip():
                removed += 1
                continue

            # Superviviente: verificado. Se muestra el veredicto clínico con
            # honestidad, igual que las preguntas nuevas.
            p["unverified"] = False
            cv = {"RELEVANT": "open", "MARGINAL": "well-studied"}.get(v.get("clinical"))
            if cv:
                p["clinical_verdict"] = cv
            if v.get("novelty") == "PARTIAL":
                p["novelty"] = "partial"
                p["still_open_because"] = v["novelty_still_open"]
                if v.get("novelty_prior_doi"):
                    p.setdefault("prior_work", [{"doi": v["novelty_prior_doi"],
                                                 "what_was_done": "trabajo previo cercano"}])
            elif v.get("novelty") == "NOVEL":
                p["novelty"] = "novel"
            if v.get("feasible") == "FEASIBLE_WITH_CAVEAT":
                p["feasibility"] = "feasible_with_caveat"
            # Dificultad pesimista.
            if isinstance(v.get("difficulty"), (int, float)):
                p["difficulty"] = max(int(p.get("difficulty") or 0),
                                      max(1, min(5, int(round(v["difficulty"]))))) or p.get("difficulty")
            keep.append(p)
            promoted += 1
        if "projects" in r:
            r["projects"] = keep

    errors, _ = schema.validate(records)
    if errors:
        print("El esquema rechaza el resultado; no se escribe nada:", file=sys.stderr)
        for e in errors[:10]:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)

    print(f"  verificadas y promovidas {promoted}")
    print(f"  cerradas (ya publicadas) {closed}")
    print(f"  eliminadas (veto)        {removed}")
    print(f"  sin cambios              {untouched}")

    if args.dry_run:
        print("\n(dry-run: no se escribió nada)")
        return

    shutil.copy(DB, DB.with_suffix(".yml.bak"))
    DB.write_text(yaml.safe_dump(records, allow_unicode=True, sort_keys=False,
                                 default_flow_style=False, width=100),
                  encoding="utf-8")
    print("\n  -> data/databases.yml (copia previa en .bak)")
    print("  Siguiente: python3 scripts/build.py")


if __name__ == "__main__":
    main()
