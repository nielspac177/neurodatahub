#!/usr/bin/env python3
"""
components.py — Constructores de HTML.

Cada función recibe datos y devuelve una cadena. Ninguna toca el disco ni
lee plantillas, así que todas se pueden probar con asserts normales. Aquí vive
toda la iteración y la lógica condicional que deliberadamente no está en las
plantillas.
"""
from .render import attr, classes, esc
from .strings import S, access_label
from . import schema


# --------------------------------------------------------------------- #
# Piezas atómicas
# --------------------------------------------------------------------- #
def metric(value, label):
    return (f'<div class="metric"><b class="metric__value tnum">{esc(value)}</b>'
            f'<span class="metric__label">{esc(label)}</span></div>')


def modality_badge(modality, lang):
    if not modality:
        return ""
    return (f'<span class="badge badge--modality is-{esc(modality)}">'
            f'{esc(modality)}</span>')


def access_dot(access, lang):
    """Punto + texto. Nunca sólo color: el color es codificación redundante."""
    if not access:
        return ""
    return (f'<span class="access-dot is-{esc(access)}">'
            f'{esc(access_label(lang, access))}</span>')


def soft_badges(values, limit=None):
    vals = list(values or [])
    if limit and len(vals) > limit:
        shown, rest = vals[:limit], len(vals) - limit
        out = [f'<span class="badge badge--soft">{esc(v)}</span>' for v in shown]
        out.append(f'<span class="badge badge--soft">+{rest}</span>')
    else:
        out = [f'<span class="badge badge--soft">{esc(v)}</span>' for v in vals]
    return f'<div class="tag-row">{"".join(out)}</div>' if out else ""


def dl_inline(pairs):
    """pairs: [(term, value)] — omite valores vacíos."""
    items = [f"<div><dt>{esc(t)}</dt><dd>{esc(v)}</dd></div>"
             for t, v in pairs if v not in (None, "", [])]
    return f'<dl class="dl-inline">{"".join(items)}</dl>' if items else ""


def pips(level, lang, kind="difficulty"):
    """Cinco pips + palabra. La palabra es la señal primaria (SC 1.4.1)."""
    label = S(lang, kind)
    if not level:
        return (f'<p class="pips"><span class="pips__label">{esc(label)}</span>'
                f'<span class="pips__word">{esc(S(lang, "no_data"))}</span></p>')

    word = schema.DIFFICULTY_WORDS.get(level, ("", ""))[0 if lang == "en" else 1]
    track = "".join(
        f'<span class="{"pip pip--filled" if i <= level else "pip"}"></span>'
        for i in range(1, 6)
    )
    mod = " pips--feasibility" if kind == "feasibility" else ""
    return (
        f'<p class="pips{mod}" data-level="{level}">'
        f'<span class="pips__label">{esc(label)}</span>'
        f'<span class="pips__track" aria-hidden="true">{track}</span>'
        f'<span class="visually-hidden">{esc(label)} {level}/5, {esc(word)}</span>'
        f'<span class="pips__word" aria-hidden="true">{esc(word)}</span></p>'
    )


# --------------------------------------------------------------------- #
# Filtros
# --------------------------------------------------------------------- #
def chip_group(legend, name, values, counts=None, labeller=None):
    """Checkboxes nativos en un fieldset.

    Se eligen sobre botones aria-pressed porque el estado marcado, el nombre
    del grupo y la posición en el conjunto se anuncian de forma nativa, y
    porque el formulario funciona sin JS a través de la URL.
    """
    if not values:
        return ""
    items = []
    for v in values:
        n = (counts or {}).get(v)
        cid = f"f-{name}-{v}".replace(" ", "-").lower()
        text = labeller(v) if labeller else v
        count_html = (f'<span class="chip__count" aria-hidden="true">{n}</span>'
                      f'<span class="visually-hidden">, {n}</span>') if n else ""
        items.append(
            f'<input class="visually-hidden" type="checkbox" '
            f'{attr(id=cid, name=name, value=v)}>'
            f'<label class="chip" for="{esc(cid)}">{esc(text)}{count_html}</label>'
        )
    return (
        f'<fieldset class="chip-group">'
        f'<legend class="chip-group__legend">{esc(legend)}</legend>'
        f'<div class="chip-group__items">{"".join(items)}</div>'
        f'</fieldset>'
    )


# --------------------------------------------------------------------- #
# Tarjetas
# --------------------------------------------------------------------- #
def dataset_card(r, lang, root):
    desc = r.get(f"short_desc_{lang}") or r.get("short_desc_en") or r.get("short_desc_es") or ""
    mod = r.get("modality_primary") or ""
    href = f'{root}datasets/{esc(r["id"])}/'

    n_projects = len(schema.projects_of(r))
    proj_word = S(lang, "m_projects_one" if n_projects == 1 else "m_projects")
    proj_note = (f'<span class="badge badge--soft">{n_projects} '
                 f'{esc(proj_word)}</span>') if n_projects else ""

    return (
        f'<li class="{classes("card", "card--dataset", mod and f"card--{mod}")}" '
        f'{attr(data_id=r["id"], data_modality=mod, data_access=r.get("access"), data_category="|".join(r.get("disease_category") or []))}>'
        f'<div class="card__head">'
        f'<h3 class="card__title"><a href="{href}">{esc(r["name"])}</a></h3>'
        f'{modality_badge(mod, lang)}'
        f'</div>'
        f'{dl_inline([(S(lang, "subjects"), r.get("n_subjects")), (S(lang, "years"), r.get("years"))])}'
        f'<p class="card__desc">{esc(desc)}</p>'
        f'{soft_badges(r.get("diseases"), limit=4)}'
        f'<div class="card__foot">{access_dot(r.get("access"), lang)}{proj_note}'
        f'{compare_toggle(r, lang)}</div>'
        f'</li>'
    )


def compare_toggle(r, lang):
    """Casilla de comparación.

    Va por encima del enlace estirado de la tarjeta (z-index en CSS) y su
    nombre accesible incluye el dataset, para que en una rejilla de 21
    tarjetas no haya 21 casillas llamadas "Comparar".
    """
    cid = f'cmp-{r["id"]}'
    return (
        f'<label class="card__compare" for="{esc(cid)}">'
        f'<input type="checkbox" id="{esc(cid)}" data-compare="{esc(r["id"])}">'
        f'<span aria-hidden="true">{esc(S(lang, "compare"))}</span>'
        f'<span class="visually-hidden">{esc(S(lang, "compare_add", name=r["name"]))}</span>'
        f'</label>'
    )


def compare_tray(lang, root):
    """Bandeja pegajosa. Vacía y oculta hasta que se selecciona algo."""
    return (
        f'<div class="cmp-tray" id="cmp-tray" hidden role="region" '
        f'aria-label="{esc(S(lang, "compare_tray"))}">'
        f'<ol class="cmp-tray__list" id="cmp-tray-list"></ol>'
        f'<a class="btn btn--primary" id="cmp-go" href="{root}compare/">'
        f'{esc(S(lang, "compare_go"))}</a>'
        f'<button class="btn btn--ghost" type="button" id="cmp-clear">'
        f'{esc(S(lang, "clear"))}</button>'
        f'</div>'
    )


# Filas de la tabla comparativa: (clave de cadena, función extractora).
COMPARE_ROWS = [
    ("modality", lambda r, lang: r.get("modality_primary")),
    ("access_label", lambda r, lang: access_label(lang, r.get("access"))),
    ("subjects", lambda r, lang: r.get("n_subjects")),
    ("years", lambda r, lang: r.get("years")),
    ("region", lambda r, lang: r.get("region")),
    ("license", lambda r, lang: r.get("license")),
    ("provider", lambda r, lang: r.get("provider")),
]


def compare_table(records, lang, root):
    """Tabla real con th scope=row/col.

    Se usa <table> y no una rejilla de divs porque las cabeceras de fila y
    columna son justo lo que hace navegable esto en modo lectura de tablas.
    """
    if not records:
        return ""
    # Se pre-renderizan TODAS las columnas y el JS oculta las no elegidas.
    # Sin JS la página muestra la tabla completa, que sigue siendo útil; una
    # tabla construida en el cliente estaría simplemente vacía.
    heads = "".join(
        f'<th scope="col" data-ds="{esc(r["id"])}">'
        f'<a href="{root}datasets/{esc(r["id"])}/">{esc(r["name"])}</a></th>'
        for r in records
    )
    body = []
    for key, get in COMPARE_ROWS:
        cells = "".join(
            f'<td data-ds="{esc(r["id"])}">{esc(get(r, lang) or "—")}</td>' for r in records)
        body.append(f'<tr><th scope="row" class="cmp-table__rowhead">'
                    f'{esc(S(lang, key))}</th>{cells}</tr>')

    n_proj = "".join(
        f'<td data-ds="{esc(r["id"])}">{len(schema.projects_of(r))}</td>' for r in records)
    body.append(f'<tr><th scope="row" class="cmp-table__rowhead">'
                f'{esc(S(lang, "questions"))}</th>{n_proj}</tr>')

    return (
        f'<div style="overflow-x:auto"><table class="cmp-table">'
        f'<caption>{esc(S(lang, "compare_caption", n=len(records)))}</caption>'
        f'<thead><tr><td></td>{heads}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


def pack_card(p, lang, root):
    modules = p.get("modules") or []
    ds = {d for m in modules for d in (m.get("datasets") or [])}
    return (
        f'<li class="card card--pack">'
        f'<h3 class="card__title">'
        f'<a href="{root}packs/{esc(p["id"])}/">'
        f'{esc(p.get(f"title_{lang}") or p.get("title_en"))}</a></h3>'
        f'{dl_inline([(S(lang, "level"), p.get("level")), (S(lang, "duration"), p.get(f"duration_{lang}") or p.get("duration_en")), (S(lang, "m_datasets"), len(ds))])}'
        f'<p class="card__desc">{esc(p.get(f"summary_{lang}") or p.get("summary_en") or "")}</p>'
        f'{soft_badges(p.get("prerequisites"), limit=5)}'
        f'</li>'
    )


def project_card(p, lang, root):
    q = p.get(f"question_{lang}") or p.get("question_en") or p.get("question_es") or ""
    mod = p.get("modality_primary") or ""
    ds_href = f'{root}datasets/{esc(p["dataset_id"])}/'

    unverified = ""
    if p.get("unverified"):
        unverified = (f'<span class="badge badge--soft" title="{esc(S(lang, "unverified_note"))}">'
                      f'{esc(S(lang, "unverified"))}</span>')

    skills = soft_badges(p.get("skills"), limit=4)
    effort = ""
    if p.get("effort_weeks"):
        effort = (f'<span class="badge badge--soft">{p["effort_weeks"]} '
                  f'{esc(S(lang, "weeks"))}</span>')

    # La subespecialidad neuroquirúrgica se muestra como insignia y como
    # motivo clínico de una línea: es lo que un estudiante de medicina busca.
    sub = ""
    if p.get("subspecialty"):
        sub = (f'<span class="badge badge--soft is-subspecialty">'
               f'{esc(S(lang, "sub_" + p["subspecialty"]))}</span>')
    rationale = ""
    if p.get("clinical_rationale"):
        rationale = f'<p class="card__desc">{esc(p["clinical_rationale"])}</p>'

    return (
        f'<li class="{classes("card", "card--project", mod and f"card--{mod}")}" '
        f'{attr(data_id=p.get("id"), data_dataset=p["dataset_id"], data_modality=mod, data_access=p.get("access_hardest"), data_difficulty=p.get("difficulty") or "", data_lens=p.get("lens") or "", data_skills="|".join(p.get("skills") or []), data_subspecialty=p.get("subspecialty") or "")}>'
        f'<h3 class="card__title"><a href="{ds_href}#{esc(p.get("id", ""))}">{esc(q)}</a></h3>'
        f'{pips(p.get("difficulty"), lang, "difficulty")}'
        f'{rationale}'
        f'{skills}'
        f'<div class="card__foot">'
        f'{access_dot(p.get("access_hardest"), lang)}'
        f'<span class="badge badge--soft">{esc(p["dataset_name"])}</span>'
        f'{sub}{effort}{unverified}'
        f'</div>'
        f'</li>'
    )


# --------------------------------------------------------------------- #
# Piezas de la página de detalle
# --------------------------------------------------------------------- #
def access_steps(steps, lang):
    if not steps:
        return ""
    out = []
    for i, s in enumerate(steps, 1):
        text = s.get(f"step_{lang}") or s.get("step_en") or s.get("step_es") or ""
        # eta_<lang> con respaldo a `eta`: un plazo escrito sólo en un idioma
        # se filtraba a la otra página ("3-14 días" en la versión inglesa).
        eta_txt = s.get(f"eta_{lang}") or s.get("eta_en") or s.get("eta")
        eta = f'<p class="step__eta">{esc(eta_txt)}</p>' if eta_txt else ""
        body = (f'<a href="{esc(s["url"])}">{esc(text)}</a>' if s.get("url") else esc(text))
        out.append(f'<li class="step"><span class="step__num tnum" aria-hidden="true">{i}</span>'
                   f'<div><p>{body}</p>{eta}</div></li>')
    return f'<ol class="steps">{"".join(out)}</ol>'


def snippet(code, code_lang, dataset_name, lang):
    """Bloque de código con botón de copiar.

    El <pre> lleva tabindex para que un usuario de teclado pueda desplazarlo
    si desborda (SC 2.1.1), y el nombre accesible del botón incluye el dataset
    para que sea único en páginas con varios fragmentos.
    """
    if not code:
        return ""
    return (
        f'<div class="snippet">'
        f'<div class="snippet__bar">'
        f'<span class="badge badge--soft">{esc(code_lang)}</span>'
        f'<button class="btn btn--ghost snippet__copy" type="button" '
        f'data-copy-target="next">{esc(S(lang, "copy"))}'
        f'<span class="visually-hidden"> — {esc(code_lang)}, {esc(dataset_name)}</span>'
        f'</button></div>'
        f'<pre tabindex="0" role="group" aria-label="{esc(code_lang)} — {esc(dataset_name)}">'
        f'<code>{esc(code)}</code></pre></div>'
    )


def publications(pubs, lang):
    if not pubs:
        return ""
    out = []
    for p in pubs:
        if isinstance(p, str):
            out.append(f"<li>{esc(p)}</li>")
            continue
        title = esc(p.get("title", ""))
        if p.get("doi"):
            title = f'<a href="https://doi.org/{esc(p["doi"])}">{title}</a>'
        bits = [b for b in (p.get("year"), p.get("task"), p.get("method")) if b]
        meta = f' <span class="badge badge--soft">{esc(" · ".join(str(b) for b in bits))}</span>' if bits else ""
        out.append(f"<li>{title}{meta}</li>")
    return f'<ul class="prose">{"".join(out)}</ul>'


def project_detail(p, lang):
    """Bloque completo de un proyecto en la página de detalle del dataset."""
    q = p.get(f"question_{lang}") or p.get("question_en") or p.get("question_es") or ""

    rows = []
    if p.get("skills"):
        rows.append(f'<p><strong>{esc(S(lang, "needs"))}:</strong> {soft_badges(p["skills"])}</p>')
    if p.get("prior_work"):
        items = "".join(
            f'<li>{esc(w.get("what_was_done", ""))}'
            + (f' (<a href="https://doi.org/{esc(w["doi"])}">{esc(w.get("year", "DOI"))}</a>)' if w.get("doi") else "")
            + "</li>"
            for w in p["prior_work"] if isinstance(w, dict)
        )
        if items:
            rows.append(f'<h4>{esc(S(lang, "prior_work"))}</h4><ul>{items}</ul>')
    if p.get("still_open_because"):
        rows.append(f'<h4>{esc(S(lang, "still_open"))}</h4><p>{esc(p["still_open_because"])}</p>')

    warn = ""
    if p.get("unverified"):
        warn = (f'<p class="callout callout--warn">'
                f'<strong>{esc(S(lang, "unverified"))}.</strong> '
                f'{esc(S(lang, "unverified_note"))}</p>')

    meta = []
    if p.get("effort_weeks"):
        meta.append((S(lang, "effort"), f'{p["effort_weeks"]} {S(lang, "weeks")}'))
    if p.get("compute"):
        meta.append((S(lang, "compute"), p["compute"]))

    return (
        f'<article class="card" id="{esc(p.get("id", ""))}">'
        f'<h3 class="card__title">{esc(q)}</h3>'
        f'{pips(p.get("difficulty"), lang, "difficulty")}'
        f'{pips(p.get("feasibility_score"), lang, "feasibility") if p.get("feasibility_score") else ""}'
        f'{dl_inline(meta)}'
        f'{warn}'
        f'{"".join(rows)}'
        f'</article>'
    )


# --------------------------------------------------------------------- #
# Índice de búsqueda
# --------------------------------------------------------------------- #
def _fold(s):
    """Minúsculas sin acentos, para que 'epilepsia' encuentre 'Epilepsía'."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def dataset_haystack(r):
    """Pajar pre-normalizado.

    Se calcula en build.py y no en el navegador: bajar 150 cadenas a
    minúsculas en cada pulsación de tecla es trabajo desperdiciado.
    """
    parts = [r.get("name"), r.get("provider"), r.get("short_desc_en"), r.get("short_desc_es"),
             " ".join(r.get("diseases") or []), " ".join(r.get("tags") or []),
             " ".join(r.get("data_types") or []), r.get("region")]
    return _fold(" ".join(p for p in parts if p))


def project_haystack(p):
    parts = [p.get("question_en"), p.get("question_es"), p.get("dataset_name"),
             " ".join(p.get("skills") or []), p.get("lens"),
             p.get("clinical_rationale"), p.get("outcome_measure"), p.get("subspecialty"),
             " ".join(p.get("diseases") or [])]
    return _fold(" ".join(x for x in parts if x))
