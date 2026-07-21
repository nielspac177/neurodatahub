#!/usr/bin/env python3
"""
dandi.py — Enumeración del DANDI Archive (BRAIN Initiative) vía REST público.

876 dandisets al momento de escribir esto. Muy denso en electrofisiología
(Neuropixels, patch-clamp, óptica), que es justo donde el catálogo está más
flojo.
"""
from datetime import date

from ..lib.http import get_json, qs
from .base import Harvester, raw_item

API = "https://api.dandiarchive.org/api/dandisets/"


class Dandi(Harvester):
    name = "dandi"

    def incremental(self, limit=None):
        watermark = self.state.get("last_created", "")
        newest = watermark
        url = API + "?" + qs(page_size=100, ordering="-created")
        produced = 0

        while url:
            data = get_json(url)
            if not data:
                break
            results = data.get("results") or []
            if not results:
                break

            stop = False
            for d in results:
                created = (d.get("created") or "")[:19]
                if watermark and created <= watermark:
                    stop = True
                    break
                if created > newest:
                    newest = created
                item = self._to_item(d)
                if item:
                    yield item
                    produced += 1
                if limit and produced >= limit:
                    stop = True
                    break

            if stop:
                break
            url = data.get("next")

        self.state["last_created"] = newest
        self.state["last_run"] = date.today().isoformat()

    def backfill(self, limit=None):
        self.state.pop("last_created", None)
        return self.incremental(limit=limit)

    @staticmethod
    def _to_item(d):
        ident = d.get("identifier") or ""
        version = d.get("most_recent_published_version") or d.get("draft_version") or {}
        name = version.get("name") or ""
        if not name:
            return None

        meta = version.get("metadata") or {}
        # Las técnicas y especies son la señal más útil para el léxico.
        extras = []
        for key in ("measurementTechnique", "variableMeasured", "approach", "species"):
            v = meta.get(key)
            if isinstance(v, list):
                extras += [x.get("name", "") if isinstance(x, dict) else str(x) for x in v]
            elif v:
                extras.append(str(v))

        return raw_item(
            title=name,
            abstract=" ".join([version.get("description") or ""] + extras),
            url=f"https://dandiarchive.org/dandiset/{ident}",
            doi=(meta.get("doi") or ""),
            date=(d.get("created") or "")[:10],
            venue="DANDI Archive",
            source="DANDI",
            raw_id=f"DANDI:{ident}",
            n_hint=(version.get("asset_count") or None),
        )
