#!/usr/bin/env python3
"""
assemble_record.py — Une los archivos parciales de una corrida en el borrador.

Existe para quitar del pipeline el paso más caro y más tonto que tenía: un
agente que recibía el registro entero como texto (60-86k tokens de Opus) sólo
para volver a escribirlo en disco. Ahora cada etapa guarda su propia parte y
esto las une en Python, sin que ningún payload grande vuelva a pasar por un
modelo.

    python scripts/assemble_record.py <id>
    python scripts/assemble_record.py --all
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
PARTS = DRAFTS / "parts"

# nombre de la parte -> clave en el registro final
LAYOUT = {
    "scope": "scope",
    "draft": None,          # se fusiona en la raíz (name, fields, access_steps…)
    "literature": "literature",
    "ideas": None,          # aporta projects
    "grounding": ("critics", "grounding"),
    "access": ("critics", "access"),
    "novelty": ("critics", "novelty"),
    "feasibility": ("critics", "feasibility"),
}


def load(rid, part):
    f = PARTS / f"{rid}.{part}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  ✗ {rid}.{part}.json ilegible: {e}", file=sys.stderr)
        return None


def assemble(rid):
    record = {"id": rid, "critics": {}, "pipeline_version": "enrich/2.0"}

    draft = load(rid, "draft")
    if not draft:
        return None, "sin parte 'draft'"
    record["name"] = draft.get("name") or rid
    record["fields"] = draft.get("fields") or {}
    record["access_steps"] = draft.get("access_steps") or []
    record["starter_code"] = draft.get("starter_code") or {}

    for part, target in LAYOUT.items():
        if part == "draft":
            continue
        data = load(rid, part)
        if data is None:
            continue
        if part == "ideas":
            record["projects"] = data.get("projects") or []
        elif isinstance(target, tuple):
            # La forma tiene que coincidir EXACTAMENTE con lo que lee
            # ingest_records.py, que es quien aplica los vetos:
            #   grounding    -> {"verdicts": [...]}   (dict)
            #   access       -> {...}                 (dict)
            #   novelty/feas -> [...]                 (lista)
            if part == "grounding":
                v = data.get("verdicts") if isinstance(data, dict) else data
                record[target[0]][target[1]] = {"verdicts": v or []}
            elif part in ("novelty", "feasibility"):
                record[target[0]][target[1]] = (
                    data if isinstance(data, list) else (data or {}).get("verdicts") or [])
            else:
                record[target[0]][target[1]] = data
        elif target:
            record[target] = data

    record.setdefault("projects", [])
    record["critics"].setdefault("novelty", [])
    record["critics"].setdefault("feasibility", [])
    return record, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        ids = sorted({p.name.split(".")[0] for p in PARTS.glob("*.draft.json")})
    else:
        ids = args.ids
    if not ids:
        sys.exit("Nada que ensamblar. Uso: assemble_record.py <id> | --all")

    ok = 0
    for rid in ids:
        record, err = assemble(rid)
        if err:
            print(f"  ✗ {rid}: {err}")
            continue
        out = DRAFTS / f"{rid}.record.json"
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        n_p = len(record.get("projects") or [])
        n_c = sum(1 for k, v in record["critics"].items() if v)
        print(f"  ✓ {rid}: {n_p} proyectos, {n_c} críticos -> {out.name}")
        ok += 1
    print(f"\n{ok}/{len(ids)} registros ensamblados")


if __name__ == "__main__":
    main()
