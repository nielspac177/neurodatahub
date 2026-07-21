# RUNBOOK — actualización semanal de NeuroDataHub

Este archivo está escrito para dos lectores: tú, y un agente de Claude Code
que abras sin contexto previo. Si eres el agente: lee esto entero antes de
ejecutar nada, y respeta las reglas de la sección 5 — no son sugerencias.

---

## 0. Arrancar un agente nuevo

```bash
cd ~/neurodatahub
claude
```

Y pega esto:

> Lee RUNBOOK.md y ejecuta la actualización semanal completa de NeuroDataHub.
> Párate y enséñame lo que haya en drafts/needs_human/ antes de publicar nada.
> No hagas push: déjalo commiteado en una rama y dime el comando para mergear.

Eso es todo. El resto de este documento es lo que el agente necesita saber.

---

## 1. Qué es esto

Catálogo de datasets abiertos de neurociencia para estudiantes. Sitio estático
en GitHub Pages. **Contribuidor único**: nada se publica sin revisión humana.

El sistema tiene dos mitades que se comunican **sólo por archivos commiteados**:

| Mitad | Dónde | Qué hace |
|---|---|---|
| Python | GitHub Actions, semanal, sin claves | enumera, deduplica, tría, audita enlaces, valida, genera HTML |
| LLM | Aquí, bajo demanda | enriquece, mapea literatura, propone proyectos, verificación adversarial |

**Regla dura: el LLM nunca escribe en `data/databases.yml`.** Escribe borradores
en `drafts/*.record.json`; `scripts/ingest_records.py` los re-verifica en Python
y decide qué se publica.

---

## 2. El ciclo completo, en orden

```bash
# 0) partir de limpio y en rama
git checkout main && git pull
git checkout -b weekly/$(date +%Y-%m-%d)

# 1) DESCUBRIMIENTO — enumera revistas de datos y repositorios
python3 scripts/harvest_run.py
#    -> queue/{candidates,borderline,rejected}.jsonl, reports/latest-scan.md

# 2) EVIDENCIA — congela las fuentes (sha256) antes de que nada genere texto
python3 scripts/fetch_evidence.py --limit 20
#    -> drafts/<id>.evidence.json

# 3) ENRIQUECIMIENTO — panel adversarial (ver sección 3)

# 4) PUBLICACIÓN — re-verifica TODO en Python y mezcla
python3 scripts/ingest_records.py
#    -> data/databases.yml  +  drafts/needs_human/  <- REVISAR ESTO

# 5) MANTENIMIENTO
python3 scripts/audit_links.py          # enlaces muertos, cambios de acceso
python3 scripts/reaudit_queue.py --top 20
python3 scripts/prune_evidence.py       # recorta paquetes ya consumidos

# 6) COMPROBACIONES — las cuatro deben pasar
python3 scripts/build.py --check        # esquema del catálogo
python3 scripts/check_contrast.py       # WCAG 2.2 AA, ambos temas
python3 scripts/calibrate_triage.py     # control positivo del léxico
python3 scripts/build.py                # genera el sitio

# 7) VER EL RESULTADO
python3 -m http.server 8000             # http://localhost:8000

# 8) COMMIT (no push)
git add -A && git commit
```

---

## 3. El paso de enriquecimiento

Usa la herramienta `Workflow` de Claude Code:

```
Workflow({ scriptPath: "workflows/enrich.mjs", args: { limit: 8 } })
```

Tarda ~15 min y lanza ~100 subagentes. Lo que hace, por etapas:

1. **Alcance** — puerta barata; descarta lo que no es neuro antes de gastar tokens.
2. **Redactor** — sólo ve la evidencia congelada. Cada campo lleva una cita
   literal. *Si no está en la evidencia, el campo va a `null`.*
3. **Literatura + ideación** (en paralelo) — la literatura se mapea siguiendo
   `cites:` del DOI del descriptor: los trabajos que citan un dataset son los
   que realmente lo usaron.
4. **Críticos, a ciegas entre sí** — sólo pueden **vetar**, nunca aprobar:

   | Crítico | Veta cuando |
   |---|---|
   | C1 fundamentación | la cita no es literal o no sostiene el valor → campo a `null` |
   | C2 acceso | re-deriva los términos **sin ver** el borrador; si discrepan, gana el más restrictivo |
   | C3 novedad | la pregunta ya se publicó → idea eliminada |
   | C4 viabilidad | el dataset no contiene las variables que pide → idea eliminada |

Si sale mal a mitad, no repitas desde cero: usa `resumeFromRunId` con el id que
devolvió la corrida. Los agentes sin cambios se sirven de caché.

---

## 4. Qué revisar en `drafts/needs_human/`

Cada archivo trae `_blocks` con el motivo. Los habituales:

| Motivo | Qué significa | Qué hacer |
|---|---|---|
| `'open' con una sola derivación` | sólo una fuente dice que es abierto | abrir la URL y confirmar a mano |
| `desacuerdo: redactor=X, crítico=Y` | los dos derivaron accesos distintos | comprobar la licencia real |
| `N citas no verificables` | el modelo citó frases que no existen | descartar el registro |
| `campo contradicho por la evidencia` | la evidencia dice lo contrario | descartar |
| `falta campo obligatorio` | falta `id`, `name`, `modality_primary`, `access` o `url` | completar a mano o descartar |

Para publicar uno a mano: corrige el JSON, muévelo a `drafts/` y vuelve a
correr `ingest_records.py`.

---

## 5. Reglas que el agente NO debe romper

1. **No editar `data/databases.yml` a mano** para meter registros nuevos. Pasa
   siempre por `ingest_records.py`, que es donde viven las reglas de veto.
2. **No relajar el acceso.** Un registro nunca se publica como `open` salvo que
   dos derivaciones independientes coincidan. Prometer acceso abierto de más le
   cuesta semanas a un estudiante.
3. **No inventar campos.** Si la evidencia no lo dice, el campo va vacío. Un
   campo vacío es correcto y útil; uno adivinado es un defecto.
4. **No hacer push sin permiso.** `git push` a `main` dispara el deploy.
5. **No commitear el HTML generado.** Está en `.gitignore`; lo reconstruye
   `deploy-pages.yml`.
6. **No borrar registros con el enlace roto.** `audit_links.py` los marca tras
   dos semanas; un enlace roto documentado sirve más que un registro que
   desaparece.
7. **Si una comprobación de la sección 2.6 falla, para.** No la desactives.

---

## 6. Cuando algo falla

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| `harvest_run.py` no trae nada | las marcas de agua ya están al día | normal; `--backfill` para recorrer histórico |
| `fetch_evidence.py` sin evidencia utilizable | la página es una SPA sin HTML | añadir un extractor por API en `gather()` |
| `ingest_records.py` bloquea todo | los críticos no coinciden en el acceso | mirar `_blocks`; suele ser correcto |
| `calibrate_triage.py` falla | el léxico dejaría caer un conocido-bueno | ajustar `scripts/lib/lexicon.py`, **no** el umbral |
| `check_contrast.py` falla | un token nuevo no cumple AA | oscurecer/aclarar hasta ≥4.5:1 |
| el build cambia sin tocar datos | algo no determinista (un `set`, un timestamp) | arreglar el origen, no el síntoma |

Estado persistente, por si hay que reiniciar algo:

- `state/harvest_state.json` — hasta dónde llegó cada fuente
- `state/seen.json` — libro mayor de dedup (**recuerda también los rechazos**)
- `state/audit_state.json` — salud de enlaces y hash de la página de acceso
- `queue/*.jsonl` — colas de candidatos (append-only)

Borrar `state/seen.json` hace que se re-tríe todo lo ya descartado. No lo hagas
salvo que quieras exactamente eso.

---

## 7. Cadencia realista

El bot de GitHub Actions corre solo cada domingo y abre un PR. Los pasos 2–4
(los que cuestan tokens) los lanzas tú cuando tengas 30–60 minutos. A 20
registros enriquecidos por semana y ~70% de publicación, el catálogo crece unos
14 registros semanales.
