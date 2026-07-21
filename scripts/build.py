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
import re
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
SRC_PACKS = ROOT / "data" / "coursepacks.yml"
OUT_PACKS = ROOT / "data" / "coursepacks.json"


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


# Imports relativos dentro de los módulos ES: `from './x.js'`,
# `import './x.js'`, `import('./x.js')`. Se les añade el mismo ?v= que al HTML.
_IMPORT_RX = re.compile(r"""(from\s+|import\s*\(?\s*)(['"])(\.{1,2}/[^'"?]+\.js)(\?v=[a-f0-9]+)?(['"])""")


def _strip_import_versions(text):
    """Quita cualquier ?v= de los imports, para hashear el contenido limpio."""
    return _IMPORT_RX.sub(lambda m: m.group(1) + m.group(2) + m.group(3) + m.group(5), text)


def asset_version():
    """Hash corto de CSS+JS, para romper caché sólo cuando cambian de verdad.

    Se hashea el JS SIN sus ?v= de import, de modo que el hash dependa sólo del
    código real. Si no, incrustar el hash en los imports lo cambiaría en la
    siguiente corrida (huevo y gallina) y el build dejaría de ser estable.
    """
    h = hashlib.sha1()
    for p in sorted((ROOT / "assets").rglob("*")):
        if p.suffix == ".css":
            h.update(p.read_bytes())
        elif p.suffix == ".js":
            h.update(_strip_import_versions(p.read_text(encoding="utf-8")).encode("utf-8"))
    return h.hexdigest()[:8]


def stamp_module_imports(version):
    """Añade ?v=<version> a los imports relativos de cada módulo ES.

    El cache-busting del <script> de entrada NO alcanza a los imports internos:
    `main.js?v=H` importa `./grid.js` SIN versión, así que el navegador puede
    servir un grid.js viejo en caché aunque main.js sea nuevo. Ese fue el bug:
    tras desplegar un arreglo en grid.js, los usuarios que volvían seguían con
    el grid.js antiguo y los filtros multivalor dejaban de funcionar.

    Idempotente: primero quita cualquier ?v= previo y luego pone el actual.
    """
    for p in (ROOT / "assets" / "js").rglob("*.js"):
        text = _strip_import_versions(p.read_text(encoding="utf-8"))
        stamped = _IMPORT_RX.sub(
            lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}?v={version}{m.group(5)}", text)
        if stamped != p.read_text(encoding="utf-8"):
            p.write_text(stamped, encoding="utf-8")


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
    packs = []
    if SRC_PACKS.exists():
        packs = yaml.safe_load(SRC_PACKS.read_text(encoding="utf-8")) or []

    errors, warnings = schema.validate(records)
    pack_errors, pack_warnings = schema.validate_packs(packs, records)
    errors += pack_errors
    warnings += pack_warnings

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
              f"{len(packs)} paquetes, {len(warnings)} avisos, 0 errores")
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
    if packs:
        dump(OUT_PACKS, {"count": len(packs), "packs": packs})

    pages.ASSET_V = asset_version()
    stamp_module_imports(pages.ASSET_V)   # cache-bust también los imports internos
    written = pages.build_all(records, projects, ROOT, packs=packs)

    print(f"OK: {len(records)} bases -> {OUT_DB.relative_to(ROOT)}")
    print(f"    {len(projects)} proyectos -> {OUT_PROJECTS.relative_to(ROOT)}")
    print(f"    {len(written)} páginas HTML (EN + ES)")
    if warnings:
        print(f"    {len(warnings)} avisos (no bloquean el build)")


if __name__ == "__main__":
    main()
