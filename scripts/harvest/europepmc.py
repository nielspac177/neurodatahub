#!/usr/bin/env python3
"""europepmc.py — Data descriptors y artículos de datos recientes (cola larga)."""
from datetime import date, timedelta

from ..lib.http import get_json, qs
from .base import Harvester, raw_item
from .openalex_keyword import DISEASES

DATA_TERMS = '(dataset OR database OR "data descriptor" OR benchmark OR "open data")'
ROTATE = 8


class EuropePMC(Harvester):
    name = "europepmc"

    def incremental(self, limit=None, days=21):
        since = (date.today() - timedelta(days=days)).isoformat()
        day_index = (date.today() - date(date.today().year, 1, 1)).days
        start = (day_index * ROTATE) % max(len(DISEASES), 1)
        selected = (DISEASES + DISEASES)[start:start + ROTATE]

        produced = 0
        for disease in selected:
            q = f'({disease}) AND {DATA_TERMS} AND (FIRST_PDATE:[{since} TO 3000])'
            data = get_json(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + qs(
                    query=q, format="json", pageSize=10, resultType="lite"))
            for r in ((data or {}).get("resultList") or {}).get("result", []):
                doi = r.get("doi") or ""
                yield raw_item(
                    title=r.get("title") or "",
                    abstract=r.get("abstractText") or "",
                    url=(f"https://doi.org/{doi}" if doi else
                         f"https://europepmc.org/abstract/{r.get('source','')}/{r.get('id','')}"),
                    doi=doi,
                    date=r.get("firstPublicationDate") or "",
                    venue=r.get("journalTitle") or "",
                    source="EuropePMC", query=disease,
                )
                produced += 1
                if limit and produced >= limit:
                    return
        self.state["last_run"] = date.today().isoformat()
