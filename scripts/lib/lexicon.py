#!/usr/bin/env python3
"""
lexicon.py — Puntuación determinista de relevancia neuro (sin LLM).

Corre en GitHub Actions sin clave de API. Su trabajo NO es decidir si un
dataset entra al catálogo: es bajar de miles de items enumerados a decenas que
merezcan el gasto de tokens del pipeline de enriquecimiento.

Los umbrales se calibran contra los registros ya publicados: si una base que
sabemos buena puntúa por debajo del umbral, el léxico está mal, no el registro.
"""
import re
import unicodedata

# --- términos de enfermedad (peso alto: definen el alcance) ---
DISEASE_TERMS = {
    # neuroquirúrgico
    "glioma": 6, "glioblastoma": 6, "meningioma": 5, "brain tumor": 6, "brain tumour": 6,
    "epilepsy": 6, "seizure": 5, "deep brain stimulation": 6, "dbs": 3,
    "traumatic brain injury": 6, "tbi": 3, "subarachnoid": 6, "aneurysm": 6,
    "hydrocephalus": 5, "subdural": 5, "spine": 3, "spinal": 3, "neurosurg": 6,
    # neurológico
    "parkinson": 6, "alzheimer": 6, "dementia": 5, "multiple sclerosis": 6,
    "stroke": 6, "ischemic": 4, "amyotrophic": 5, "als": 2, "huntington": 5,
    "migraine": 4, "sleep": 3, "tremor": 5, "dystonia": 5, "ataxia": 4,
    "neurodegenerat": 5, "cognitive impairment": 5, "mci": 3,
    # psiquiátrico
    "schizophrenia": 6, "depression": 5, "depressive": 5, "bipolar": 5,
    "autism": 6, "adhd": 5, "obsessive": 5, "ptsd": 5, "psychiatric": 5,
    "addiction": 4, "substance use": 4, "anxiety": 4, "psychosis": 5,
    # transversal
    "brain": 4, "neural": 3, "neuro": 3, "cortex": 3, "cortical": 3,
    "hippocamp": 4, "thalam": 4, "cerebell": 4, "white matter": 4,
}

# --- términos de modalidad (peso medio: confirman que es dato utilizable) ---
MODALITY_TERMS = {
    "eeg": 6, "ieeg": 6, "ecog": 6, "meg": 5, "erp": 4, "lfp": 5,
    "mri": 5, "fmri": 6, "dwi": 4, "dti": 4, "pet": 4, "spect": 4, "ct scan": 4,
    "structural mri": 5, "resting state": 5, "connectome": 5, "neuroimaging": 6,
    "gwas": 5, "genome-wide": 5, "transcriptom": 4, "polygenic": 4,
    "exome": 4, "snp": 3, "biobank": 5,
    "brain-computer interface": 7, "brain computer interface": 7, "bci": 5,
    "motor imagery": 6, "p300": 5, "ssvep": 5, "neurofeedback": 4,
    "electronic health record": 5, "ehr": 4, "intensive care": 4, "icu": 3,
    "electrophysiolog": 5, "spike sorting": 4, "neuropixels": 5,
}

# --- señales de que es un RECURSO DE DATOS, no un estudio cualquiera ---
DATASET_TERMS = {
    "dataset": 6, "data descriptor": 8, "database": 5, "open data": 6,
    "data sharing": 4, "benchmark": 5, "cohort": 3, "repository": 4,
    "openly available": 5, "publicly available": 5, "data release": 6,
    "corpus": 5, "atlas": 3, "challenge": 3,
}

# --- penalizaciones ---
NEGATIVE_TERMS = {
    "retraction": -40, "erratum": -40, "corrigendum": -40,
    "editorial": -25, "systematic review": -20, "meta-analysis": -15,
    "study protocol": -20, "case report": -20, "conference abstract": -25,
}

# Sólo penaliza si NO aparece ningún término humano.
ANIMAL_TERMS = ["mouse", "mice", "murine", "rat ", "rats", "zebrafish",
                "drosophila", "macaque", "primate", "porcine", "rabbit", "c. elegans"]
HUMAN_TERMS = ["human", "patient", "participant", "subject", "clinical", "volunteer"]

# Órganos fuera de alcance: si dominan, el item no es neuro.
OFF_TOPIC = ["breast cancer", "lung cancer", "prostate", "hepatic", "renal",
             "cardiac", "myocardial", "diabetes", "dermatolog", "retina",
             "covid-19", "influenza", "agricultur", "climate"]

# Prior por revista. Data in Brief publica ~774 items/año con densidad neuro
# baja, así que aporta poco por sí misma; Scientific Data es mucho más densa.
VENUE_PRIOR = {
    "scientific data": 15,
    "gigascience": 12,
    "gigadb": 12,
    "data in brief": 5,
    "frontiers in neuroscience": 8,
    "neuroimage": 10,
    "journal of open source software": 3,
}

# Umbrales calibrados empíricamente (scripts/calibrate_triage.py), no elegidos
# a ojo. Distribuciones medidas sobre los 16 registros publicados y sobre 25
# items reales de Scientific Data / Data in Brief:
#
#   conocidos-buenos      9 – 29   (mediana 20)
#   items neuro reales   23 – 27
#   ruido no-neuro        0 – 10   (sedimentos marinos, clima, fútbol, 5G)
#
# CANDIDATE=18 separa lo neuro del ruido; BORDERLINE=8 garantiza que ningún
# conocido-bueno caiga en 'rejected' sin que un humano o el LLM lo vea.
THRESHOLD_CANDIDATE = 18
THRESHOLD_BORDERLINE = 8


def fold(text):
    t = unicodedata.normalize("NFD", str(text or ""))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


_RX_CACHE = {}


def _rx(term):
    """Regex con límites de palabra, cacheada.

    La coincidencia por subcadena es un error de precisión en ambos sentidos:
    'rats' aparecía dentro de 'BraTS' y penalizaba el dataset de tumores
    cerebrales como si fuera de animales; 'pet' aparecía dentro de
    'competition' y regalaba puntos de modalidad. Los límites de palabra
    eliminan ambos.

    Los términos que terminan en raíz (p. ej. 'neurodegenerat') sólo llevan
    límite por delante, para que casen con sus sufijos.
    """
    if term not in _RX_CACHE:
        prefix_only = term.endswith(("at", "ic", "og", "am", "ell", "hal"))
        tail = r"" if prefix_only else r"\b"
        _RX_CACHE[term] = re.compile(r"\b" + re.escape(term).replace(r"\ ", r"\s+") + tail)
    return _RX_CACHE[term]


def _hits(blob, table, cap):
    """Suma acotada. El tope evita que un término repetido domine el puntaje."""
    score, matched = 0, []
    for term, weight in table.items():
        if _rx(term).search(blob):
            score += weight
            matched.append(term)
    return min(score, cap), matched


def score(item):
    """Devuelve (puntaje, detalle). Determinista y sin red."""
    blob = fold(" ".join(str(item.get(k) or "") for k in
                         ("title", "abstract", "description", "keywords", "venue")))
    if not blob.strip():
        return 0, {"reason": "sin texto"}

    disease, d_hit = _hits(blob, DISEASE_TERMS, 30)
    modality, m_hit = _hits(blob, MODALITY_TERMS, 25)
    dataness, n_hit = _hits(blob, DATASET_TERMS, 20)

    total = disease + modality + dataness
    detail = {"disease": disease, "modality": modality, "dataness": dataness,
              "matched": (d_hit + m_hit + n_hit)[:12]}

    # El prior de revista es un PRIOR, no evidencia: sólo cuenta si ya hay
    # alguna señal neuro. Si no, Scientific Data regalaría +15 a sus datasets
    # de sedimentos marinos y de clima, que son la mayoría de su volumen.
    venue = fold(item.get("venue"))
    if disease or modality:
        for name, prior in VENUE_PRIOR.items():
            if name in venue:
                total += prior
                detail["venue_prior"] = prior
                break

    # Una fuente que sólo publica datasets ya es evidencia de "dataness".
    if item.get("source") in ("OpenNeuro", "DANDI", "PhysioNet"):
        total += 12
        detail["repo_bonus"] = 12

    # Todas las comprobaciones usan límites de palabra, igual que _hits.
    for term, penalty in NEGATIVE_TERMS.items():
        if _rx(term).search(blob):
            total += penalty
            detail.setdefault("penalties", []).append(term)

    if (any(_rx(a).search(blob) for a in ANIMAL_TERMS)
            and not any(_rx(h).search(blob) for h in HUMAN_TERMS)):
        total -= 25
        detail.setdefault("penalties", []).append("animal-only")

    off = [o for o in OFF_TOPIC if _rx(o).search(blob)]
    if off and disease < 12:
        total -= 20
        detail.setdefault("penalties", []).append(f"off-topic:{off[0]}")

    # Sin ninguna señal de enfermedad ni de modalidad neuro, nada lo salva.
    if disease == 0 and modality == 0:
        total = min(total, 10)
        detail["reason"] = "sin términos neuro"

    detail["total"] = max(0, total)
    return detail["total"], detail


def route(points):
    if points >= THRESHOLD_CANDIDATE:
        return "candidates"
    if points >= THRESHOLD_BORDERLINE:
        return "borderline"
    return "rejected"
