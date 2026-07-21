#!/usr/bin/env python3
"""zenodo.py — Registros de tipo dataset en Zenodo (cola larga)."""
from datetime import date, timedelta

from ..lib.http import get_json, qs
from .base import Harvester, raw_item
from .openalex_keyword import DISEASES

ROTATE = 8


class Zenodo(Harvester):
    name = "zenodo"

    def incremental(self, limit=None, days=21):
        since = (date.today() - timedelta(days=days)).isoformat()
        day_index = (date.today() - date(date.today().year, 1, 1)).days
        start = (day_index * ROTATE) % max(len(DISEASES), 1)
        selected = (DISEASES + DISEASES)[start:start + ROTATE]

        produced = 0
        for disease in selected:
            q = f"{disease} (EEG OR MRI OR iEEG OR neuroimaging OR brain)"
            data = get_json("https://zenodo.org/api/records?" + qs(
                q=q, type="dataset", size=10, sort="mostrecent",
            ))
            for h in ((data or {}).get("hits") or {}).get("hits", []):
                meta = h.get("metadata") or {}
                pub = meta.get("publication_date") or ""
                if pub and pub < since:
                    continue
                yield raw_item(
                    title=meta.get("title") or "",
                    abstract=(meta.get("description") or "")[:2000],
                    url=(h.get("links") or {}).get("self_html") or h.get("doi_url") or "",
                    # conceptdoi une todas las versiones de un mismo registro;
                    # sin él, cada versión nueva parecería un dataset nuevo.
                    doi=h.get("conceptdoi") or h.get("doi") or "",
                    date=pub, venue="Zenodo", source="Zenodo", query=disease,
                )
                produced += 1
                if limit and produced >= limit:
                    return
        self.state["last_run"] = date.today().isoformat()
