#!/usr/bin/env python3
"""
state.py — Estado persistente entre corridas semanales.

Dos archivos:
    state/harvest_state.json  marcas de agua por fuente (dónde se quedó)
    state/seen.json           libro mayor de dedup

El libro mayor guarda TAMBIÉN los rechazos. Sin eso, los 774 artículos que
Data in Brief publica al año se vuelven a triar cada domingo, para siempre.

Escritura atómica (escribir a .tmp y renombrar) porque una corrida de Actions
puede morir a mitad y un JSON truncado dejaría el estado irrecuperable.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = ROOT / "state"
QUEUE_DIR = ROOT / "queue"

HARVEST_STATE = STATE_DIR / "harvest_state.json"
SEEN = STATE_DIR / "seen.json"


def _read(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    os.replace(tmp, path)


def load_harvest_state():
    return _read(HARVEST_STATE, {})


def save_harvest_state(state):
    _write(HARVEST_STATE, state)


class Ledger:
    """Libro mayor de dedup. Cada clave de un item apunta a la misma entrada."""

    def __init__(self):
        self.data = _read(SEEN, {})

    def seen(self, keys):
        """Devuelve la entrada si CUALQUIER clave autoritativa ya se conoce."""
        for name, value in keys.items():
            if name == "title" or not value:
                continue
            hit = self.data.get(f"{name}:{value}")
            if hit:
                return hit
        return None

    def title_collision(self, keys):
        """Coincidencia sólo por título: bandera para el crítico de duplicados."""
        t = keys.get("title")
        return self.data.get(f"title:{t}") if t else None

    def record(self, keys, disposition, when, record_id=None, score=None):
        entry = {"disposition": disposition, "first_seen": when}
        if record_id:
            entry["record_id"] = record_id
        if score is not None:
            entry["score"] = score
        for name, value in keys.items():
            if not value:
                continue
            k = f"{name}:{value}"
            # No pisar la fecha original de descubrimiento.
            if k in self.data:
                self.data[k].update({x: y for x, y in entry.items() if x != "first_seen"})
            else:
                self.data[k] = dict(entry)

    def save(self):
        _write(SEEN, self.data)

    def __len__(self):
        return len(self.data)


def append_jsonl(name, rows):
    """Añade a queue/<name>.jsonl. Append-only: la cola es auditable."""
    if not rows:
        return 0
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"{name}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def read_jsonl(name):
    path = QUEUE_DIR / f"{name}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out
