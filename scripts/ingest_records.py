#!/usr/bin/env python3
"""
ingest_records.py — Puerta de publicación. Re-verifica TODO en Python.

Este script no confía en nada de lo que devolvió el pipeline LLM. Vuelve a
comprobar cada cita contra la evidencia congelada, vuelve a aplicar cada regla
de veto y sólo entonces mezcla en data/databases.yml. Todo lo demás cae en
drafts/needs_human/, que es la cola de revisión semanal del mantenedor.

La comprobación clave es determinista y gratis: cada cita del redactor tiene
que aparecer LITERALMENTE en el texto de la fuente que dice haber citado. Una
cita inventada se detecta con str.find(), sin pedirle su opinión a un segundo
modelo.

    python scripts/ingest_records.py [--dry-run] [--verbose]
"""
import argparse
import json
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import yaml
except ImportError:
    sys.exit("Falta PyYAML.")

from scripts.lib import schema

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
NEEDS_HUMAN = DRAFTS / "needs_human"
DB = ROOT / "data" / "databases.yml"

# Campos que se copian al registro final si sobreviven a los críticos.
MIN_QUOTE_CHARS = 10   # sólo excluye trivialidades; el soporte lo juzga C1

FIELD_NAMES = [
    "modality_primary", "access", "license", "cost", "n_subjects", "years",
    "region", "provider", "doi", "diseases", "data_types", "species",
    "short_desc_en", "short_desc_es", "access_notes",
]


def norm(s):
    """Normaliza para comparar citas: sin acentos, espacios colapsados.

    La comparación NO es laxa en el contenido — sólo tolera diferencias de
    espaciado y de forma unicode, que son artefactos de extraer texto de HTML,
    no reescrituras del modelo.
    """
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"\s+", " ", s).strip().lower()


class Report:
    def __init__(self):
        self.published, self.blocked = [], []
        self.hallucinated_quotes = 0
        self.stripped_fields = 0
        self.projects_kept = self.projects_killed = 0


def check_quotes(record, evidence):
    """Comprobación determinista: ¿cada cita existe literalmente?

    Devuelve (campos_ok, campos_falsos). Es la única verificación del sistema
    que no puede engañarse: no depende del juicio de ningún modelo.
    """
    texts = {s["src_id"]: norm(s["text"]) for s in evidence.get("sources", [])}
    ok, fake = set(), {}

    for name, field in (record.get("fields") or {}).items():
        if not isinstance(field, dict) or field.get("value") in (None, "", []):
            continue
        quotes = field.get("evidence") or []
        if not quotes:
            fake[name] = "sin cita"
            continue
        grounded = False
        for q in quotes:
            body = norm(q.get("quote"))
            src = texts.get(q.get("src"), "")
            # Esta comprobación responde UNA sola pregunta: ¿la cita existe
            # literalmente en la fuente? Es la prueba anti-invención, y es la
            # única del sistema que no puede engañarse.
            #
            # Si la cita SOSTIENE o no el valor es una pregunta distinta, y de
            # ésa se encarga el crítico C1. Mezclarlas fue un error: un mínimo
            # de 20 caracteres rechazaba "License: CC0" (12 caracteres,
            # literal y concluyente). El mínimo sólo excluye trivialidades
            # como "CC0" a secas, que casarían con cualquier cosa.
            if len(body) >= MIN_QUOTE_CHARS and body in src:
                grounded = True
                break
        if grounded:
            ok.add(name)
        else:
            fake[name] = f"cita no encontrada en {[q.get('src') for q in quotes]}"
    return ok, fake


def resolve_access(drafted, critic, report):
    """Regla asimétrica de acceso.

    Devuelve (acceso, confianza, nota, bloquea).

    La asimetría es específicamente sobre 'open'. Publicar 'open' de más manda
    al estudiante a descargar algo que en realidad exige un DUA; publicar de
    más restrictivo sólo le cuesta un clic. Por eso:

      - los dos coinciden            -> publica
      - sólo el crítico, y NO es open -> publica (medium); errar por exceso
                                         de cautela es seguro
      - sólo el crítico, y ES open    -> BLOQUEA; 'open' exige dos
                                         derivaciones independientes
      - desacuerdo                    -> toma el más restrictivo y BLOQUEA
      - el crítico no sabe            -> BLOQUEA
    """
    d = (drafted or {}).get("value")
    c = (critic or {}).get("access")
    conf = (critic or {}).get("confidence", "low")

    if c in (None, "unknown"):
        return None, "low", "el crítico de acceso no pudo determinar los términos", True
    if d == c:
        return c, conf, None, False
    if d is None:
        if c == "open":
            return c, "low", "'open' con una sola derivación — requiere confirmación", True
        return c, "medium", "sólo el crítico determinó el acceso", False

    order = schema.ACCESS_RESTRICTIVENESS
    try:
        worst = order[max(order.index(d), order.index(c))]
    except ValueError:
        return None, "low", f"valor de acceso inválido: {d!r} vs {c!r}", True
    return worst, "low", f"desacuerdo: redactor={d}, crítico={c}; se toma {worst}", True


def _rating(*values):
    """Toma la valoración más pesimista y la ACOTA a un entero 1-5.

    Los críticos devuelven a veces 7 o 4.5 pese al esquema. Sin acotar, un
    solo valor fuera de rango hace que schema.validate rechace el lote entero
    y no se publique nada — un fallo de formato tumbando trabajo válido.
    """
    best = None
    for v in values:
        if v in (None, ""):
            continue
        try:
            n = int(round(float(v)))
        except (TypeError, ValueError):
            continue
        n = max(schema.DIFFICULTY_MIN, min(schema.DIFFICULTY_MAX, n))
        best = n if best is None else max(best, n)
    return best


def _join_critic(verdicts, projects):
    """Empareja veredictos con proyectos, por id y si no por POSICIÓN.

    Los críticos se lanzan con projects.map(), así que el veredicto i
    corresponde al proyecto i. La posición es la verdad; el project_id que
    devuelve el modelo es sólo una pista. Fiarse del id hizo que dos vetos
    INFEASIBLE reales se perdieran en silencio y se publicaran proyectos que
    los críticos habían rechazado.
    """
    ids = {p.get("id") for p in projects}
    out = {}
    for i, v in enumerate(verdicts):
        if not isinstance(v, dict):
            continue
        vid = v.get("project_id")
        key = vid if vid in ids else (projects[i].get("id") if i < len(projects) else None)
        if key:
            out[key] = v
    return out


def build_record(draft, evidence, report, verbose=False):
    """Aplica todas las reglas de veto. Devuelve (registro, motivos_de_bloqueo)."""
    blocks = []
    rid = draft["id"]

    ok_quotes, fake_quotes = check_quotes(draft, evidence)
    if fake_quotes:
        report.hallucinated_quotes += len(fake_quotes)
        if len(fake_quotes) >= 3:
            blocks.append(f"{len(fake_quotes)} citas no verificables")

    verdicts = {v["field"]: v["verdict"]
                for v in ((draft.get("critics") or {}).get("grounding") or {}).get("verdicts", [])}

    rec = {"id": rid}
    for name in FIELD_NAMES:
        field = (draft.get("fields") or {}).get(name)
        if not isinstance(field, dict):
            continue
        value = field.get("value")
        if value in (None, "", []):
            continue

        if name in fake_quotes:
            report.stripped_fields += 1
            if verbose:
                print(f"    − {name}: {fake_quotes[name]}")
            continue

        v = verdicts.get(name)
        if v == "CONTRADICTED":
            blocks.append(f"campo contradicho por la evidencia: {name}")
            continue
        if v == "UNSUPPORTED":
            # Se elimina, nunca se adivina ni se conserva.
            report.stripped_fields += 1
            if verbose:
                print(f"    − {name}: crítico C1 UNSUPPORTED")
            continue

        rec[name] = value

    rec["name"] = draft.get("name") or rid

    # Si C1 refutó la fundamentación del campo `access`, la respuesta del
    # redactor deja de contar como derivación independiente. Sin esto, un
    # valor que el crítico de fundamentación declaró no sostenido seguiría
    # sumando como "los dos coinciden" y publicaría 'open' con confianza alta.
    drafted_access = (draft.get("fields") or {}).get("access")
    if verdicts.get("access") in ("UNSUPPORTED", "CONTRADICTED") or "access" in fake_quotes:
        drafted_access = None

    access, conf, note, access_blocks = resolve_access(
        drafted_access, (draft.get("critics") or {}).get("access"), report)
    if access is None:
        blocks.append(note or "acceso indeterminado")
    else:
        rec["access"] = access
        rec["access_confidence"] = conf
        if access_blocks:
            blocks.append(note)
        elif note:
            rec.setdefault("access_notes", note)
        crit = (draft.get("critics") or {}).get("access") or {}
        if crit.get("license") and "license" not in rec:
            rec["license"] = crit["license"]

    # --- proyectos: novedad y viabilidad ---
    projects_in = draft.get("projects") or []
    nov = _join_critic((draft.get("critics") or {}).get("novelty", []), projects_in)
    fea = _join_critic((draft.get("critics") or {}).get("feasibility", []), projects_in)

    kept, closed = [], []
    for p in draft.get("projects") or []:
        pid = p.get("id")
        n, f = nov.get(pid), fea.get(pid)

        if n and n.get("verdict") == "PUBLISHED":
            closed.append({"title": p.get("question_en"), "doi": n.get("prior_doi", ""),
                           "task": "ya publicado"})
            report.projects_killed += 1
            continue
        if f and f.get("verdict") == "INFEASIBLE":
            report.projects_killed += 1
            continue

        proj = {
            "id": pid,
            "question_en": p.get("question_en"),
            "question_es": p.get("question_es") or p.get("question_en"),
            "lens": p.get("lens") if p.get("lens") in schema.VALID_LENS else None,
            "skills": p.get("skills") or [],
            "compute": p.get("compute") if p.get("compute") in schema.VALID_COMPUTE else None,
            "status": "open",
            "unverified": False,
        }

        # Ante desacuerdo, se toma SIEMPRE el valor pesimista del crítico:
        # una dificultad optimista es lo que hace que un estudiante abandone
        # el proyecto a mitad de camino.
        if f:
            proj["difficulty"] = _rating(p.get("difficulty"), f.get("difficulty"))
            proj["effort_weeks"] = max(int(float(p.get("effort_weeks") or 0)),
                                       int(float(f.get("effort_weeks") or 0))) or None
            proj["feasibility"] = ("feasible_with_caveat"
                                   if f.get("verdict") == "FEASIBLE_WITH_CAVEAT" else "feasible")
        else:
            proj["difficulty"] = _rating(p.get("difficulty"))
            proj["effort_weeks"] = (int(float(p["effort_weeks"]))
                                    if p.get("effort_weeks") else None)

        if n and n.get("verdict") == "PARTIAL":
            reason = (n.get("still_open_because") or p.get("still_open_because") or "").strip()
            if not reason:
                # 'partial' sin el delta explícito no le sirve a nadie.
                report.projects_killed += 1
                continue
            proj["novelty"] = "partial"
            proj["still_open_because"] = reason
            if n.get("prior_doi"):
                proj["prior_work"] = [{"doi": n["prior_doi"], "what_was_done": "trabajo previo cercano"}]
        elif n and n.get("verdict") == "NOVEL":
            proj["novelty"] = "novel"

        kept.append({k: v for k, v in proj.items() if v not in (None, "", [])})
        report.projects_kept += 1

    if kept:
        rec["projects"] = kept

    lit = draft.get("literature") or {}
    pubs = [p for p in (lit.get("key_publications") or []) if isinstance(p, dict)] + closed
    if pubs:
        rec["key_publications"] = pubs[:8]
    if lit.get("n_citing_works") is not None:
        rec["literature"] = {
            "n_citing_works": lit.get("n_citing_works"),
            "saturation": lit.get("saturation"),
            "dominant_tasks": lit.get("dominant_tasks") or [],
        }

    if draft.get("access_steps"):
        rec["access_steps"] = draft["access_steps"]
    if draft.get("starter_code"):
        rec["starter_code"] = draft["starter_code"]

    cand = evidence.get("candidate") or {}
    rec["url"] = cand.get("url")
    rec["last_verified"] = date.today().isoformat()
    rec["status"] = "published"
    rec["provenance"] = {
        "discovered_by": cand.get("discovered_by"),
        "discovered_at": cand.get("discovered_at"),
        "pipeline_version": draft.get("pipeline_version", "enrich/1.0"),
    }
    rec["verification"] = {
        "verified_at": date.today().isoformat(),
        "grounded_fields": sorted(ok_quotes),
        "stripped_fields": sorted(fake_quotes),
        "evidence": [{"src_id": s["src_id"], "url": s["url"], "sha256": s["sha256"]}
                     for s in evidence.get("sources", [])],
    }

    # Campos obligatorios del esquema: sin ellos no se publica.
    for req in schema.REQUIRED:
        if not rec.get(req):
            blocks.append(f"falta campo obligatorio: {req}")

    return rec, blocks


def append_to_yaml(records):
    """Añade al final de databases.yml.

    Se AÑADE en vez de reescribir el archivo entero para no reformatear los
    registros existentes: un diff de revisión debe mostrar sólo lo nuevo.
    """
    chunks = []
    for r in records:
        text = yaml.safe_dump([r], allow_unicode=True, sort_keys=False,
                              default_flow_style=False, width=100)
        chunks.append(text)
    with DB.open("a", encoding="utf-8") as f:
        f.write("\n" + "\n".join(chunks))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    drafts = sorted(DRAFTS.glob("*.record.json"))
    if not drafts:
        sys.exit("No hay borradores. Corre antes el workflow de enriquecimiento.")

    existing = {r["id"] for r in (yaml.safe_load(DB.read_text(encoding="utf-8")) or [])}
    report = Report()
    to_publish = []

    for path in drafts:
        draft = json.loads(path.read_text(encoding="utf-8"))
        rid = draft.get("id", path.stem)
        ev_path = DRAFTS / f"{rid}.evidence.json"
        if not ev_path.exists():
            print(f"  ✗ {rid}: sin paquete de evidencia — no verificable")
            report.blocked.append((rid, ["sin evidencia"]))
            continue

        evidence = json.loads(ev_path.read_text(encoding="utf-8"))
        if args.verbose:
            print(f"\n  {rid}")

        rec, blocks = build_record(draft, evidence, report, args.verbose)

        if rid in existing:
            blocks.append("el id ya existe en el catálogo")

        if blocks:
            report.blocked.append((rid, blocks))
            print(f"  ⚠️  {rid}: BLOQUEADO — {blocks[0]}")
            if not args.dry_run:
                NEEDS_HUMAN.mkdir(parents=True, exist_ok=True)
                (NEEDS_HUMAN / f"{rid}.record.json").write_text(
                    json.dumps({**draft, "_blocks": blocks}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                path.unlink()
        else:
            to_publish.append(rec)
            print(f"  ✅ {rid}: publicable ({len(rec.get('projects', []))} proyectos)")

    # Última red: el esquema tiene que aceptar el lote completo.
    if to_publish:
        errors, _ = schema.validate(to_publish)
        if errors:
            print("\nEl esquema rechaza el lote; no se publica nada:", file=sys.stderr)
            for e in errors[:10]:
                print(f"  - {e}", file=sys.stderr)
            to_publish = []

    print(f"\n{'─' * 58}")
    print(f"  publicables            {len(to_publish)}")
    print(f"  bloqueados             {len(report.blocked)}")
    print(f"  citas no verificables  {report.hallucinated_quotes}")
    print(f"  campos eliminados      {report.stripped_fields}")
    print(f"  proyectos conservados  {report.projects_kept}")
    print(f"  proyectos descartados  {report.projects_killed}")

    if args.dry_run:
        print("\n(dry-run: no se escribió nada)")
        return

    if to_publish:
        shutil.copy(DB, DB.with_suffix(".yml.bak"))
        append_to_yaml(to_publish)
        for r in to_publish:
            p = DRAFTS / f"{r['id']}.record.json"
            if p.exists():
                p.unlink()
        print(f"\n{len(to_publish)} registros -> data/databases.yml "
              f"(copia previa en databases.yml.bak)")
        print("Siguiente: python3 scripts/build.py")

    if report.blocked:
        print(f"\nRevisa drafts/needs_human/ — {len(report.blocked)} registros esperan tu criterio.")


if __name__ == "__main__":
    main()
