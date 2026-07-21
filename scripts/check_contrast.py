#!/usr/bin/env python3
"""
check_contrast.py — Verifica WCAG 2.2 AA sobre los tokens de assets/css/tokens.css.

Lee los tokens directamente del CSS (no una copia) para que el CSS y esta
comprobación no puedan divergir. Sale con código 1 si algún par falla, de modo
que pueda correr en CI.

Umbrales:
    4.5:1  texto normal            (SC 1.4.3)
    3.0:1  texto grande / bordes   (SC 1.4.3 / 1.4.11)

Uso:
    python scripts/check_contrast.py [-v]
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "assets" / "css" / "tokens.css"

AA_TEXT, AA_UI = 4.5, 3.0


def luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = f(r), f(g), f(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    l1, l2 = sorted((luminance(a), luminance(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def parse_blocks(css):
    """{nombre_bloque: {token: hex}} para cada selector de tema del archivo."""
    # Los comentarios se quitan primero: si no, el capturador de selectores se
    # traga el comentario anterior y la clave del bloque deja de coincidir.
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    blocks = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css, re.S):
        sel = " ".join(sel.split()).lstrip("@").strip()
        if "--" not in body:
            continue
        pairs = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", body))
        if pairs:
            blocks.setdefault(sel, {}).update(pairs)
    return blocks


def resolve(tokens, base):
    """Fusiona un bloque de tema sobre las primitivas de :root."""
    out = dict(base)
    out.update(tokens)
    return out


MODALITIES = ["clinical", "neuroimaging", "genetics",
              "electrophysiology", "bci", "multimodal", "aggregator"]


def checks_for(t):
    """Pares (etiqueta, primer plano, fondo, umbral) para un tema resuelto."""
    out = []
    for surf in ("--canvas", "--surface", "--surface-raised"):
        for fg, thr in (("--text", AA_TEXT), ("--text-muted", AA_TEXT),
                        ("--text-faint", AA_TEXT), ("--accent", AA_TEXT),
                        ("--ok", AA_TEXT), ("--warn", AA_TEXT), ("--crit", AA_TEXT)):
            if fg in t and surf in t:
                out.append((f"{fg} sobre {surf}", t[fg], t[surf], thr))

    if "--text-on-accent" in t and "--accent-fill" in t:
        out.append(("--text-on-accent sobre --accent-fill", t["--text-on-accent"], t["--accent-fill"], AA_TEXT))
    if "--focus-ring" in t and "--canvas" in t:
        out.append(("--focus-ring sobre --canvas", t["--focus-ring"], t["--canvas"], AA_UI))
    if "--border-interactive" in t and "--surface-raised" in t:
        out.append(("--border-interactive sobre --surface-raised", t["--border-interactive"], t["--surface-raised"], AA_UI))

    for m in MODALITIES:
        fill, ink = f"--hue-{m}", f"--mod-{m}-ink"
        if fill in t and "--text-on-fill" in t:
            out.append((f"--text-on-fill sobre {fill} (insignia)", t["--text-on-fill"], t[fill], AA_TEXT))
        if ink in t and not t[ink].startswith("var") and "--surface" in t:
            out.append((f"{ink} sobre --surface (filete/texto)", t[ink], t["--surface"], AA_TEXT))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true", help="mostrar también los que pasan")
    args = ap.parse_args()

    css = TOKENS.read_text(encoding="utf-8")
    blocks = parse_blocks(css)

    primitives = {}
    for sel, toks in blocks.items():
        if sel.startswith(":root") and "data-theme" not in sel:
            primitives.update(toks)

    themes = {
        "oscuro": resolve(blocks.get(':root, :root[data-theme="dark"]', {}), primitives),
        "claro": resolve(blocks.get(':root[data-theme="light"]', {}), primitives),
    }
    for sel, toks in blocks.items():
        if "prefers-color-scheme: light" in sel or ":root:not([data-theme])" in sel:
            themes["claro (auto)"] = resolve(toks, primitives)

    failures = 0
    total = 0
    for name, tokens in themes.items():
        pairs = checks_for(tokens)
        if not pairs:
            continue
        print(f"\n=== tema {name} ===")
        for label, fg, bg, thr in pairs:
            total += 1
            r = ratio(fg, bg)
            ok = r >= thr
            if not ok:
                failures += 1
                print(f"  ❌ {label:52s} {r:5.2f}:1  (necesita {thr})  {fg} / {bg}")
            elif args.verbose:
                print(f"  ✅ {label:52s} {r:5.2f}:1")
        if not args.verbose:
            print(f"  {sum(1 for l, f, b, t in pairs if ratio(f, b) >= t)}/{len(pairs)} pares cumplen AA")

    print(f"\n{total - failures}/{total} pares cumplen WCAG 2.2 AA")
    if failures:
        print(f"FALLAN {failures} pares.", file=sys.stderr)
        sys.exit(1)
    print("Todos los pares de tokens cumplen AA.")


if __name__ == "__main__":
    main()
