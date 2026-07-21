#!/usr/bin/env python3
"""
reaudit_queue.py — Qué revalidar esta semana, y por qué.

Combina dos disparadores baratos (cambio en la página de acceso y crecimiento
de citas) con la antigüedad y la confianza, y produce una cola priorizada.
El trabajo caro con modelos sólo toca lo que estos disparadores encienden.

El crecimiento de citas es el disparador de novedad: los trabajos que citan un
dataset son exactamente la población que puede haber CERRADO una de tus
preguntas abiertas. Calcularlo cuesta una petición y cero tokens.

    python scripts/reaudit_queue.py [--top 20]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML.")

from scripts.lib import schema, state
from scripts.lib.http import get_json, qs
from scripts.lib.keys import doi_key

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "databases.yml"
REPORTS = ROOT / "reports"
CITE_STATE = state.STATE_DIR / "citations.json"

# Riesgo por tipo de acceso: equivocarse en un acceso controlado le cuesta
# semanas a un estudiante; equivocarse en uno abierto, un clic.
ACCESS_RISK = {"application": 1.0, "dua": 1.0, "credentialed": 0.8,
               "registration": 0.4, "open": 0.1}

CITATION_GROWTH_TRIGGER = 0.20


def citation_delta(records, verbose=True):
    """Crecimiento de citas por registro. Una petición por DOI, sin tokens."""
    st = state._read(CITE_STATE, {})
    today = date.today().isoformat()
    triggered = []

    for r in records:
        doi = doi_key(r.get("descriptor_doi") or r.get("doi"))
        if not doi:
            continue
        w = get_json(f"https://api.openalex.org/works/doi:{doi}?"
                     + qs(select="id,cited_by_count"), quiet=True)
        if not w:
            continue
        count = w.get("cited_by_count") or 0
        entry = st.setdefault(r["id"], {})
        prev = entry.get("count")
        entry.update({"doi": doi, "count": count, "checked": today})

        if prev is not None and prev > 0 and (count - prev) / prev >= CITATION_GROWTH_TRIGGER:
            entry["novelty_recheck"] = True
            triggered.append((r["id"], prev, count))
            if verbose:
                print(f"  ↑ {r['id']:22s} citas {prev} → {count} — revalidar novedad")

    state._write(CITE_STATE, st)
    return st, triggered


def priority(record, audit, cites, today):
    """Puntaje de prioridad. Cada término dice por qué el registro sube."""
    access = record.get("access", "open")
    interval = schema.REVERIFY_INTERVAL_DAYS.get(access, 365)

    lv = record.get("last_verified")
    try:
        age = (today - date.fromisoformat(str(lv))).days if lv else interval * 2
    except ValueError:
        age = interval * 2

    a = audit.get(record["id"], {})
    c = cites.get(record["id"], {})
    confidence = float(record.get("confidence") or
                       (0.9 if record.get("access_confidence") == "high" else 0.6))

    reasons, score = [], 0.0

    term = 2.0 * (age / interval)
    score += term
    if age > interval:
        reasons.append(f"vencido hace {age - interval} d")

    score += 1.5 * (1 - confidence)
    score += 1.0 * ACCESS_RISK.get(access, 0.5)

    if a.get("access_recheck"):
        score += 3.0
        reasons.append("la página de acceso cambió")
    if c.get("novelty_recheck"):
        score += 2.0
        reasons.append("las citas crecieron")
    if a.get("fail_streak", 0) > 0:
        score += 2.0
        reasons.append(f"enlace fallando ({a['fail_streak']} sem)")

    n_open = sum(1 for p in schema.projects_of(record) if p.get("status") != "closed")
    if n_open and any(p.get("unverified") for p in schema.projects_of(record)):
        score += 0.5
        reasons.append(f"{n_open} preguntas sin verificar")

    return round(score, 2), reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--skip-citations", action="store_true",
                    help="no consultar OpenAlex (útil sin red)")
    args = ap.parse_args()

    records = yaml.safe_load(DB.read_text(encoding="utf-8")) or []
    audit = state._read(state.STATE_DIR / "audit_state.json", {})

    if args.skip_citations:
        cites = state._read(CITE_STATE, {})
        triggered = []
    else:
        print("Comprobando crecimiento de citas…")
        cites, triggered = citation_delta(records)

    today = date.today()
    ranked = []
    for r in records:
        score, reasons = priority(r, audit, cites, today)
        ranked.append({"id": r["id"], "score": score, "reasons": reasons,
                       "access": r.get("access"),
                       "last_verified": r.get("last_verified")})
    ranked.sort(key=lambda x: -x["score"])
    queue = ranked[:args.top]

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "reaudit-queue.json").write_text(
        json.dumps({"generated": today.isoformat(),
                    "citation_triggers": len(triggered),
                    "queue": queue}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"\nCola de re-auditoría (top {len(queue)}):\n")
    for q in queue:
        why = "; ".join(q["reasons"]) or "rotación normal"
        print(f"  {q['score']:5.2f}  {q['id']:22s} {q['access']:13s} {why}")
    print(f"\n-> reports/reaudit-queue.json")


if __name__ == "__main__":
    main()
