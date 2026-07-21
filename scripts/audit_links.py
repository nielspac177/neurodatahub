#!/usr/bin/env python3
"""
audit_links.py — Salud de enlaces y detección de cambios en los términos de acceso.

Corre semanalmente en Actions, sin claves. Dos señales:

1. ¿El enlace sigue vivo? Un 404 durante DOS semanas seguidas marca el
   registro como needs_human. Nunca se borra en silencio: un enlace roto
   documentado le sirve más a un estudiante que un registro desaparecido.

2. ¿Cambió el texto de la página de acceso? Se guarda un sha256 del texto. Si
   cambia, se levanta access_recheck. Ésta es la señal más valiosa de todo el
   sistema de mantenimiento: es la que atrapa un dataset que pasa
   silenciosamente de abierto a requerir un DUA, que es exactamente el error
   que le cuesta semanas a un estudiante.

    python scripts/audit_links.py [--limit N]
"""
import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML.")

from scripts.fetch_evidence import fetch_html
from scripts.lib import state
from scripts.lib.http import head_status

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "databases.yml"
AUDIT_STATE = state.STATE_DIR / "audit_state.json"

FAIL_STREAK_TO_FLAG = 2


def load_state():
    return state._read(AUDIT_STATE, {})


def save_state(s):
    state._write(AUDIT_STATE, s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    records = yaml.safe_load(DB.read_text(encoding="utf-8")) or []
    if args.limit:
        records = records[:args.limit]

    st = load_state()
    today = date.today().isoformat()
    broken, moved, changed, ok = [], [], [], 0

    for r in records:
        rid, url = r["id"], r.get("url")
        if not url:
            continue
        entry = st.setdefault(rid, {"fail_streak": 0})

        status, final = head_status(url)
        entry["http_status"] = status
        entry["checked"] = today

        if status in (0, 404, 410):
            entry["fail_streak"] = entry.get("fail_streak", 0) + 1
            if entry["fail_streak"] >= FAIL_STREAK_TO_FLAG:
                broken.append((rid, status, entry["fail_streak"]))
            print(f"  ✗ {rid:22s} HTTP {status} (racha {entry['fail_streak']})")
            continue

        entry["fail_streak"] = 0
        entry["last_ok"] = today
        ok += 1

        if final and final.rstrip("/") != url.rstrip("/"):
            entry["redirects_to"] = final
            moved.append((rid, final))

        # Hash del texto de la página de acceso.
        text, _ = fetch_html(url)
        if text and not text.startswith("[fetch failed"):
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            prev = entry.get("access_page_sha256")
            entry["access_page_sha256"] = digest
            if prev and prev != digest:
                entry["access_recheck"] = True
                entry["access_changed_at"] = today
                changed.append(rid)
                print(f"  ⚠ {rid:22s} la página de acceso cambió — revalidar términos")

    save_state(st)

    print(f"\n  vivos           {ok}/{len(records)}")
    print(f"  rotos (>={FAIL_STREAK_TO_FLAG} sem) {len(broken)}")
    print(f"  redirigidos     {len(moved)}")
    print(f"  acceso cambiado {len(changed)}")

    if broken:
        print("\n  Marcar como needs_human:", ", ".join(b[0] for b in broken))
    if changed:
        print("  Revalidar acceso:", ", ".join(changed))


if __name__ == "__main__":
    main()
