#!/usr/bin/env python3
"""
render.py — Motor de plantillas mínimo (sólo biblioteca estándar).

Las plantillas son HTML plano con huecos {{slot}}. No hay bucles ni
condicionales en las plantillas: toda iteración es una función de
components.py que recibe un dict y devuelve una cadena. Eso mantiene la capa
HTML testeable con asserts normales y evita que esto se convierta en un
framework accidental.

Un hueco sin valor lanza KeyError: un error tipográfico rompe el build en vez
de publicarse silenciosamente.
"""
import html
import json
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"

_SLOT = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
_cache = {}


def load(name):
    if name not in _cache:
        _cache[name] = (TEMPLATES / name).read_text(encoding="utf-8")
    return _cache[name]


def render(tpl, ctx):
    def sub(m):
        k = m.group(1)
        if k not in ctx:
            raise KeyError(f"el hueco '{{{{{k}}}}}' no tiene valor")
        v = ctx[k]
        return "" if v is None else str(v)
    return _SLOT.sub(sub, tpl)


def render_file(name, ctx):
    return render(load(name), ctx)


def esc(v):
    """Escapa para contenido y para atributos entrecomillados."""
    return "" if v is None else html.escape(str(v), quote=True)


def attr(**kw):
    """Atributos escapados. None/False se omiten; True queda como booleano."""
    out = []
    for k, v in kw.items():
        if v is None or v is False:
            continue
        k = k.rstrip("_").replace("_", "-")
        if v is True:
            out.append(k)
        else:
            out.append(f'{k}="{esc(v)}"')
    return " ".join(out)


def classes(*args):
    """Une clases ignorando falsy: classes('card', mod and f'card--{mod}')."""
    return " ".join(str(a) for a in args if a)


def json_script(obj, **attrs):
    """Isla JSON embebida.

    El escape de "</" es obligatorio: una descripción de dataset que contenga
    "</script>" cerraría la etiqueta y rompería la página.
    """
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" {attr(**attrs)}>{payload}</script>'
