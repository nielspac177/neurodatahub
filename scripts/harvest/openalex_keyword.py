#!/usr/bin/env python3
"""
openalex_keyword.py — Búsqueda por palabras clave (SÓLO cola larga).

Es la estrategia original de research_update.py, conservada porque encuentra
datasets alojados en sitios que no enumeramos. Ya no es el mecanismo
principal: las fuentes enumerables dan recall completo y ésta sólo muestrea.

La matriz enfermedad x modalidad rota por día del año para no repetir siempre
las mismas consultas.
"""
from datetime import date, timedelta

from ..lib.http import get_json, qs
from .base import Harvester, raw_item

DISEASES = [
    "Parkinson disease", "epilepsy", "glioma glioblastoma", "ischemic stroke",
    "Alzheimer disease", "major depressive disorder", "schizophrenia",
    "traumatic brain injury", "multiple sclerosis", "autism spectrum disorder",
    "ADHD", "obsessive compulsive disorder", "deep brain stimulation",
    "subarachnoid haemorrhage", "intracranial aneurysm", "hydrocephalus",
]
MODALITIES = [
    "EEG dataset", "iEEG intracranial dataset", "MRI open dataset",
    "fMRI dataset", "GWAS summary statistics", "brain computer interface dataset",
    "electronic health record ICU database", "PET imaging dataset",
    "MEG dataset", "diffusion MRI dataset",
]

ROTATE = 24


class OpenAlexKeyword(Harvester):
    name = "openalex"

    def incremental(self, limit=None, days=21):
        since = (date.today() - timedelta(days=days)).isoformat()
        queries = [f"{d} {m}" for d in DISEASES for m in MODALITIES]
        day_index = (date.today() - date(date.today().year, 1, 1)).days
        start = (day_index * ROTATE) % max(len(queries), 1)
        selected = (queries + queries)[start:start + ROTATE]

        produced = 0
        for q in selected:
            data = get_json("https://api.openalex.org/works?" + qs(
                search=q,
                filter=f"type:dataset,from_publication_date:{since}",
                per_page=5, sort="publication_date:desc",
            ))
            for w in (data or {}).get("results", []):
                loc = w.get("primary_location") or {}
                src = loc.get("source") or {}
                yield raw_item(
                    title=w.get("title") or "",
                    url=loc.get("landing_page_url") or w.get("id") or "",
                    doi=(w.get("doi") or "").replace("https://doi.org/", ""),
                    date=w.get("publication_date") or "",
                    venue=src.get("display_name") or "",
                    source="OpenAlex", query=q,
                )
                produced += 1
                if limit and produced >= limit:
                    self.state["rotation_index"] = start
                    return
        self.state["rotation_index"] = start
        self.state["last_run"] = date.today().isoformat()
