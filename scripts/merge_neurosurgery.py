#!/usr/bin/env python3
"""
merge_neurosurgery.py — Añade al catálogo las preguntas neuroquirúrgicas.

Consume drafts/ns-parts/*.json (salida de workflows/neurosurgery-map.mjs) y
las inserta como proyectos del dataset al que pertenecen.

Igual que ingest_records.py, esto NO se fía de lo que devolvió el modelo:
comprueba que el dataset exista, que los ids sean únicos, que la dificultad
esté en rango y que las habilidades sean etiquetas del vocabulario. Lo que no
pasa se descarta con motivo.

    python scripts/merge_neurosurgery.py [--dry-run]
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML.")

from scripts.lib import schema

ROOT = Path(__file__).resolve().parent.parent
PARTS = ROOT / "drafts" / "ns-parts"
DB = ROOT / "data" / "databases.yml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not PARTS.exists() or not any(PARTS.glob("*.json")):
        sys.exit("No hay drafts/ns-parts/. Corre antes workflows/neurosurgery-map.mjs")

    records = yaml.safe_load(DB.read_text(encoding="utf-8")) or []
    by_id = {r["id"]: r for r in records}
    existing_pids = {p.get("id") for r in records for p in schema.projects_of(r)}

    added, rejected = [], []
    per_sub = {}

    for path in sorted(PARTS.glob("*.json")):
        try:
            questions = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  ✗ {path.name}: ilegible ({e})")
            continue

        for q in questions:
            qid = q.get("id")
            ds = q.get("dataset_id")

            if not qid or not q.get("question_en"):
                rejected.append((qid or "?", "sin id o sin pregunta")); continue
            if qid in existing_pids:
                rejected.append((qid, "id de proyecto duplicado")); continue
            if ds not in by_id:
                # El modelo inventó un dataset que no está en el catálogo.
                rejected.append((qid, f"dataset inexistente: {ds}")); continue

            extras = [e for e in (q.get("extra_datasets") or []) if e in by_id]
            skills = schema.normalize_skills(q.get("skills"))
            lens = q.get("lens") if q.get("lens") in schema.VALID_LENS else None

            # Si los críticos no llegaron a correr (p. ej. límite de sesión a
            # media corrida), la pregunta es honestamente una idea SIN
            # VERIFICAR. El sitio ya la etiqueta como tal; afirmar lo
            # contrario sería exactamente el fallo que este proyecto evita.
            unverified = q.get("_critics_ran") is False

            proj = {
                "id": qid,
                "question_en": q["question_en"],
                "question_es": q.get("question_es") or q["question_en"],
                "lens": lens,
                "difficulty": max(1, min(5, int(round(float(q.get("difficulty") or 3))))),
                "effort_weeks": int(q.get("effort_weeks") or 10),
                "skills": skills,
                "extra_datasets": extras,
                "status": "open",
                "unverified": unverified,
                # Lo que distingue estas preguntas: por qué le importa a un
                # neurocirujano, y con qué escala se mide la respuesta.
                "clinical_rationale": q.get("clinical_rationale"),
                "outcome_measure": q.get("outcome_measure"),
                "subspecialty": q.get("subspecialty"),
                # El veredicto del neurocirujano se muestra, no se oculta:
                # "open" = incertidumbre clínica real; "well-studied" = buena
                # pregunta pero ya resuelta por ensayos. El estudiante elige.
                "clinical_verdict": ({"RELEVANT":"open","MARGINAL":"well-studied"}
                                     .get(q.get("clinical_verdict"))),
            }
            if q.get("novelty") in schema.VALID_NOVELTY:
                proj["novelty"] = q["novelty"]
            if q.get("still_open_because"):
                proj["still_open_because"] = q["still_open_because"]
            if q.get("feasibility") in schema.VALID_FEASIBILITY:
                proj["feasibility"] = q["feasibility"]

            proj = {k: v for k, v in proj.items() if v not in (None, "", [])}
            by_id[ds].setdefault("projects", []).append(proj)
            existing_pids.add(qid)
            added.append((qid, ds, q.get("subspecialty")))
            per_sub[q.get("subspecialty", "?")] = per_sub.get(q.get("subspecialty", "?"), 0) + 1

    # Red final: el esquema tiene que aceptar el catálogo entero.
    errors, _ = schema.validate(records)
    if errors:
        print("El esquema rechaza el resultado; no se escribe nada:", file=sys.stderr)
        for e in errors[:10]:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  añadidas   {len(added)}")
    for sub, n in sorted(per_sub.items()):
        print(f"    {sub:12s} {n}")
    print(f"  descartadas {len(rejected)}")
    for qid, why in rejected[:8]:
        print(f"    {qid}: {why}")

    if args.dry_run:
        print("\n(dry-run: no se escribió nada)")
        return

    if added:
        shutil.copy(DB, DB.with_suffix(".yml.bak"))
        DB.write_text(yaml.safe_dump(records, allow_unicode=True, sort_keys=False,
                                     default_flow_style=False, width=100),
                      encoding="utf-8")
        print(f"\n  -> data/databases.yml (copia previa en .bak)")
        print("  Siguiente: python3 scripts/build.py")


if __name__ == "__main__":
    main()
