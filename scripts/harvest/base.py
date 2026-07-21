#!/usr/bin/env python3
"""
base.py — Contrato de un harvester.

Un harvester enumera su fuente desde una marca de agua y va cediendo items. El
orquestador guarda el estado SÓLO después de persistir los items, de modo que
una corrida que muere a la mitad vuelve a traer en vez de saltarse.
"""


def raw_item(**kw):
    """Forma normalizada que todos los harvesters devuelven."""
    return {
        "title": kw.get("title") or "",
        "abstract": kw.get("abstract") or "",
        "url": kw.get("url") or "",
        "doi": kw.get("doi") or "",
        "date": kw.get("date") or "",
        "venue": kw.get("venue") or "",
        "source": kw.get("source") or "",
        "raw_id": kw.get("raw_id") or "",
        "n_hint": kw.get("n_hint"),
        "query": kw.get("query") or "",
    }


class Harvester:
    name = "base"

    def __init__(self, state):
        # Sub-diccionario propio dentro de state/harvest_state.json.
        self.state = state.setdefault(self.name, {})

    def incremental(self, limit=None):
        """Cede RawItems nuevos desde la marca de agua y la avanza."""
        raise NotImplementedError

    def backfill(self, limit=None):
        """Recorrido histórico. Por defecto igual que incremental."""
        return self.incremental(limit=limit)
