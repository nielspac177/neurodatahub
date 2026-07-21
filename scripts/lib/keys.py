#!/usr/bin/env python3
"""
keys.py — Claves de deduplicación en cuatro niveles.

Un mismo dataset llega por tres caminos distintos: el descriptor en Scientific
Data, el registro en OpenNeuro y una copia en Zenodo. Sin una clave que los
una, el catálogo acumula triplicados.

Autoridad de cada nivel:
    doi        autoritativa
    url        autoritativa
    accession  autoritativa (nativa del repositorio)
    title      SÓLO indicativa — levanta una bandera, nunca descarta sola
"""
import re
import unicodedata

STOPWORDS = {
    "a", "an", "the", "of", "for", "and", "or", "in", "on", "with", "from",
    "data", "dataset", "database", "de", "la", "el", "los", "las", "y", "en",
}


def normalize_url(u):
    """Minúsculas, sin esquema, sin www, sin barra final, sin query ni fragmento.

    Quitar el query es intencional: los portales añaden parámetros de
    seguimiento que harían pasar por nuevo un enlace ya conocido.
    """
    if not u:
        return ""
    u = str(u).strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0].split("?")[0]
    return u.rstrip("/")


def doi_key(doi):
    """DOI normalizado. Las versiones de Zenodo colapsan al concept DOI.

    Zenodo asigna un DOI por versión (….5281/zenodo.123456) más un
    "concept DOI" que apunta a todas. Sin colapsarlos, cada versión nueva
    parecería un dataset nuevo cada semana.
    """
    if not doi:
        return ""
    d = str(doi).strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = d.rstrip(".")
    return d


ACCESSION_PATTERNS = [
    (re.compile(r"openneuro\.org/datasets/(ds\d+)", re.I), "openneuro"),
    (re.compile(r"\b(ds\d{6})\b"), "openneuro"),
    (re.compile(r"dandiarchive\.org/dandiset/(\d+)", re.I), "dandi"),
    (re.compile(r"\bDANDI:?\s*(\d{6})\b", re.I), "dandi"),
    (re.compile(r"physionet\.org/content/([a-z0-9\-]+)", re.I), "physionet"),
    (re.compile(r"openneuro|neurovault\.org/collections/(\d+)", re.I), "neurovault"),
    (re.compile(r"zenodo\.org/records?/(\d+)", re.I), "zenodo"),
    (re.compile(r"osf\.io/([a-z0-9]{5})\b", re.I), "osf"),
    (re.compile(r"ebrains\.eu/.*?/([0-9a-f\-]{36})", re.I), "ebrains"),
]


def accession_key(*texts):
    """Identificador nativo del repositorio, p. ej. 'openneuro:ds004215'.

    Es la clave más fuerte: sobrevive a que el portal cambie de dominio o de
    esquema de URL, cosa que pasa más de lo que uno querría.
    """
    blob = " ".join(str(t) for t in texts if t)
    for pattern, repo in ACCESSION_PATTERNS:
        m = pattern.search(blob)
        if m and m.lastindex:
            return f"{repo}:{m.group(1).lower()}"
    return ""


def title_fingerprint(title, length=80):
    """Huella indicativa: minúsculas, sin acentos, sin stopwords, sólo alfanum."""
    if not title:
        return ""
    t = unicodedata.normalize("NFD", str(title))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    words = [w for w in re.findall(r"[a-z0-9]+", t) if w not in STOPWORDS]
    return " ".join(words)[:length]


def all_keys(item):
    """Todas las claves de un item. seen.json mapea CADA una al mismo registro."""
    url = item.get("url") or ""
    doi = item.get("doi") or ""
    keys = {}
    if doi:
        keys["doi"] = doi_key(doi)
    if url:
        keys["url"] = normalize_url(url)
    acc = accession_key(url, doi, item.get("title"), item.get("raw_id"))
    if acc:
        keys["accession"] = acc
    fp = title_fingerprint(item.get("title"))
    if fp:
        keys["title"] = fp
    return keys


def authoritative(keys):
    """Sólo las claves con las que es seguro descartar automáticamente."""
    return [v for k, v in keys.items() if k != "title" and v]
