# NeuroDataHub

Catálogo curado de las bases de datos **clínicas, genéticas, de neuroimagen, electrofisiología y BCI** más importantes para investigación en enfermedades **neuroquirúrgicas, neurológicas y psiquiátricas**.

Sitio estático (GitHub Pages) · contribuidor único · actualización semanal asistida.

🔗 **Sitio**: `https://<tu-usuario>.github.io/neurodatahub/` (tras configurar Pages)

---

## Cómo funciona

- **`data/databases.yml`** — la *fuente de verdad*. Cada base es un registro (esquema abajo).
- **`scripts/build.py`** — convierte el YAML en `data/databases.json` (validado) que consume el sitio.
- **`index.html`** — sitio de una sola página: filtros por modalidad / categoría / acceso, buscador y toggle ES/EN. Sin dependencias ni build pesado.
- **`scripts/research_update.py`** — escaneo semanal: consulta OpenAlex, Zenodo y Europe PMC recorriendo la matriz *enfermedad × modalidad*, deduplica contra el catálogo y escribe candidatos.
- **`.github/workflows/weekly-update.yml`** — cron dominical que corre el escaneo y **abre un Pull Request** con los candidatos (nunca publica solo).
- **`.github/workflows/deploy-pages.yml`** — publica el sitio en cada push a `main`.

El flujo mantiene **un único contribuidor**: el bot solo abre PRs; tú revisas, curas y mergeas.

---

## Puesta en marcha

```bash
# 1. Crear el repo en tu cuenta y subir estos archivos
git init && git add . && git commit -m "init: NeuroDataHub"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/neurodatahub.git
git push -u origin main

# 2. Generar los datos y ver el sitio localmente
pip install -r requirements.txt
python scripts/build.py
python -m http.server 8000   # abrir http://localhost:8000
```

**Activar GitHub Pages**: Settings → Pages → Source = *GitHub Actions*.
**Permitir PRs del bot**: Settings → Actions → General → *Allow GitHub Actions to create and approve pull requests*.
**(Opcional)** Settings → Secrets → Actions → `OPENALEX_MAILTO` con tu email (mejor cuota en OpenAlex).

---

## Añadir una base de datos

Añade un bloque a `data/databases.yml` y corre `python scripts/build.py`:

```yaml
- id: identificador-unico
  name: Nombre visible
  modality_primary: neuroimaging   # clinical | neuroimaging | genetics | electrophysiology | bci | multimodal | aggregator
  diseases: [parkinson, epilepsy]
  disease_category: [neurological]
  provider: Institución
  url: https://...
  access: open                     # open | registration | credentialed | dua | application
  access_notes: "Requisitos de acceso"
  license: "..."
  n_subjects: "..."
  years: "..."
  region: "..."
  short_desc_es: "Descripción en español."
  short_desc_en: "Description in English."
  key_publications: ["Uso publicado dominante", "..."]
  open_questions: ["Pregunta abierta 1", "..."]
  last_verified: "2026-07-21"
  tags: [benchmark, longitudinal]
```

Campos obligatorios: `id`, `name`, `modality_primary`, `diseases`, `access`, `url`.

---

## Nota legal

Este catálogo **enlaza a fuentes oficiales y no redistribuye datos**. Muchas bases son de acceso controlado (credencial, DUA o solicitud); el campo `access` lo indica. Respeta siempre la licencia y el acuerdo de uso de cada fuente.

## Licencia

Código y metadatos del catálogo: MIT (ver `LICENSE`). Los datasets enlazados conservan sus propias licencias.
