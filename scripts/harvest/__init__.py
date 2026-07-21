"""Harvesters: enumeran fuentes conocidas-buenas en vez de muestrear por palabras clave."""
from . import crossref_journals, dandi, europepmc, openalex_citedby, openalex_keyword, openneuro, zenodo

REGISTRY = {
    "crossref": crossref_journals.CrossrefJournals,
    "openneuro": openneuro.OpenNeuro,
    "dandi": dandi.Dandi,
    "citedby": openalex_citedby.OpenAlexCitedBy,
    "openalex": openalex_keyword.OpenAlexKeyword,
    "zenodo": zenodo.Zenodo,
    "europepmc": europepmc.EuropePMC,
}

# Fuentes enumerables (recall completo) frente a las de muestreo (cola larga).
ENUMERATING = ["crossref", "openneuro", "dandi", "citedby"]
SAMPLING = ["openalex", "zenodo", "europepmc"]
