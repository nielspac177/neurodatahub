#!/usr/bin/env python3
"""
pages.py — Ensambla cada tipo de página y la escribe en disco.

Rutas: EN en la raíz, ES bajo /es/. El idioma es una ruta, no un conmutador
en tiempo de ejecución: un conmutador JS no puede traducir access_notes, la
prosa de los proyectos ni el <title>, y muestra inglés antes de cambiar.

Todos los enlaces son relativos vía {{root}} porque un sitio de proyecto de
GitHub Pages vive en /<repo>/ y las rutas absolutas se romperían.
"""
from pathlib import Path

from . import components as C
from . import schema
from .render import esc, json_script, render_file
from .strings import S, js_strings

LANGS = ("en", "es")


def _prefix(lang):
    return "" if lang == "en" else "es/"


def _root(depth):
    return "../" * depth


def _shell(lang, page, title, description, main, depth, alt_href, islands=""):
    root = _root(depth)
    prefix = _prefix(lang)
    alt_lang = "es" if lang == "en" else "en"
    return render_file("base.html", {
        "lang": lang,
        "page": page,
        "title": esc(title),
        "description": esc(description),
        "main": main,
        "root": root,
        "asset_v": ASSET_V,
        "skip": esc(S(lang, "skip")),
        "nav_label": esc(S(lang, "nav_datasets")),
        "href_datasets": f"{root}{prefix}",
        "href_projects": f"{root}{prefix}projects/",
        "href_packs": f"{root}{prefix}packs/",
        "href_compare": f"{root}{prefix}compare/",
        "nav_packs": esc(S(lang, "nav_packs")),
        "nav_compare": esc(S(lang, "nav_compare")),
        "current_packs": 'aria-current="page"' if page in ("packs", "pack") else "",
        "current_compare": 'aria-current="page"' if page == "compare" else "",
        "nav_datasets": esc(S(lang, "nav_datasets")),
        "nav_projects": esc(S(lang, "nav_projects")),
        "current_datasets": 'aria-current="page"' if page == "datasets" else "",
        "current_projects": 'aria-current="page"' if page == "projects" else "",
        "alt_href": alt_href,
        "alt_lang": alt_lang,
        "lang_switch": esc(S(lang, "lang_switch")),
        "theme_label": esc(S(lang, "theme")),
        "footer": esc(S(lang, "footer")),
        "data_islands": islands,
    })


# Se recalcula en build.py a partir del hash de los assets, para romper caché
# sólo cuando el CSS/JS cambia de verdad.
ASSET_V = "1"


def _write(out_root, rel, html):
    path = Path(out_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


# --------------------------------------------------------------------- #
# Portada: rejilla de datasets
# --------------------------------------------------------------------- #
def build_home(records, projects, lang, out_root):
    depth = 0 if lang == "en" else 1
    root = _root(depth)
    facets = schema.facets(records)

    rail = "".join([
        f'<div class="rail__head"><span class="rail__title">{esc(S(lang, "filters"))}</span>'
        f'<button class="btn btn--ghost" type="button" data-clear-filters>{esc(S(lang, "clear"))}</button></div>',
        f'<a class="visually-hidden skip-link" href="#results-heading">{esc(S(lang, "skip_filters"))}</a>',
        C.chip_group(S(lang, "f_modality"), "m",
                     [m for m in schema.MODALITY_ORDER if facets["modality"].get(m)],
                     facets["modality"]),
        C.chip_group(S(lang, "f_category"), "c", list(facets["category"]), facets["category"]),
        C.chip_group(S(lang, "f_access"), "a",
                     [a for a in schema.ACCESS_RESTRICTIVENESS if facets["access"].get(a)],
                     facets["access"],
                     labeller=lambda v: S(lang, f"access_{v}")),
    ])

    cards = "".join(C.dataset_card(r, lang, root) for r in records)
    n_open = facets["access"].get("open", 0)

    main = f"""
<section class="hero">
  <div class="container">
    <h1>{esc(S(lang, "tagline"))}</h1>
    <p class="hero__lede">{esc(S(lang, "lede"))}</p>
    <div class="metrics">
      {C.metric(len(records), S(lang, "m_datasets"))}
      {C.metric(len(projects), S(lang, "m_projects"))}
      {C.metric(n_open, S(lang, "m_open"))}
    </div>
  </div>
</section>

<div class="container workspace">
  <form class="rail" id="filters" method="get" role="search" aria-label="{esc(S(lang, "filters"))}">
    {rail}
    <noscript><button class="btn btn--primary" type="submit">{esc(S(lang, "filters"))}</button></noscript>
  </form>

  <div>
    <div class="toolbar">
      <input class="search" type="search" id="q" name="q"
             placeholder="{esc(S(lang, "search_ph"))}"
             aria-label="{esc(S(lang, "search_ph"))}" form="filters">
    </div>
    <h2 id="results-heading" class="focus-target" tabindex="-1">{esc(S(lang, "results_heading"))}</h2>
    <p class="results-status" id="results-status">{esc(S(lang, "count", n=len(records), total=len(records)))}</p>
    <ul class="grid" id="results">{cards}</ul>
    <p class="empty-state" id="empty" hidden>
      <strong>{esc(S(lang, "none"))}</strong><br>{esc(S(lang, "none_hint"))}
    </p>
  </div>
</div>
{C.compare_tray(lang, root)}
"""
    islands = json_script(
        [{"id": r["id"], "hay": C.dataset_haystack(r)} for r in records],
        id="search-index",
    ) + json_script(js_strings(lang), id="i18n")

    alt = f'{root}es/' if lang == "en" else f'{root}'
    html = _shell(lang, "datasets",
                  f'{S(lang, "site_name")} — {S(lang, "tagline")}',
                  S(lang, "lede"), main, depth, alt, islands)
    return _write(out_root, f"{_prefix(lang)}index.html", html)


# --------------------------------------------------------------------- #
# Índice de proyectos
# --------------------------------------------------------------------- #
def build_projects(records, projects, lang, out_root):
    depth = 1 if lang == "en" else 2
    root = _root(depth)
    pf = schema.project_facets(projects)

    diff_values = [d for d in ("1", "2", "3", "4", "5") if pf["difficulty"].get(d)]
    rail = "".join([
        f'<div class="rail__head"><span class="rail__title">{esc(S(lang, "filters"))}</span>'
        f'<button class="btn btn--ghost" type="button" data-clear-filters>{esc(S(lang, "clear"))}</button></div>',
        f'<a class="visually-hidden skip-link" href="#results-heading">{esc(S(lang, "skip_filters"))}</a>',
        C.chip_group(S(lang, "f_subspecialty"), "sub",
                     list(pf.get("subspecialty", {})),
                     pf.get("subspecialty", {}),
                     labeller=lambda v: S(lang, "sub_" + v)),
        C.chip_group(S(lang, "f_difficulty"), "d", diff_values, pf["difficulty"],
                     labeller=lambda v: schema.DIFFICULTY_WORDS[int(v)][0 if lang == "en" else 1]),
        C.chip_group(S(lang, "f_modality"), "m",
                     [m for m in schema.MODALITY_ORDER if pf["modality"].get(m)], pf["modality"]),
        C.chip_group(S(lang, "f_access"), "a",
                     [a for a in schema.ACCESS_RESTRICTIVENESS if pf.get("access", {}).get(a)],
                     pf.get("access", {}), labeller=lambda v: S(lang, f"access_{v}")),
        C.chip_group(S(lang, "f_skills"), "s", list(pf["skills"])[:20], pf["skills"]),
    ])

    cards = "".join(C.project_card(p, lang, root) for p in projects)

    main = f"""
<section class="hero">
  <div class="container">
    <h1>{esc(S(lang, "projects_heading"))}</h1>
    <p class="hero__lede">{esc(S(lang, "lede"))}</p>
  </div>
</section>

<div class="container workspace">
  <form class="rail" id="filters" method="get" role="search" aria-label="{esc(S(lang, "filters"))}">
    {rail}
  </form>
  <div>
    <div class="toolbar">
      <input class="search" type="search" id="q" name="q"
             placeholder="{esc(S(lang, "search_projects_ph"))}"
             aria-label="{esc(S(lang, "search_projects_ph"))}" form="filters">
    </div>
    <h2 id="results-heading" class="focus-target" tabindex="-1">{esc(S(lang, "projects_heading"))}</h2>
    <p class="results-status" id="results-status">{esc(S(lang, "count_projects", n=len(projects), total=len(projects)))}</p>
    <ul class="grid" id="results">{cards}</ul>
    <p class="empty-state" id="empty" hidden>
      <strong>{esc(S(lang, "none"))}</strong><br>{esc(S(lang, "none_hint"))}
    </p>
  </div>
</div>
"""
    islands = json_script(
        [{"id": p.get("id"), "hay": C.project_haystack(p)} for p in projects],
        id="search-index",
    ) + json_script(js_strings(lang), id="i18n")

    alt = (f"{root}es/projects/" if lang == "en" else f"{root}projects/")
    html = _shell(lang, "projects", f'{S(lang, "projects_heading")} — {S(lang, "site_name")}',
                  S(lang, "lede"), main, depth, alt, islands)
    return _write(out_root, f"{_prefix(lang)}projects/index.html", html)


# --------------------------------------------------------------------- #
# Detalle de un dataset
# --------------------------------------------------------------------- #
def build_detail(r, lang, out_root):
    depth = 2 if lang == "en" else 3
    root = _root(depth)
    prefix = _prefix(lang)
    desc = r.get(f"short_desc_{lang}") or r.get("short_desc_en") or r.get("short_desc_es") or ""
    projs = schema.projects_of(r)

    meta = C.dl_inline([
        (S(lang, "provider"), r.get("provider")),
        (S(lang, "subjects"), r.get("n_subjects")),
        (S(lang, "years"), r.get("years")),
        (S(lang, "region"), r.get("region")),
        (S(lang, "license"), r.get("license")),
    ])

    steps = C.access_steps(r.get("access_steps"), lang)
    if not steps and r.get("access_notes"):
        steps = f'<p class="callout callout--info">{esc(r["access_notes"])}</p>'

    sc = r.get("starter_code") or {}
    snippets = "".join(
        C.snippet(sc.get(k), lbl, r["name"], lang)
        for k, lbl in (("python", "Python"), ("r", "R"), ("bash", "Shell"))
    )

    pubs = C.publications(r.get("key_publications"), lang)
    proj_html = "".join(C.project_detail(p, lang) for p in projs)

    sections = []
    if steps:
        sections.append(f'<section><h2>{esc(S(lang, "access_how"))}</h2>{steps}</section>')
    if snippets:
        sections.append(f'<section><h2>{esc(S(lang, "starter"))}</h2>{snippets}</section>')
    if pubs:
        sections.append(f'<section><h2>{esc(S(lang, "pubs"))}</h2>{pubs}</section>')
    if proj_html:
        sections.append(f'<section><h2>{esc(S(lang, "questions"))}</h2>'
                        f'<div class="grid">{proj_html}</div></section>')

    body = "".join(f'<div style="margin-top:var(--sp-7)">{s}</div>' for s in sections)

    main = f"""
<section class="hero">
  <div class="container">
    <p><a href="{root}{prefix}">&larr; {esc(S(lang, "back"))}</a></p>
    <h1>{esc(r["name"])}</h1>
    <div class="tag-row" style="margin-top:var(--sp-4)">
      {C.modality_badge(r.get("modality_primary"), lang)}
      {C.access_dot(r.get("access"), lang)}
    </div>
    <p class="hero__lede">{esc(desc)}</p>
    <div style="margin-top:var(--sp-5)">{meta}</div>
    <p style="margin-top:var(--sp-5)">
      <a class="btn btn--primary" href="{esc(r.get("url", "#"))}" rel="noopener">
        {esc(S(lang, "visit"))}</a>
    </p>
  </div>
</section>
<div class="container">{body}</div>
"""
    alt = (f'{root}es/datasets/{r["id"]}/' if lang == "en" else f'{root}datasets/{r["id"]}/')
    html = _shell(lang, "detail", f'{r["name"]} — {S(lang, "site_name")}', desc, main, depth, alt)
    return _write(out_root, f'{prefix}datasets/{r["id"]}/index.html', html)


# --------------------------------------------------------------------- #
# Comparación
# --------------------------------------------------------------------- #
def build_compare(records, lang, out_root):
    depth = 1 if lang == "en" else 2
    root = _root(depth)
    main = f"""
<section class="hero">
  <div class="container">
    <h1>{esc(S(lang, "compare_heading"))}</h1>
    <p class="hero__lede">{esc(S(lang, "compare_empty"))}</p>
  </div>
</section>
<div class="container" style="padding-block:var(--sp-7)">
  {C.compare_table(records, lang, root)}
</div>
"""
    islands = json_script(js_strings(lang), id="i18n")
    alt = f"{root}es/compare/" if lang == "en" else f"{root}compare/"
    html = _shell(lang, "compare",
                  f'{S(lang, "compare_heading")} — {S(lang, "site_name")}',
                  S(lang, "compare_empty"), main, depth, alt, islands)
    return _write(out_root, f"{_prefix(lang)}compare/index.html", html)


# --------------------------------------------------------------------- #
# Paquetes de curso
# --------------------------------------------------------------------- #
def build_packs_index(packs, lang, out_root):
    depth = 1 if lang == "en" else 2
    root = _root(depth)
    cards = "".join(C.pack_card(p, lang, root) for p in packs)
    main = f"""
<section class="hero">
  <div class="container">
    <h1>{esc(S(lang, "packs_heading"))}</h1>
    <p class="hero__lede">{esc(S(lang, "packs_lede"))}</p>
  </div>
</section>
<div class="container" style="padding-block:var(--sp-7)">
  <ul class="grid">{cards}</ul>
</div>
"""
    alt = f"{root}es/packs/" if lang == "en" else f"{root}packs/"
    html = _shell(lang, "packs", f'{S(lang, "packs_heading")} — {S(lang, "site_name")}',
                  S(lang, "packs_lede"), main, depth, alt,
                  json_script(js_strings(lang), id="i18n"))
    return _write(out_root, f"{_prefix(lang)}packs/index.html", html)


def build_pack(pack, records, lang, out_root):
    depth = 2 if lang == "en" else 3
    root = _root(depth)
    by_id = {r["id"]: r for r in records}
    projects = {p["id"]: (p, r) for r in records for p in schema.projects_of(r) if p.get("id")}

    weeks = []
    for m in pack.get("modules") or []:
        ds_links = " · ".join(
            f'<a href="{root}datasets/{esc(i)}/">{esc(by_id[i]["name"])}</a>'
            for i in (m.get("datasets") or []) if i in by_id)
        pr = []
        for pid in (m.get("projects") or []):
            if pid in projects:
                proj, owner = projects[pid]
                q = proj.get(f"question_{lang}") or proj.get("question_en") or ""
                pr.append(f'<li><a href="{root}datasets/{esc(owner["id"])}/#{esc(pid)}">'
                          f'{esc(q[:120])}</a></li>')
        notes = m.get(f"notes_{lang}") or m.get("notes_en") or ""
        weeks.append(
            f'<li class="step"><span class="step__num tnum" aria-hidden="true">{m.get("week", "?")}</span>'
            f'<div><h3>{esc(m.get(f"title_{lang}") or m.get("title_en") or "")}</h3>'
            + (f'<p>{ds_links}</p>' if ds_links else "")
            + (f'<ul>{"".join(pr)}</ul>' if pr else "")
            + (f'<p class="step__eta">{esc(notes)}</p>' if notes else "")
            + "</div></li>")

    outcomes = "".join(f"<li>{esc(o)}</li>"
                       for o in (pack.get(f"learning_outcomes_{lang}")
                                 or pack.get("learning_outcomes_en") or []))
    sections = []
    if outcomes:
        sections.append(f'<section><h2>{esc(S(lang, "pack_outcomes"))}</h2>'
                        f'<ul class="prose">{outcomes}</ul></section>')
    if weeks:
        sections.append(f'<section><h2>{esc(S(lang, "pack_modules"))}</h2>'
                        f'<ol class="steps">{"".join(weeks)}</ol></section>')
    assessment = pack.get(f"assessment_{lang}") or pack.get("assessment_en")
    if assessment:
        sections.append(f'<section><h2>{esc(S(lang, "pack_assessment"))}</h2>'
                        f'<p class="prose">{esc(assessment)}</p></section>')

    body = "".join(f'<div style="margin-top:var(--sp-7)">{x}</div>' for x in sections)
    title = pack.get(f"title_{lang}") or pack.get("title_en") or pack["id"]
    summary = pack.get(f"summary_{lang}") or pack.get("summary_en") or ""

    main = f"""
<section class="hero">
  <div class="container">
    <p><a href="{root}{_prefix(lang)}packs/">&larr; {esc(S(lang, "packs_heading"))}</a></p>
    <h1>{esc(title)}</h1>
    <p class="hero__lede">{esc(summary)}</p>
    {C.dl_inline([(S(lang, "level"), pack.get("level")), (S(lang, "duration"), pack.get(f"duration_{lang}") or pack.get("duration_en"))])}
    {C.soft_badges(pack.get("prerequisites"))}
  </div>
</section>
<div class="container">{body}</div>
"""
    alt = (f'{root}es/packs/{pack["id"]}/' if lang == "en"
           else f'{root}packs/{pack["id"]}/')
    html = _shell(lang, "pack", f'{title} — {S(lang, "site_name")}', summary,
                  main, depth, alt, json_script(js_strings(lang), id="i18n"))
    return _write(out_root, f'{_prefix(lang)}packs/{pack["id"]}/index.html', html)


def build_all(records, projects, out_root, packs=None):
    written = []
    for lang in LANGS:
        lang_projects = [p for p in projects]
        written.append(build_home(records, lang_projects, lang, out_root))
        written.append(build_projects(records, lang_projects, lang, out_root))
        written.append(build_compare(records, lang, out_root))
        for r in records:
            written.append(build_detail(r, lang, out_root))
        if packs:
            written.append(build_packs_index(packs, lang, out_root))
            for p in packs:
                written.append(build_pack(p, records, lang, out_root))
    return written
