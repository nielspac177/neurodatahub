#!/usr/bin/env python3
"""
schema.py — Fuente única de verdad del esquema de NeuroDataHub.

Todo lo que valida, normaliza o cuenta registros vive aquí. Lo importan
build.py, triage.py e ingest_records.py, de modo que el validador de Python
y el JSON Schema que consume el pipeline LLM no puedan divergir.

Dos niveles de diagnóstico:
    ERRORES   — rompen el build (campo obligatorio ausente, enum inválido, id duplicado)
    AVISOS    — se imprimen y el build continúa (calidad, cobertura, frescura)

Con ~150 registros, un solo campo de baja confianza no puede bloquear el deploy
de GitHub Pages; por eso la separación.
"""
import re
from collections import Counter
from datetime import date

# --------------------------------------------------------------------- #
# Enumeraciones
# --------------------------------------------------------------------- #
# Orden canónico de presentación. Debe ser una LISTA, no un set: el HTML
# generado se commitea, y la iteración de un set varía entre procesos por la
# aleatorización del hash de cadenas, lo que produciría un diff distinto en
# cada corrida del build.
MODALITY_ORDER = [
    "clinical", "neuroimaging", "genetics",
    "electrophysiology", "bci", "multimodal", "aggregator",
]
VALID_MODALITIES = set(MODALITY_ORDER)
VALID_ACCESS = {"open", "registration", "credentialed", "dua", "application"}

# Orden de restrictividad: ante desacuerdo entre el redactor y el crítico de
# acceso, ingest_records.py toma SIEMPRE el valor de índice mayor.
ACCESS_RESTRICTIVENESS = ["open", "registration", "credentialed", "dua", "application"]

VALID_STATUS = {"draft", "published", "needs_human", "deprecated", "dead"}
VALID_ACCESS_CONFIDENCE = {"high", "medium", "low"}
VALID_COMPUTE = {"laptop", "gpu-single", "cluster"}
VALID_SPECIES = {"human", "animal", "mixed", "phantom", "simulated"}

# Las seis lentes de hueco de PLAN.md §6.
VALID_LENS = {
    "generalization", "multimodal", "causal",
    "equity", "neuromodulation", "foundation-models",
}

VALID_PROJECT_STATUS = {"open", "closed"}
VALID_NOVELTY = {"novel", "partial"}
VALID_FEASIBILITY = {"feasible", "feasible_with_caveat"}

DIFFICULTY_MIN, DIFFICULTY_MAX = 1, 5

DIFFICULTY_WORDS = {
    1: ("Starter", "Inicial"),
    2: ("Approachable", "Accesible"),
    3: ("Intermediate", "Intermedio"),
    4: ("Advanced", "Avanzado"),
    5: ("Research-grade", "Nivel investigación"),
}

# `diseases` NO es obligatorio: las cohortes normativas y de controles sanos
# están dentro del alcance (PLAN.md §2) y legítimamente no tienen enfermedad.
# Exigirlo bloqueaba datasets válidos de neurociencia cognitiva. Su ausencia
# se reporta como aviso, no como error.
REQUIRED = ["id", "name", "modality_primary", "access", "url"]

# Semanas de un semestre; el crítico de viabilidad rechaza proyectos cuyo
# access_latency_weeks + effort_weeks lo superen.
SEMESTER_WEEKS = 15

# Cada cuánto revalidar según el riesgo del tipo de acceso (días).
REVERIFY_INTERVAL_DAYS = {
    "open": 365,
    "registration": 270,
    "credentialed": 180,
    "dua": 180,
    "application": 180,
}


# --------------------------------------------------------------------- #
# Validación
# --------------------------------------------------------------------- #
def validate(records):
    """Devuelve (errores, avisos). Los errores rompen el build; los avisos no."""
    errors, warnings = [], []

    if not isinstance(records, list):
        return ["databases.yml debe ser una lista de registros."], []

    ids = set()
    project_ids = set()

    for i, r in enumerate(records):
        label = r.get("id", f"#{i}")

        for field in REQUIRED:
            if field not in r or r[field] in (None, "", []):
                errors.append(f"[{label}] falta campo obligatorio: {field}")

        if r.get("id") in ids:
            errors.append(f"[{label}] id duplicado")
        ids.add(r.get("id"))

        _enum(errors, label, r, "modality_primary", VALID_MODALITIES)
        _enum(errors, label, r, "access", VALID_ACCESS)
        _enum(errors, label, r, "status", VALID_STATUS, optional=True)
        _enum(errors, label, r, "access_confidence", VALID_ACCESS_CONFIDENCE, optional=True)
        _enum(errors, label, r, "species", VALID_SPECIES, optional=True)

        for field in ("last_verified", "access_verified_at", "link_checked_at"):
            _iso_date(errors, label, r.get(field), field)

        # --- avisos de calidad ---
        if not (r.get("short_desc_en") or r.get("short_desc_es")):
            warnings.append(f"[{label}] sin descripción en ningún idioma")
        if not r.get("diseases"):
            warnings.append(f"[{label}] sin etiquetas de enfermedad — "
                            f"no aparecerá en los filtros por enfermedad")
        if not r.get("descriptor_doi") and not r.get("doi"):
            warnings.append(f"[{label}] sin DOI — el mapeo de literatura por cited_by no funcionará")
        if r.get("access") in ("credentialed", "dua", "application") and not r.get("access_notes"):
            warnings.append(f"[{label}] acceso controlado sin access_notes")
        if r.get("access") == "open" and r.get("access_confidence") == "low":
            warnings.append(f"[{label}] publicado como 'open' con confianza baja — revisar")

        _validate_access_steps(errors, warnings, label, r)
        _validate_projects(errors, warnings, label, r, ids_seen=project_ids)

    # Referencias cruzadas entre datasets (se comprueban al final, cuando ids está completo).
    for r in records:
        label = r.get("id", "?")
        for p in r.get("projects") or []:
            for ref in p.get("extra_datasets") or []:
                if ref not in ids:
                    errors.append(
                        f"[{label}/{p.get('id','?')}] extra_datasets apunta a un id inexistente: {ref}"
                    )
        for ref in r.get("mirrors") or []:
            if ref not in ids:
                warnings.append(f"[{label}] mirrors apunta a un id inexistente: {ref}")

    return errors, warnings


VALID_PACK_LEVEL = {"undergraduate", "graduate", "bootcamp"}


def validate_packs(packs, records):
    """Valida los paquetes contra el catálogo.

    Cada id de `datasets:` y `projects:` debe resolver. Sin esta comprobación
    un paquete se pudre en silencio cuando el catálogo cambia, y un docente
    reparte un temario con enlaces muertos.
    """
    errors, warnings = [], []
    if not packs:
        return errors, warnings

    ds_ids = {r["id"] for r in records}
    proj_ids = {p["id"] for r in records for p in projects_of(r) if p.get("id")}
    seen = set()

    for i, p in enumerate(packs):
        label = p.get("id", f"#{i}")
        if not p.get("id"):
            errors.append(f"[pack {label}] sin id")
        elif p["id"] in seen:
            errors.append(f"[pack {label}] id duplicado")
        seen.add(p.get("id"))

        if not (p.get("title_en") or p.get("title_es")):
            errors.append(f"[pack {label}] sin título en ningún idioma")
        if p.get("level") and p["level"] not in VALID_PACK_LEVEL:
            errors.append(f"[pack {label}] level inválido: {p['level']}")

        for m in p.get("modules") or []:
            for d in m.get("datasets") or []:
                if d not in ds_ids:
                    errors.append(f"[pack {label}] semana {m.get('week')}: "
                                  f"dataset inexistente: {d}")
            for q in m.get("projects") or []:
                if q not in proj_ids:
                    errors.append(f"[pack {label}] semana {m.get('week')}: "
                                  f"proyecto inexistente: {q}")
        if not p.get("modules"):
            warnings.append(f"[pack {label}] sin módulos — no hay nada que asignar")
    return errors, warnings


def _enum(errors, label, record, field, allowed, optional=False):
    v = record.get(field)
    if v is None or v == "":
        if not optional and field in REQUIRED:
            pass  # ya reportado como campo obligatorio ausente
        return
    if v not in allowed:
        errors.append(f"[{label}] {field} inválido: {v!r} (permitidos: {sorted(allowed)})")


def _iso_date(errors, label, value, field):
    if not value:
        return
    try:
        date.fromisoformat(str(value))
    except ValueError:
        errors.append(f"[{label}] {field} no es una fecha ISO (YYYY-MM-DD): {value!r}")


def _validate_access_steps(errors, warnings, label, record):
    steps = record.get("access_steps")
    if not steps:
        if record.get("access") in ("credentialed", "dua", "application"):
            warnings.append(f"[{label}] acceso controlado sin access_steps — el estudiante no sabrá por dónde empezar")
        return
    if not isinstance(steps, list):
        errors.append(f"[{label}] access_steps debe ser una lista")
        return
    for j, s in enumerate(steps):
        if not isinstance(s, dict):
            errors.append(f"[{label}] access_steps[{j}] debe ser un mapa")
        elif not (s.get("step_en") or s.get("step_es")):
            errors.append(f"[{label}] access_steps[{j}] sin texto en ningún idioma")


def _validate_projects(errors, warnings, label, record, ids_seen):
    projects = record.get("projects")
    if not projects:
        return
    if not isinstance(projects, list):
        errors.append(f"[{label}] projects debe ser una lista")
        return

    for p in projects:
        if not isinstance(p, dict):
            errors.append(f"[{label}] cada proyecto debe ser un mapa")
            continue

        pid = p.get("id")
        if not pid:
            errors.append(f"[{label}] proyecto sin id")
        elif pid in ids_seen:
            errors.append(f"[{label}] id de proyecto duplicado (deben ser únicos globalmente): {pid}")
        else:
            ids_seen.add(pid)

        if not (p.get("question_en") or p.get("question_es")):
            errors.append(f"[{label}/{pid}] proyecto sin pregunta en ningún idioma")

        bad = check_spanish_accents(p.get("question_es"))
        if bad:
            warnings.append(f"[{label}/{pid}] español posiblemente sin tildes: "
                            f"{', '.join(bad[:5])}")

        _enum(errors, f"{label}/{pid}", p, "lens", VALID_LENS, optional=True)
        _enum(errors, f"{label}/{pid}", p, "compute", VALID_COMPUTE, optional=True)
        _enum(errors, f"{label}/{pid}", p, "status", VALID_PROJECT_STATUS, optional=True)
        _enum(errors, f"{label}/{pid}", p, "novelty", VALID_NOVELTY, optional=True)
        _enum(errors, f"{label}/{pid}", p, "feasibility", VALID_FEASIBILITY, optional=True)

        for field in ("difficulty", "feasibility_score"):
            _rating(errors, f"{label}/{pid}", p.get(field), field)

        # Regla del semestre: si ambos plazos están declarados, deben caber.
        eff, lat = p.get("effort_weeks"), p.get("access_latency_weeks")
        if isinstance(eff, int) and isinstance(lat, int) and eff + lat > SEMESTER_WEEKS:
            warnings.append(
                f"[{label}/{pid}] {lat}+{eff}={lat + eff} semanas supera un semestre ({SEMESTER_WEEKS})"
            )

        # 'partial' sin la justificación del delta es una idea sin valor para el estudiante.
        if p.get("novelty") == "partial" and not (p.get("still_open_because") or "").strip():
            errors.append(f"[{label}/{pid}] novelty 'partial' requiere still_open_because no vacío")

        if p.get("status") == "closed" and not p.get("closed_by_doi"):
            warnings.append(f"[{label}/{pid}] proyecto cerrado sin closed_by_doi")


# Palabras españolas frecuentes que, sin tilde, son otra palabra o un error
# claro. El pipeline LLM devolvió "anos" por "años" en una corrida; sin este
# aviso eso se publica y nadie lo ve.
_MISSING_ACCENT = re.compile(
    r"\b(anos|ano|division|cuanto|cuantos|varian|geometria|discriminacion|"
    r"tamanos|condicion|manipulacion|dinamica|numero|analisis|metodo|"
    r"tecnica|practica|clinico|linea|dia|mas|segun|tambien)\b")


def check_spanish_accents(text):
    """Devuelve las palabras sospechosas de haber perdido la tilde."""
    return sorted(set(_MISSING_ACCENT.findall(text or "")))


def _rating(errors, label, value, field):
    if value is None:
        return
    if not isinstance(value, int) or not (DIFFICULTY_MIN <= value <= DIFFICULTY_MAX):
        errors.append(
            f"[{label}] {field} debe ser un entero {DIFFICULTY_MIN}-{DIFFICULTY_MAX}: {value!r}"
        )


# --------------------------------------------------------------------- #
# Normalización / migración
# --------------------------------------------------------------------- #
# El ideador devuelve a veces frases enteras como "habilidad" ("explicit
# reporting of demographic limits (single-site Japanese volunteer sample…)").
# Eso no es filtrable: produce un chip por proyecto y ninguno se reutiliza.
# Se mapea a un vocabulario corto y lo que no encaja se descarta.
SKILL_MAP = {
    "python": ["python", "pandas", "numpy", "scipy"],
    "r": ["r statistics", " r ", "rstudio", "data.table"],
    "machine-learning": ["scikit-learn", "sklearn", "machine learning", "classifier",
                         "random forest", "regression model", "xgboost"],
    "deep-learning": ["pytorch", "tensorflow", "keras", "neural network",
                      "self-supervised", "transformer", "cnn"],
    "statistics": ["statistic", "mixed model", "power analysis", "effect size",
                   "bayesian", "psychometric", "survival analysis", "multiple comparison"],
    "causal-inference": ["causal", "propensity", "instrumental variable",
                         "mediation", "confound"],
    "neuroimaging": ["fmri", "mri", "nibabel", "bids", "fmriprep", "freesurfer",
                     "voxel", "rdm", "representational similarity", "mriqc", "roi"],
    "signal-processing": ["eeg", "meg", "ieeg", "mne", "spectral", "filter",
                          "time-frequency", "edf", "polysomnograph", "psg", "yasa"],
    "genomics": ["gwas", "polygenic", "variant", "genotype", "plink", "snp"],
    "clinical-data": ["ehr", "icd", "sql", "chartevents", "clinical timeseries",
                      "electronic health record", "phenotyp"],
    "validation": ["cross-validation", "external validation", "leave-subject-out",
                   "leave-one-out", "generalization", "tripod", "calibration",
                   "held-out", "reproducib"],
}


def normalize_skills(skills):
    """Frases libres -> etiquetas cortas y reutilizables."""
    out = []
    for raw in skills or []:
        low = f" {str(raw).lower()} "
        for tag, needles in SKILL_MAP.items():
            if any(n in low for n in needles) and tag not in out:
                out.append(tag)
    return out


def projects_of(record):
    """Proyectos de un registro, migrando `open_questions` heredados.

    `open_questions` era una lista de cadenas libres. Se convierte en proyectos
    marcados `unverified`, para que el sitio los etiquete como idea sin
    verificar y el bucle de re-auditoría los programe para mejora. Así los 16
    registros existentes siguen funcionando sin reescribirlos.
    """
    if record.get("projects"):
        out = []
        for p in record["projects"]:
            q = dict(p)
            q.setdefault("status", "open")
            q.setdefault("unverified", False)
            out.append(q)
        return out

    out = []
    for i, q in enumerate(record.get("open_questions") or [], 1):
        if not isinstance(q, str):
            continue
        out.append({
            "id": f"{record['id']}-q{i}",
            "question_en": q,
            "question_es": q,
            "difficulty": None,
            "feasibility_score": None,
            "lens": None,
            "skills": [],
            "extra_datasets": [],
            "effort_weeks": None,
            "access_latency_weeks": None,
            "compute": None,
            "prior_work": [],
            "still_open_because": None,
            "novelty": None,
            "status": "open",
            "confidence": 0.2,
            "unverified": True,       # el sitio lo muestra como "idea sin verificar"
            "legacy_open_question": True,
        })
    return out


def flatten_projects(records):
    """Índice plano de proyectos con datos del dataset desnormalizados.

    Es lo que consume projects.html: un estudiante filtra por dificultad o
    habilidad y necesita ver el acceso y la modalidad sin una segunda búsqueda.
    """
    by_id = {r["id"]: r for r in records}
    out = []
    for r in records:
        for p in projects_of(r):
            item = dict(p)
            item["skills"] = normalize_skills(p.get("skills"))
            item["dataset_id"] = r["id"]
            item["dataset_name"] = r["name"]
            item["dataset_url"] = r.get("url")
            item["access"] = r.get("access")
            item["modality_primary"] = r.get("modality_primary")
            item["disease_category"] = r.get("disease_category") or []
            item["diseases"] = r.get("diseases") or []
            # Un proyecto multi-dataset es tan accesible como su eslabón más restrictivo.
            extra = [by_id[x] for x in (p.get("extra_datasets") or []) if x in by_id]
            item["all_datasets"] = [r["id"]] + [x["id"] for x in extra]
            item["access_hardest"] = _hardest_access([r] + extra)
            out.append(item)
    out.sort(key=lambda p: (p.get("difficulty") or 99, p["dataset_name"].lower()))
    return out


def _hardest_access(records):
    worst = 0
    for r in records:
        a = r.get("access")
        if a in ACCESS_RESTRICTIVENESS:
            worst = max(worst, ACCESS_RESTRICTIVENESS.index(a))
    return ACCESS_RESTRICTIVENESS[worst]


# --------------------------------------------------------------------- #
# Facetas
# --------------------------------------------------------------------- #
def facets(records):
    """Facetas de datasets. Forma idéntica a la original de build.py."""
    mod, dis, acc, cat = Counter(), Counter(), Counter(), Counter()
    for r in records:
        mod[r.get("modality_primary", "?")] += 1
        acc[r.get("access", "?")] += 1
        for d in r.get("diseases", []):
            dis[d] += 1
        for c in r.get("disease_category", []):
            cat[c] += 1
    return {
        "modality": dict(mod.most_common()),
        "disease": dict(dis.most_common()),
        "access": dict(acc.most_common()),
        "category": dict(cat.most_common()),
    }


def project_facets(projects):
    diff, skill, lens, mod, ds, comp, acc = (Counter() for _ in range(7))
    for p in projects:
        diff[str(p.get("difficulty") or "unrated")] += 1
        lens[p.get("lens") or "unclassified"] += 1
        mod[p.get("modality_primary", "?")] += 1
        ds[p.get("dataset_id", "?")] += 1
        comp[p.get("compute") or "unspecified"] += 1
        # Se facetea por el acceso MÁS restrictivo de todos los datasets que
        # el proyecto necesita: un proyecto multi-dataset sólo es tan
        # alcanzable como su eslabón más difícil.
        acc[p.get("access_hardest") or "?"] += 1
        for s in p.get("skills") or []:
            skill[s] += 1
    return {
        "difficulty": dict(sorted(diff.items())),
        "skills": dict(skill.most_common()),
        "lens": dict(lens.most_common()),
        "modality": dict(mod.most_common()),
        "access": dict(acc.most_common()),
        "dataset": dict(ds.most_common()),
        "compute": dict(comp.most_common()),
    }


def coverage_gaps(records):
    """Celdas enfermedad x modalidad sin ningún dataset.

    Retroalimenta la prioridad de los harvesters: muestra dónde el catálogo
    está delgado en vez de dejar que crezca sólo donde ya es denso.
    """
    seen = {(d, r.get("modality_primary")) for r in records for d in r.get("diseases", [])}
    diseases = sorted({d for r in records for d in r.get("diseases", [])})
    gaps = [
        {"disease": d, "modality": m}
        for d in diseases
        for m in MODALITY_ORDER
        if (d, m) not in seen and m != "aggregator"
    ]
    return gaps
