#!/usr/bin/env python3
"""
research_update.py — OBSOLETO. Delega en harvest_run.py.

La búsqueda por palabras clave que vivía aquí se movió a
scripts/harvest/openalex_keyword.py y ahora es sólo la cola larga. El
descubrimiento principal pasó a ser la ENUMERACIÓN de revistas de datos por
ISSN y de repositorios por API (scripts/harvest/), que da recall completo en
vez de muestrear lo que uno pensó preguntar.

Se conserva para no romper invocaciones antiguas.
"""
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    print("research_update.py está obsoleto; ejecutando scripts/harvest_run.py",
          file=sys.stderr)
    target = str(Path(__file__).with_name("harvest_run.py"))
    sys.argv[0] = target
    runpy.run_path(target, run_name="__main__")
