#!/usr/bin/env python3
"""
openneuro.py — Enumeración de OpenNeuro vía su GraphQL público (sin auth).

1.827 datasets al momento de escribir esto. Se recorren por `created`
descendente y se corta al llegar a la marca de agua, así que una corrida
semanal sólo toca lo nuevo.
"""
from datetime import date

from ..lib.http import post_json
from .base import Harvester, raw_item

ENDPOINT = "https://openneuro.org/crn/graphql"

QUERY = """
query($after: String) {
  datasets(first: 25, after: $after, orderBy: {created: descending}) {
    pageInfo { hasNextPage endCursor count }
    edges { node {
      id created
      latestSnapshot {
        tag
        description { Name Authors BIDSVersion }
        summary { subjects modalities tasks }
      }
    } }
  }
}
"""


class OpenNeuro(Harvester):
    name = "openneuro"

    def incremental(self, limit=None):
        watermark = self.state.get("last_created", "")
        newest = watermark
        after, produced = None, 0

        while True:
            data = post_json(ENDPOINT, {"query": QUERY, "variables": {"after": after}})
            if not data or "data" not in data:
                break
            block = (data["data"] or {}).get("datasets") or {}
            edges = block.get("edges") or []
            if not edges:
                break

            stop = False
            for edge in edges:
                node = edge.get("node") or {}
                created = (node.get("created") or "")[:19]
                if watermark and created <= watermark:
                    stop = True
                    break
                if created > newest:
                    newest = created
                yield self._to_item(node)
                produced += 1
                if limit and produced >= limit:
                    stop = True
                    break

            page = block.get("pageInfo") or {}
            if stop or not page.get("hasNextPage"):
                break
            after = page.get("endCursor")

        self.state["last_created"] = newest
        self.state["last_run"] = date.today().isoformat()

    def backfill(self, limit=None):
        self.state.pop("last_created", None)
        return self.incremental(limit=limit)

    @staticmethod
    def _to_item(node):
        ds_id = node.get("id") or ""
        snap = node.get("latestSnapshot") or {}
        desc = snap.get("description") or {}
        summary = snap.get("summary") or {}
        subjects = summary.get("subjects") or []
        modalities = summary.get("modalities") or []
        tasks = summary.get("tasks") or []

        # Las modalidades y tareas van al abstract para que el léxico las vea:
        # un dataset de OpenNeuro casi nunca trae prosa descriptiva.
        blob = " ".join(filter(None, [
            " ".join(modalities), " ".join(tasks),
            " ".join(desc.get("Authors") or [])[:200],
        ]))

        return raw_item(
            title=desc.get("Name") or ds_id,
            abstract=blob,
            url=f"https://openneuro.org/datasets/{ds_id}",
            date=(node.get("created") or "")[:10],
            venue="OpenNeuro",
            source="OpenNeuro",
            raw_id=ds_id,
            n_hint=len(subjects) if subjects else None,
        )
