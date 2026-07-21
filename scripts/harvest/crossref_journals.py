#!/usr/bin/env python3
"""
crossref_journals.py — Enumeración COMPLETA de revistas de datos por ISSN.

Este es el cambio de estrategia principal frente a la búsqueda por palabras
clave. Una revista de descriptores de datos publica, por definición, un
dataset por artículo. Enumerar todo lo que publica y luego triar da recall
completo; buscar por palabras clave sólo encuentra lo que uno pensó preguntar.

Volumen real (verificado): Data in Brief publicó 774 items en 2026 hasta julio.
Por eso el triaje posterior es obligatorio, no opcional.

Marca de agua: `from-index-date`, NO `from-pub-date`. Crossref indexa
depósitos con fecha de publicación retroactiva; filtrar por fecha de
publicación se los salta permanentemente.
"""
from datetime import date, timedelta

from ..lib.http import get_json, qs
from .base import Harvester, raw_item

JOURNALS = {
    "2052-4463": "Scientific Data",
    "2352-3409": "Data in Brief",
    "2047-217X": "GigaScience",
    "1053-8119": "NeuroImage",
    "2213-1582": "NeuroImage: Clinical",
    "1662-453X": "Frontiers in Neuroscience",
}

# Solape al releer: un depósito puede indexarse con retraso. Los duplicados no
# cuestan nada porque el libro mayor los colapsa.
OVERLAP_DAYS = 7


class CrossrefJournals(Harvester):
    name = "crossref"

    def incremental(self, limit=None, issns=None, since=None):
        targets = issns or list(JOURNALS)
        produced = 0

        for issn in targets:
            per_journal = self.state.setdefault(issn, {})
            watermark = since or per_journal.get("high_water_index_date")
            if not watermark:
                # Primera corrida: ventana corta. El histórico es --backfill.
                watermark = (date.today() - timedelta(days=30)).isoformat()
            else:
                watermark = (date.fromisoformat(watermark)
                             - timedelta(days=OVERLAP_DAYS)).isoformat()

            newest = watermark
            # El cursor NUNCA se persiste entre corridas: los cursores de
            # Crossref caducan. Lo persistente es la marca de agua de fecha.
            cursor = "*"
            seen_here = 0

            while True:
                url = ("https://api.crossref.org/journals/" + issn + "/works?" + qs(
                    filter=f"from-index-date:{watermark}",
                    rows=100, cursor=cursor, select=(
                        "DOI,title,abstract,URL,issued,container-title,"
                        "indexed,subject,type"),
                ))
                data = get_json(url)
                if not data:
                    break
                msg = data.get("message", {})
                items = msg.get("items", [])
                if not items:
                    break

                for w in items:
                    idx = ((w.get("indexed") or {}).get("date-time") or "")[:10]
                    if idx > newest:
                        newest = idx
                    yield self._to_item(w, issn)
                    produced += 1
                    seen_here += 1
                    if limit and produced >= limit:
                        break

                if limit and produced >= limit:
                    break
                cursor = msg.get("next-cursor")
                if not cursor or len(items) < 100:
                    break

            per_journal["high_water_index_date"] = newest
            per_journal["last_run"] = date.today().isoformat()
            per_journal["last_count"] = seen_here

            if limit and produced >= limit:
                return

    def backfill(self, limit=None, issns=None, years=3):
        since = (date.today() - timedelta(days=365 * years)).isoformat()
        return self.incremental(limit=limit, issns=issns, since=since)

    @staticmethod
    def _to_item(w, issn):
        title = " ".join(w.get("title") or []) or "(sin título)"
        container = " ".join(w.get("container-title") or []) or JOURNALS.get(issn, "")
        issued = (w.get("issued") or {}).get("date-parts") or [[]]
        pub = "-".join(str(x) for x in (issued[0] or []) if x)
        # Crossref devuelve el abstract como JATS; basta con quitar etiquetas.
        abstract = w.get("abstract") or ""
        if abstract:
            import re
            abstract = re.sub(r"<[^>]+>", " ", abstract)
        return raw_item(
            title=title,
            abstract=abstract,
            url=w.get("URL") or "",
            doi=w.get("DOI") or "",
            date=pub,
            venue=container,
            source="Crossref",
            raw_id=w.get("DOI") or "",
        )
