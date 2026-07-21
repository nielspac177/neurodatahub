# NeuroDataHub

Catálogo curado y **verificado** de las bases de datos **clínicas, genéticas, de neuroimagen, electrofisiología y BCI** más importantes para investigación en enfermedades **neuroquirúrgicas, neurológicas y psiquiátricas** — pensado para que estudiantes de bioingeniería y medicina encuentren datos que puedan conseguir de verdad y preguntas en las que puedan trabajar de verdad.

Sitio estático (GitHub Pages) · contribuidor único · descubrimiento semanal automatizado.

🔗 **Sitio**: `https://nielspac177.github.io/neurodatahub/`

---

## Las dos mitades

El sistema se parte en dos, y se comunican **sólo a través de archivos commiteados**.

| Mitad | Dónde corre | Qué hace |
|---|---|---|
| **Python** | GitHub Actions, semanal, sin claves de API | enumera fuentes, deduplica, tría, audita enlaces, valida, genera el HTML |
| **LLM** | Tu portátil, bajo demanda | enriquece, mapea literatura, propone proyectos, verificación adversarial |

**Regla dura: el LLM nunca escribe en `data/databases.yml`.** Escribe borradores en `drafts/*.record.json`, y `scripts/ingest_records.py` los re-verifica en Python y decide qué se publica. Así la validación vive en un solo sitio y cada aportación del modelo es revisable como un diff.

---

## El ciclo semanal

### Domingo 06:00 UTC — automático, sin intervención

```
harvest_run.py      enumera revistas de datos por ISSN + repositorios por API
   ↓                deduplica contra state/seen.json (que también recuerda los rechazos)
   ↓                tría con el léxico determinista → queue/{candidates,borderline,rejected}
audit_links.py      ¿siguen vivos los enlaces? ¿cambió el texto de acceso?
reaudit_queue.py    prioriza qué revalidar (delta de citas + antigüedad + riesgo)
build.py --check    valida el catálogo
   ↓
Pull Request        con reports/latest-scan.md como cuerpo
```

### Tú, cualquier tarde (~30–60 min)

```bash
git pull                                   # o mergea el PR del bot
python3 scripts/fetch_evidence.py --limit 20   # congela las fuentes (sha256)
#   → panel adversarial (workflows/enrich.mjs)
python3 scripts/ingest_records.py          # re-verifica TODO en Python y mezcla
#   → revisa drafts/needs_human/
python3 scripts/build.py && git push
```

---

## Descubrimiento: enumerar, no adivinar

La estrategia principal **no** es buscar por palabras clave, es **enumerar fuentes conocidas-buenas y luego triar**:

| Fuente | Cómo | Volumen |
|---|---|---|
| Revistas de datos por ISSN | Crossref `from-index-date` | *Data in Brief* publica ~774 items/año |
| OpenNeuro | GraphQL público | ~1.827 datasets |
| DANDI Archive | REST público | ~876 dandisets |
| Grafo de citas | OpenAlex `cites:` sobre los DOI ya catalogados | se realimenta solo |
| Cola larga | OpenAlex / Zenodo / Europe PMC por palabras clave | rotación diaria |

Una revista de descriptores de datos publica, por definición, un dataset por artículo. Enumerarla da **recall completo**; buscar por palabras clave sólo encuentra lo que uno pensó preguntar.

Se usa `from-index-date` y no `from-pub-date` porque Crossref indexa depósitos con fecha de publicación retroactiva, y filtrar por fecha de publicación se los salta para siempre.

### Deduplicación en cuatro niveles

`doi` · `url` · `accession` (`openneuro:ds004215`) son **autoritativas**; `title` sólo levanta una bandera y nunca descarta sola. `state/seen.json` mapea *todas* las claves de un item a la misma entrada y **recuerda también los rechazos** — sin eso, los 774 items anuales de *Data in Brief* se vuelven a triar cada domingo, para siempre.

### El triaje se calibra, no se adivina

```bash
python3 scripts/calibrate_triage.py
```

Puntúa los **registros ya publicados** como si acabaran de descubrirse. Ninguno puede caer en `rejected`: si un conocido-bueno se pierde, el léxico está mal, no el registro. Corre en CI **antes** de que el escaneo escriba nada.

Los umbrales salen de distribuciones medidas, no de intuición: conocidos-buenos 9–29, items neuro reales 23–27, ruido no-neuro 0–10.

---

## El panel adversarial

Cada candidato pasa por un pipeline donde **los críticos sólo pueden vetar, nunca aprobar**. Eso evita el modo de fallo en que un coro de críticos complacientes sella una invención.

**Etapa 1 — evidencia congelada** (determinista, sin modelo). Se descargan y se guardan con `sha256` la página de aterrizaje, los metadatos de Crossref y el registro del repositorio. Esto convierte la comprobación de fundamentación en una **búsqueda de subcadena**, no en la opinión de un segundo modelo: una cita inventada se detecta con `str.find()`, gratis y con certeza.

**Etapa 2 — redactor.** Sólo ve la evidencia. Cada campo lleva una cita literal. *Si no está en la evidencia, el campo va a `null`* — nunca se infiere.

**Etapa 3–4 — literatura e ideación** (en paralelo). La literatura se mapea siguiendo `cites:` del DOI del descriptor en OpenAlex: los trabajos que citan un dataset son los que **realmente lo usaron**, señal mucho mejor que buscar su nombre.

**Etapa 5 — críticos, a ciegas entre sí:**

| Crítico | Qué refuta | Veto |
|---|---|---|
| C1 fundamentación | ¿la cita es literal y sostiene el valor? | `UNSUPPORTED` → **campo a null**; `CONTRADICTED` → registro bloqueado |
| C2 acceso | re-deriva los términos **sin ver** la respuesta del redactor | desacuerdo → se toma **el más restrictivo** + revisión humana |
| C3 novedad | ¿ya se publicó esta pregunta? | `PUBLISHED` → idea eliminada; `PARTIAL` sin delta explícito → eliminada |
| C4 viabilidad | ¿el dataset contiene de verdad las variables que pide? | `INFEASIBLE` → idea eliminada; dificultad → se toma la **pesimista** |

**Regla asimétrica de acceso:** un registro **nunca** se publica como `open` salvo que dos derivaciones independientes coincidan. Prometer acceso abierto de más le cuesta semanas a un estudiante; prometerlo de menos, un clic.

`ingest_records.py` vuelve a comprobar **todo** en Python sin fiarse del JSON. Lo que no pasa cae en `drafts/needs_human/`, que es toda tu cola de revisión.

---

## Mantenimiento: que el catálogo no envejezca mal

- **`audit_links.py`** — enlaces muertos (dos semanas seguidas → `needs_human`, nunca se borra en silencio) y **hash del texto de la página de acceso**. Ese hash es el disparador más valioso del sistema: atrapa un dataset que pasa silenciosamente de abierto a exigir un DUA.
- **`reaudit_queue.py`** — delta de citas (crecimiento >20% → revalidar novedad, cuesta cero tokens) + antigüedad + riesgo de acceso. Revalidación: abierto 365 d, registro 270 d, **acceso controlado 180 d**.

Las preguntas que C3 encuentra ya publicadas pasan a `status: closed` y **siguen visibles** con el paper que las cerró. Para un estudiante eso es una función, no un defecto: enseña que el campo se mueve y demuestra que el catálogo se mantiene.

---

## Desarrollo local

```bash
pip install -r requirements.txt
python3 scripts/build.py            # genera 36 páginas (EN + ES) + los JSON
python3 -m http.server 8000         # http://localhost:8000
```

El HTML generado **no se commitea** (`.gitignore`): `deploy-pages.yml` corre `build.py` y sube el árbol completo, así que el sitio siempre se regenera desde `data/databases.yml`.

### Comprobaciones

```bash
python3 scripts/build.py --check       # esquema del catálogo (errores vs avisos)
python3 scripts/check_contrast.py      # WCAG 2.2 AA sobre los tokens, ambos temas
python3 scripts/calibrate_triage.py    # control positivo del léxico
```

### Arquitectura del sitio

- **Sin cadena de build**: nada de npm, Tailwind CLI ni empaquetadores. Tokens CSS a mano + módulos ES nativos.
- **Pre-renderizado**: `build.py` emite cada tarjeta en el HTML; el JS sólo conmuta `hidden`. Funciona sin JS, pinta al instante e indexa.
- **El idioma es una ruta** (`/` y `/es/`), no un conmutador en tiempo de ejecución.
- **Estado en la URL**: `/?m=electrophysiology,bci&a=open` — un docente puede enlazar a sus estudiantes una vista ya filtrada.
- **WCAG 2.2 AA**: chips como checkboxes nativos en `fieldset/legend`, rejilla `ul/li` con un solo punto de tabulación por tarjeta, conteo en región viva con retardo, dificultad codificada con palabra + pips (nunca sólo color).

---

## Esquema

Campos obligatorios: `id`, `name`, `modality_primary`, `diseases`, `access`, `url`.

```yaml
- id: identificador-unico
  name: Nombre visible
  modality_primary: neuroimaging   # clinical | neuroimaging | genetics | electrophysiology | bci | multimodal | aggregator
  diseases: [parkinson, epilepsy]
  disease_category: [neurological]
  provider: Institución
  url: https://...
  doi: 10.xxxx/yyyy
  descriptor_doi: 10.1038/s41597-...   # dispara todo el trabajo de cited_by
  access: open                     # open | registration | credentialed | dua | application
  access_confidence: high          # high | medium | low
  access_notes: "Requisitos de acceso"
  access_steps:                    # ruta paso a paso, con tiempos realistas
    - {step_en: "Create a PhysioNet account", step_es: "Crea una cuenta", eta: "5 min"}
  starter_code:
    python: |
      import pandas as pd
  short_desc_es: "Descripción en español."
  short_desc_en: "Description in English."
  key_publications: [{title: "...", year: 2024, doi: "...", task: biomarker}]
  projects:                        # sustituye a open_questions (que sigue soportado)
    - id: proyecto-unico
      question_en: "..."
      question_es: "..."
      lens: generalization         # las seis lentes de PLAN.md §6
      difficulty: 3                # 1-5
      skills: [python, ml]
      effort_weeks: 8
      still_open_because: "..."    # obligatorio si novelty = partial
  last_verified: "2026-07-21"
```

`open_questions` (lista de cadenas) sigue funcionando: `build.py` lo convierte en proyectos marcados **"idea sin verificar"**, y el bucle de re-auditoría los programa para mejora. Sin día de corte.

---

## Nota legal

Este catálogo **enlaza a fuentes oficiales y no redistribuye datos**. Muchas bases son de acceso controlado (credencial, DUA o solicitud); el campo `access` lo indica y nunca se relaja sin doble verificación. Respeta siempre la licencia y el acuerdo de uso de cada fuente.

## Licencia

Código y metadatos del catálogo: MIT (ver `LICENSE`). Los datasets enlazados conservan sus propias licencias.
