#!/usr/bin/env python3
"""
build.py — Convierte data/databases.yml en los JSON que consume el sitio.

Emite:
    data/databases.json  — catálogo + facetas (contrato estable; no romper la forma)
    data/projects.json   — índice plano de proyectos para la vista de estudiantes
    data/stats.json      — frescura, confianza y huecos de cobertura

La validación y las facetas viven en scripts/lib/schema.py, compartidas con
triage.py e ingest_records.py para que no puedan divergir.

Uso:
    python scripts/build.py [--check]

    --check  valida y reporta sin escribir nada (para CI y para pre-commit)
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML. Instala con: pip install pyyaml")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import pages, schema  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "databases.yml"
OUT_DB = ROOT / "data" / "databases.json"
OUT_PROJECTS = ROOT / "data" / "projects.json"
OUT_STATS = ROOT / "data" / "stats.json"


def load():
    with open(SRC, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        sys.exit("databases.yml debe ser una lista de registros.")
    return data


def dump(path, payload):
    """Escritura estable byte a byte.

    Los JSON y el HTML generados se commitean, así que cualquier
    no-determinismo (orden de claves, timestamps) produciría un PR con ruido
    cada domingo. Sin marcas de tiempo aquí a propósito.
    """
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def asset_version():
    """Hash corto de CSS+JS, para romper caché sólo cuando cambian de verdad.

    Debe ser determinista: el HTML generado se commitea, así que un valor que
    cambiara en cada corrida produciría un PR con ruido cada domingo.
    """
    h = hashlib.sha1()
    for p in sorted((ROOT / "assets").rglob("*")):
        if p.suffix in (".css", ".js"):
            h.update(p.read_bytes())
    return h.hexdigest()[:8]


def build_stats(records, projects):
    today = date.today()
    stale, no_desc = [], 0

    for r in records:
        lv = r.get("last_verified")
        interval = schema.REVERIFY_INTERVAL_DAYS.get(r.get("access"), 365)
        if lv:
            try:
                age = (today - date.fromisoformat(str(lv))).days
                if age > interval:
                    stale.append({"id": r["id"], "days": age, "interval": interval})
            except ValueError:
                pass
        else:
            stale.append({"id": r["id"], "days": None, "interval": interval})
        if not (r.get("short_desc_en") or r.get("short_desc_es")):
            no_desc += 1

    return {
        "n_datasets": len(records),
        "n_projects": len(projects),
        "n_projects_unverified": sum(1 for p in projects if p.get("unverified")),
        "n_datasets_missing_desc": no_desc,
        "stale": sorted(stale, key=lambda s: -(s["days"] or 10 ** 6)),
        "by_access": schema.facets(records)["access"],
        "coverage_gaps": schema.coverage_gaps(records),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="valida y reporta sin escribir archivos")
    args = ap.parse_args()

    records = load()
    errors, warnings = schema.validate(records)

    for w in warnings:
        print(f"  aviso: {w}", file=sys.stderr)

    if errors:
        print("ERRORES DE VALIDACIÓN:", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)

    records.sort(key=lambda r: r["name"].lower())
    projects = schema.flatten_projects(records)

    if args.check:
        print(f"OK (--check): {len(records)} bases, {len(projects)} proyectos, "
              f"{len(warnings)} avisos, 0 errores")
        return

    # Contrato estable: esta forma la consume index.html y cualquier tercero.
    dump(OUT_DB, {
        "generated_from": "data/databases.yml",
        "count": len(records),
        "facets": schema.facets(records),
        "databases": records,
    })
    dump(OUT_PROJECTS, {
        "generated_from": "data/databases.yml",
        "count": len(projects),
        "facets": schema.project_facets(projects),
        "projects": projects,
    })
    dump(OUT_STATS, build_stats(records, projects))

    pages.ASSET_V = asset_version()
    written = pages.build_all(records, projects, ROOT)

    print(f"OK: {len(records)} bases -> {OUT_DB.relative_to(ROOT)}")
    print(f"    {len(projects)} proyectos -> {OUT_PROJECTS.relative_to(ROOT)}")
    print(f"    {len(written)} páginas HTML (EN + ES)")
    if warnings:
        print(f"    {len(warnings)} avisos (no bloquean el build)")


if __name__ == "__main__":
    main()
