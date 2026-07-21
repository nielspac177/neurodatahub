# NeuroDataHub — Plan de trabajo

**Repositorio de bases de datos clínicas, genéticas, de neuroimagen, electrofisiología y BCI para enfermedades neuroquirúrgicas, neurológicas y psiquiátricas.**

> Sitio estático en GitHub Pages · contribuidor único · actualización asistida por *deep-research*.

Versión del plan: v0.1 · Fecha: 2026-07-21

---

## 0. Supuestos de partida (ajustables)

| Decisión | Elección por defecto | Alternativa |
|---|---|---|
| Motor de actualización | Manual con Claude → migrar a GitHub Actions programado | Solo bajo demanda |
| Idioma | Bilingüe ES/EN (interfaz EN, descripciones ES+EN) | Solo EN o solo ES |
| Organización | Doble eje: **enfermedad × tipo de dato** | Un solo eje |
| Entregable de esta fase | Este plan | Plan + prueba de concepto |

Si cambias cualquiera, se reajusta el resto del plan.

---

## 1. Objetivo y alcance

Construir un **catálogo curado, versionado y buscable** de las bases de datos públicas (o de acceso controlado documentado) más relevantes para investigación en:

- **Neuroquirúrgico**: tumores cerebrales (glioma/GBM, meningioma), epilepsia quirúrgica, DBS (Parkinson, temblor esencial, distonía, TOC), TCE, ictus/aneurisma, columna, hidrocefalia, dolor y neuromodulación.
- **Neurológico**: Parkinson y trastornos del movimiento, Alzheimer y demencias, epilepsia, esclerosis múltiple, ictus, ELA, cefalea, trastornos del sueño.
- **Psiquiátrico**: depresión mayor, esquizofrenia, trastorno bipolar, autismo (TEA), TDAH, TOC, TEPT, adicciones.
- **BCI / interfaces cerebro-computadora** (transversal a las anteriores).

El catálogo no aloja datos: **indexa, describe y enlaza** cada fuente, documenta requisitos de acceso, mapea lo ya publicado y propone preguntas abiertas.

---

## 2. Taxonomía (doble eje de clasificación)

### Eje A — Tipo de dato / modalidad

1. **Clínico / EHR / UCI** (registros, escalas, desenlaces, claims)
2. **Neuroimagen** (MRI estructural/funcional, dMRI, PET, CT, imagen tumoral)
3. **Genética / ómica** (GWAS, WES/WGS, transcriptómica, imaging-genetics)
4. **Electrofisiología** (EEG, MEG, iEEG/ECoG, LFP, sueño, EMG)
5. **BCI** (motor imagery, P300, SSVEP, implantados)
6. **Multimodal / biobancos** (combinan varias de las anteriores)
7. **Agregadores / *data papers*** (revistas y repositorios que publican datasets)

### Eje B — Categoría de enfermedad

Neuroquirúrgica · Neurológica · Psiquiátrica · Transversal/BCI · Control/normativo (envejecimiento sano, desarrollo).

Cada base de datos recibe **una modalidad primaria** + etiquetas de enfermedad (puede tener varias). El sitio permite filtrar por ambos ejes simultáneamente.

---

## 3. Metodología de búsqueda (el "algoritmo")

### 3.1 Fuentes a rastrear sistemáticamente

- **Revistas de *data papers***: *Nature Scientific Data*, *Data in Brief* (Elsevier), *GigaScience/GigaDB*, *Frontiers in Neuroscience (data reports)*.
- **Repositorios de neurociencia**: OpenNeuro, PhysioNet, NeuroVault, iEEG.org, DABI (BRAIN Initiative), OpenfMRI (histórico), G-Node/GIN.
- **Portales de biobancos/consorcios**: UK Biobank, ADNI (LONI/IDA), PPMI, HCP, ABCD, All of Us, ENIGMA, PGC, dbGaP, GTEx, TCIA.
- **Repositorios generalistas**: Zenodo, figshare, Harvard Dataverse, OpenML, Kaggle (competencias clínicas/BCI).
- **Benchmarks/meta-colecciones**: MOABB (BCI), BNCI Horizon 2020, Medical Segmentation Decathlon, Grand Challenges (grand-challenge.org), BraTS/ISLES.
- **Literatura**: PubMed/PMC, Google Scholar, Semantic Scholar (para "qué se ha publicado con la base X").

### 3.2 Plantillas de consulta (por enfermedad × modalidad)

Estructura reutilizable para deep-research:

```
("<enfermedad>" OR "<sinónimos/CIE>")
AND ("<modalidad>": e.g. "EEG" OR "iEEG" OR "MRI" OR "GWAS" OR "EHR")
AND ("open dataset" OR "public database" OR "data descriptor"
     OR "benchmark" OR "data sharing" OR "cohort")
```

Ejemplos concretos:
- `"Parkinson" AND ("DBS" OR "local field potential") AND ("open dataset" OR "iEEG")`
- `"glioblastoma" AND ("MRI" OR "segmentation") AND ("public" OR "challenge" OR "TCIA")`
- `"major depressive disorder" AND ("EEG" OR "rs-fMRI") AND ("open dataset" OR "consortium")`
- `"motor imagery" AND "BCI" AND ("benchmark" OR "MOABB" OR "competition dataset")`

### 3.3 Criterios de inclusión / exclusión

**Incluir** si: (a) es citable (DOI/data descriptor o portal estable); (b) tiene condiciones de acceso claras; (c) es relevante a ≥1 enfermedad del alcance; (d) tamaño o singularidad justifican su valor.
**Excluir**: datasets desaparecidos/sin mantenimiento, sin licencia clara, duplicados triviales, o puramente animales sin traslación directa (se pueden marcar como "opcional").

### 3.4 Ciclo de actualización

1. Ejecutar plantillas por celda de la matriz (enfermedad × modalidad).
2. Deduplicar contra el catálogo actual (por DOI/URL canónica).
3. Rellenar el esquema (sección 4) para cada nuevo hallazgo.
4. Verificación adversarial de campos críticos (acceso, licencia, N, año) contra la fuente primaria.
5. *Commit* del `data/databases.yml` + PR de revisión.

---

## 4. Esquema de datos (backbone del sitio y de la automatización)

Un registro por base de datos, en `data/databases.yml` (o JSON). Campos:

```yaml
- id: mimic-iv
  name: MIMIC-IV
  version: "3.1"
  modality_primary: clinical_icu        # clinical | neuroimaging | genetics | electrophysiology | bci | multimodal | aggregator
  modality_secondary: [waveforms]
  diseases: [stroke, tbi, sepsis-neuro, delirium]
  disease_category: [neurosurgical, neurological]
  provider: PhysioNet / MIT-LCP
  url: https://physionet.org/content/mimiciv/3.1/
  doi: 10.13026/xxxx
  access: credentialed                  # open | registration | credentialed | dua | application
  access_notes: "CITI training + credentialing en PhysioNet"
  license: PhysioNet Credentialed Health Data License 1.5.0
  cost: free
  n_subjects: ~65000 ICU stays
  years: 2008-2019
  data_types: [EHR, vitals, labs, notes, ICD]
  region: US (Boston)
  imaging_linked: [MIMIC-CXR]
  short_desc_en: "..."
  short_desc_es: "..."
  key_publications:                     # "qué se ha publicado con esta base"
    - {title: "...", year: 2023, doi: "...", topic: mortality-prediction}
  open_questions:                        # "preguntas nuevas"
    - "..."
  last_verified: 2026-07-21
  tags: [benchmark, longitudinal, multi-center]
```

Este esquema alimenta directamente: (1) las tarjetas/tabla del sitio, (2) los filtros por eje A/B, (3) la sección "publicado con", (4) la sección "preguntas abiertas".

---

## 5. Mapa de "qué se ha publicado" (por base de datos)

Para cada entrada se documenta el **uso dominante en la literatura** y ejemplos representativos, de modo que se vea rápidamente el espacio ya explorado vs. el hueco. Enfoque:

- Búsqueda dirigida en PubMed/Semantic Scholar: `"<nombre dataset>" AND (prediction OR biomarker OR segmentation OR classification...)`.
- Clasificar publicaciones por **tarea** (predicción de desenlace, biomarcador, segmentación, subtipado, causalidad, generalización externa) y **método** (estadística clásica, ML clásico, deep learning, modelos de fundación).
- Registrar 3–6 publicaciones ancla por dataset (no exhaustivo) + una frase de "estado del arte".

### Ejemplos ilustrativos (semilla)

| Base | Modalidad | Uso publicado dominante |
|---|---|---|
| **MIMIC-IV / eICU** | Clínico-UCI | Predicción de mortalidad/sepsis/AKI, NLP de notas, *fairness*, benchmarks de deterioro clínico |
| **PPMI** | Multimodal (PD) | Progresión motora, biomarcadores DAT-SPECT/α-sinucleína, subtipos, genética LRRK2/GBA |
| **ADNI / OASIS** | Neuroimagen (AD) | Predicción de conversión MCI→AD, atrofia, PET amiloide/tau, modelos multimodales |
| **BraTS (TCIA)** | Neuroimagen tumoral | Segmentación de glioma, predicción de supervivencia/MGMT, *federated learning* |
| **UK Biobank** | Biobanco | Imaging-genetics, GWAS de rasgos cerebrales, riesgo poligénico, envejecimiento cerebral |
| **PGC** | Genética | GWAS de esquizofrenia/bipolar/MDD/TDAH, correlaciones genéticas cruzadas |
| **CHB-MIT / TUH EEG** | Electrofisiología | Detección/predicción de crisis, clasificación de EEG anormal, deep learning en EEG |
| **BCI Competition IV / MOABB** | BCI | *Motor imagery* decoding, transfer learning, benchmarking de arquitecturas EEG |

(La versión final tendrá esto por-registro y con citas.)

---

## 6. "Preguntas nuevas que aún se pueden hacer" (framework)

Para cada base, generamos preguntas abiertas usando 6 lentes de "hueco":

1. **Generalización externa / dominio**: ¿el modelo entrenado en dataset A funciona en B (otra población/escáner/hospital)?
2. **Multimodalidad no explotada**: combinar modalidades que la base ofrece pero rara vez se usan juntas (p. ej. EEG + genética + desenlace clínico).
3. **Causalidad / longitudinal**: pasar de predicción a inferencia causal o trayectorias temporales.
4. **Subgrupos infrarrepresentados / equidad**: sexo, etnia, comorbilidad, edad extrema.
5. **Nuevos *targets* de neuromodulación / biomarcadores**: LFP-DBS adaptativo, firmas electrofisiológicas transdiagnósticas.
6. **Modelos de fundación / auto-supervisión**: pre-entrenar en la base y evaluar *few-shot* en tareas clínicas.

### Ejemplos-semilla de preguntas abiertas

- **PPMI + iEEG/DBS**: ¿existen biomarcadores de LFP subtalámico que predigan respuesta a DBS estratificados por genotipo (GBA vs LRRK2)?
- **MIMIC-IV**: ¿se puede predecir delirium/deterioro neurológico agudo integrando notas + señales, y generaliza a eICU (validación externa multicéntrica)?
- **BraTS + genómica (TCGA)**: ¿firmas radiómicas que predigan metilación de MGMT o subtipo molecular sin biopsia, robustas entre centros?
- **PGC + ENIGMA (imaging-genetics)**: ¿los riesgos poligénicos transdiagnósticos (SCZ/BD/MDD) mapean a circuitos comunes explotables como dianas de neuromodulación?
- **TUH/CHB-MIT + BCI**: ¿modelos de fundación de EEG entrenados sin etiquetas transfieren a detección de crisis Y a decodificación motora (transdominio)?
- **Depresión (rs-fMRI + EEG abiertos)**: ¿biotipos reproducibles que predigan respuesta a TMS/DBS validados en cohortes independientes?

---

## 7. Arquitectura del sitio (GitHub Pages, contribuidor único)

**Principio**: separar **datos** (YAML/JSON versionado) de **presentación** (sitio estático), para que la actualización automática solo toque los datos.

Opción recomendada — **estático + JS de filtrado** (sin build pesado):

```
repo/  (github.io o /docs)
├── index.html            # tabla + filtros por enfermedad/modalidad/acceso
├── assets/               # CSS, JS (búsqueda/filtrado client-side, p.ej. list.js)
├── data/
│   └── databases.yml     # fuente de verdad
├── scripts/
│   ├── build.py          # YAML -> JSON/HTML tarjetas
│   └── research_update.py # plantillas de deep-research -> nuevos registros
├── .github/workflows/
│   └── update.yml        # Actions: corre research_update + build + PR
├── PLAN.md               # este documento
└── README.md
```

Alternativas si prefieres más "sitio": **Jekyll** (nativo en GitHub Pages, colecciones desde YAML) o **MkDocs Material** (buscador integrado, muy limpio para docs). Recomiendo empezar con **estático + JS** por control total y cero fricción de build; migrar a MkDocs si quieres navegación tipo wiki.

**Contribuidor único**: todo el trabajo se hace en tu cuenta; las actualizaciones automáticas se configuran para hacer *commit* como tú (o abrir PRs que tú apruebas), manteniéndote como único autor/mantenedor.

---

## 8. Automatización de la actualización (roadmap del "algoritmo")

**Fase manual (ahora)**: yo ejecuto las plantillas de deep-research por celdas de la matriz, verifico y te entrego el `databases.yml` poblado. Tú lo commiteas.

**Fase semi-automática**: script `research_update.py` que:
- lee la matriz de consultas,
- llama a APIs de búsqueda académica (p. ej. Semantic Scholar, Europe PMC, Crossref) — todas con API pública,
- propone candidatos + diff contra el catálogo,
- genera un borrador de PR que tú (o yo en Cowork) revisamos.

**Fase automática (GitHub Actions)**: workflow programado (mensual) que corre el script, ejecuta la fase de verificación, y abre un PR "🔄 Data refresh YYYY-MM" con los cambios. Nada se publica sin tu *merge* → mantiene calidad y autoría única.

> Nota realista: la verificación semántica fina (¿es relevante?, ¿acceso correcto?) rinde mejor con un LLM en el loop. Por eso el diseño usa Actions para *descubrir/diff* y a mí (o a ti) para *aprobar*. Además puedo dejarte una **tarea programada** en Cowork que me dispare el refresco y te avise.

---

## 9. Consideraciones de acceso, licencia y ética (crítico)

Muchas bases son de **acceso controlado** — el catálogo debe marcarlo claramente:

- **Credencial + entrenamiento** (CITI): MIMIC-IV, eICU, la mayoría de PhysioNet restringido.
- **Aplicación / DUA**: ADNI, PPMI (registro + acuerdo), dbGaP (controlado), UK Biobank (aplicación pagada + IRB), All of Us.
- **Abierto/registro simple**: OpenNeuro, muchos de Zenodo/figshare, TCIA (mixto), BCI Competition, MOABB.

El sitio incluirá un campo `access` con leyenda y **no redistribuirá datos**: solo enlaza a la fuente oficial y describe el procedimiento. Esto te protege legalmente y respeta las licencias.

---

## 10. Cronograma por fases

| Fase | Entregable | Esfuerzo |
|---|---|---|
| **0 — Plan** (esta) | Este documento | ✅ |
| **1 — Esqueleto** | Repo + `index.html` con filtros + esquema `databases.yml` + 10–15 bases semilla | Corto |
| **2 — Poblado v1** | Deep-research sistemático por matriz; ~60–100 bases con descripción bilingüe | Medio |
| **3 — "Publicado con"** | Mapa de literatura por base (3–6 refs ancla c/u) | Medio |
| **4 — Preguntas abiertas** | Banco de preguntas por base usando las 6 lentes | Corto-Medio |
| **5 — Automatización** | `research_update.py` + GitHub Actions + tarea programada Cowork | Medio |
| **6 — Pulido** | Diseño, buscador, DOIs, badge de "last verified", README/CONTRIBUTING | Corto |

---

## 11. Inventario semilla (punto de partida, no exhaustivo)

**Clínico/UCI**: MIMIC-IV, MIMIC-III, eICU-CRD, HiRID, AmsterdamUMCdb, MIMIC-CXR.
**Neuroimagen**: OpenNeuro, ADNI, OASIS, IXI, HCP, ABCD, PPMI (imagen), BraTS (TCIA), TCGA-GBM/LGG, ISLES, ATLAS (stroke), ABIDE (TEA), ADHD-200, NeuroVault, EPISURG.
**Genética/ómica**: UK Biobank, gnomAD, GWAS Catalog, PGC, ENIGMA, dbGaP, GTEx, PsychENCODE, SFARI/SSC, ClinVar/OMIM, 1000 Genomes, IGAP (AD).
**Electrofisiología**: TUH EEG Corpus, CHB-MIT, Sleep-EDF, DEAP, SEED, ERP CORE, HBN-EEG, iEEG.org, DABI, MNE sample.
**BCI**: BCI Competition II–IV, BNCI Horizon 2020, PhysioNet EEGMMIDB, OpenBMI/Lee2019, High-Gamma (Schirrmeister), MOABB (meta), Grasp-and-Lift.
**Agregadores/data papers**: Nature Scientific Data, Data in Brief, GigaDB, Zenodo, figshare, Harvard Dataverse, Grand-Challenge, TCIA.

---

## 12. Decisiones que necesito de ti para avanzar

1. ¿Nombre del proyecto/repo? (placeholder: **NeuroDataHub**).
2. ¿Confirmas idioma **bilingüe ES/EN**?
3. ¿Arranco con el **esqueleto del sitio + 10–15 bases** (Fase 1) o prefieres primero un **piloto de deep-research** sobre 2–3 enfermedades para validar formato?
4. ¿Prefieres estático+JS (recomendado), Jekyll o MkDocs?

---
*Este plan es un documento vivo; se versiona junto al repo.*
