#!/usr/bin/env python3
"""
build.py — Convierte data/databases.yml en data/databases.json para el sitio estático.
Valida el esquema mínimo y calcula facetas (conteos por modalidad, enfermedad, acceso).

Uso:
    python scripts/build.py
"""
import json
import sys
from pathlib import Path
from collections import Counter

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML. Instala con: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "databases.yml"
OUT = ROOT / "data" / "databases.json"

REQUIRED = ["id", "name", "modality_primary", "diseases", "access", "url"]
VALID_MODALITIES = {
    "clinical", "neuroimaging", "genetics",
    "electrophysiology", "bci", "multimodal", "aggregator",
}
VALID_ACCESS = {"open", "registration", "credentialed", "dua", "application"}


def load():
    with open(SRC, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        sys.exit("databases.yml debe ser una lista de registros.")
    return data


def validate(records):
    errors = []
    ids = set()
    for i, r in enumerate(records):
        label = r.get("id", f"#{i}")
        for field in REQUIRED:
            if field not in r or r[field] in (None, "", []):
                errors.append(f"[{label}] falta campo obligatorio: {field}")
        if r.get("id") in ids:
            errors.append(f"[{label}] id duplicado")
        ids.add(r.get("id"))
        m = r.get("modality_primary")
        if m and m not in VALID_MODALITIES:
            errors.append(f"[{label}] modality_primary inválida: {m}")
        a = r.get("access")
        if a and a not in VALID_ACCESS:
            errors.append(f"[{label}] access inválido: {a}")
    return errors


def facets(records):
    mod = Counter()
    dis = Counter()
    acc = Counter()
    cat = Counter()
    for r in records:
        mod[r.get("modality_primary", "?")] += 1
        acc[r.get("access", "?")] += 1
        for d in r.get("diseases", []):
            dis[d] += 1
        for c in r.get("disease_category", []):
            cat[c] += 1
    return {
        "modality": dict(mod.most_common()),
        "disease": dict(dis.most_common()),
        "access": dict(acc.most_common()),
        "category": dict(cat.most_common()),
    }


def main():
    records = load()
    errors = validate(records)
    if errors:
        print("ERRORES DE VALIDACIÓN:", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)
    records.sort(key=lambda r: r["name"].lower())
    payload = {
        "generated_from": "data/databases.yml",
        "count": len(records),
        "facets": facets(records),
        "databases": records,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(records)} bases -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
