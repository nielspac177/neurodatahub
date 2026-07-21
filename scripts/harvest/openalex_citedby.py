#!/usr/bin/env python3
"""
openalex_citedby.py — El bucle de descubrimiento que se alimenta a sí mismo.

Para cada DOI de descriptor ya catalogado, se piden los trabajos que lo citan
y se quedan los que son a su vez datasets. Quien reutiliza un dataset suele
publicar uno derivado o compararlo con otro; ese vecindario del grafo de citas
es mucho más denso en datasets relevantes que cualquier búsqueda por palabras.

Además guarda el conteo de citas por registro, que es la señal que dispara la
re-comprobación de novedad: si las citas crecieron, alguien pudo haber cerrado
una de tus preguntas abiertas.
"""
from datetime import date

from ..lib.http import get_json, qs
from ..lib.keys import doi_key
from .base import Harvester, raw_item


class OpenAlexCitedBy(Harvester):
    name = "citedby"

    def incremental(self, limit=None, seed_dois=None):
        seeds = seed_dois or []
        produced = 0
        counts = self.state.setdefault("counts", {})

        for doi in seeds:
            d = doi_key(doi)
            if not d:
                continue

            work = get_json(f"https://api.openalex.org/works/doi:{d}?" + qs(select="id,cited_by_count"),
                            quiet=True)
            if not work or not work.get("id"):
                continue

            wid = work["id"].rsplit("/", 1)[-1]
            total = work.get("cited_by_count") or 0
            prev = (counts.get(d) or {}).get("count")
            counts[d] = {"work_id": wid, "count": total,
                         "checked": date.today().isoformat(),
                         "previous": prev}

            # Sólo se expande el vecindario si hay citas nuevas.
            if prev is not None and total <= prev:
                continue

            data = get_json("https://api.openalex.org/works?" + qs(
                filter=f"cites:{wid},type:dataset", per_page=25,
                select="id,doi,title,publication_date,primary_location",
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
                    source="OpenAlex/cited_by",
                    query=f"cites:{d}",
                )
                produced += 1
                if limit and produced >= limit:
                    self.state["last_run"] = date.today().isoformat()
                    return

        self.state["last_run"] = date.today().isoformat()

    def citation_counts(self):
        return self.state.get("counts", {})
