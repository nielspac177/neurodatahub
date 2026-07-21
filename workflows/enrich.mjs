export const meta = {
  name: 'neurodatahub-enrich',
  description: 'Enrich dataset candidates into full records via adversarial critic panel',
  whenToUse: 'After scripts/harvest_run.py + scripts/fetch_evidence.py have produced drafts/*.evidence.json',
  phases: [
    { title: 'Scope',     detail: 'cheap in/out-of-scope gate before any token spend' },
    { title: 'Draft',     detail: 'fill schema fields, every value carrying a verbatim quote' },
    { title: 'Context',   detail: 'literature map via cited_by + project ideation' },
    { title: 'Critics',   detail: 'blind adversarial panel: grounding, access, novelty, feasibility' },
    { title: 'Assemble',  detail: 'apply veto rules, write drafts/<id>.record.json' },
  ],
};

// ---------------------------------------------------------------------------
// Los ficheros de evidencia son la única entrada. args.ids permite reprocesar
// un subconjunto; sin él se procesa todo lo que haya en drafts/.
// ---------------------------------------------------------------------------
const IDS = (args && args.ids) || null;
const LIMIT = (args && args.limit) || 8;

const SCOPE = {
  type: 'object',
  required: ['in_scope', 'reason'],
  properties: {
    in_scope: { type: 'boolean' },
    reason: { type: 'string' },
    modality_primary: { type: 'string' },
    disease_tags: { type: 'array', items: { type: 'string' } },
  },
};

// Cada campo lleva su cita. Un campo sin cita DEBE ser null: es la regla que
// hace verificable todo lo demás.
const FIELD = {
  type: 'object',
  required: ['value', 'evidence'],
  properties: {
    value: {},
    evidence: {
      type: 'array',
      items: {
        type: 'object',
        required: ['src', 'quote'],
        properties: { src: { type: 'string' }, quote: { type: 'string' } },
      },
    },
    needs: { type: 'string' },
  },
};

const DRAFT = {
  type: 'object',
  required: ['id', 'name', 'fields'],
  properties: {
    id: { type: 'string' },
    name: { type: 'string' },
    fields: {
      type: 'object',
      properties: {
        modality_primary: FIELD, access: FIELD, license: FIELD, cost: FIELD,
        n_subjects: FIELD, years: FIELD, region: FIELD, provider: FIELD,
        doi: FIELD, diseases: FIELD, data_types: FIELD, species: FIELD,
        short_desc_en: FIELD, short_desc_es: FIELD, access_notes: FIELD,
      },
    },
    access_steps: { type: 'array', items: { type: 'object' } },
    starter_code: { type: 'object' },
  },
};

const LITERATURE = {
  type: 'object',
  required: ['n_citing_works', 'saturation'],
  properties: {
    n_citing_works: { type: 'number' },
    saturation: { type: 'string', enum: ['low', 'medium', 'high'] },
    dominant_tasks: { type: 'array', items: { type: 'string' } },
    key_publications: { type: 'array', items: { type: 'object' } },
    summary_en: { type: 'string' },
  },
};

const IDEAS = {
  type: 'object',
  required: ['projects'],
  properties: {
    projects: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'question_en', 'lens', 'difficulty', 'required_variables'],
        properties: {
          id: { type: 'string' },
          question_en: { type: 'string' }, question_es: { type: 'string' },
          lens: { type: 'string' },
          difficulty: { type: 'number' },
          skills: { type: 'array', items: { type: 'string' } },
          required_variables: { type: 'array', items: { type: 'object' } },
          effort_weeks: { type: 'number' },
          compute: { type: 'string' },
          still_open_because: { type: 'string' },
        },
      },
    },
  },
};

const GROUNDING = {
  type: 'object',
  required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        required: ['field', 'verdict'],
        properties: {
          field: { type: 'string' },
          verdict: { type: 'string', enum: ['SUPPORTED', 'UNSUPPORTED', 'CONTRADICTED'] },
          note: { type: 'string' },
        },
      },
    },
  },
};

const ACCESS = {
  type: 'object',
  required: ['access', 'confidence'],
  properties: {
    access: { type: 'string', enum: ['open', 'registration', 'credentialed', 'dua', 'application', 'unknown'] },
    license: { type: 'string' },
    cost: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    evidence_quote: { type: 'string' },
    reasoning: { type: 'string' },
  },
};

const NOVELTY = {
  type: 'object',
  required: ['project_id', 'verdict'],
  properties: {
    project_id: { type: 'string' },
    verdict: { type: 'string', enum: ['NOVEL', 'PARTIAL', 'PUBLISHED'] },
    prior_doi: { type: 'string' },
    queries_run: { type: 'array', items: { type: 'string' } },
    still_open_because: { type: 'string' },
  },
};

const FEASIBILITY = {
  type: 'object',
  required: ['project_id', 'verdict'],
  properties: {
    project_id: { type: 'string' },
    verdict: { type: 'string', enum: ['FEASIBLE', 'FEASIBLE_WITH_CAVEAT', 'INFEASIBLE'] },
    missing_variables: { type: 'array', items: { type: 'string' } },
    difficulty: { type: 'number' },
    effort_weeks: { type: 'number' },
    reason: { type: 'string' },
  },
};

const REPO = '/Users/nielspacheco/neurodatahub';

// ---------------------------------------------------------------------------
phase('Scope');
log('Leyendo paquetes de evidencia congelados de drafts/');

const listing = await agent(
  `List the evidence bundles in ${REPO}/drafts/.
Run: ls ${REPO}/drafts/*.evidence.json
For each file (max ${LIMIT}${IDS ? `, restricted to these ids: ${IDS.join(', ')}` : ''}),
read it and return the id, the candidate title, and the src_id + kind of each source.
Return ONLY compact JSON: {"items":[{"id":..,"title":..,"sources":[{"src":"e1","kind":".."}]}]}`,
  { label: 'inventory', phase: 'Scope',
    schema: { type: 'object', required: ['items'], properties: {
      items: { type: 'array', items: { type: 'object' } } } } }
);

const items = (listing?.items || []).slice(0, LIMIT);
log(`${items.length} candidatos con evidencia`);

// ---------------------------------------------------------------------------
// Un candidato recorre TODAS las etapas por su cuenta (pipeline, sin barrera):
// el que tarda no bloquea al que va rápido.
// ---------------------------------------------------------------------------
const results = await pipeline(
  items,

  // -- Etapa 0: alcance. Puerta barata; corta antes de gastar tokens. -------
  async (item) => {
    const scope = await agent(
      `Read ${REPO}/drafts/${item.id}.evidence.json.

Decide if this is IN SCOPE for a catalog of datasets for NEUROLOGICAL,
NEUROSURGICAL, PSYCHIATRIC or BCI research, usable by students.

In scope: human neuro/psych data (EEG, iEEG, MEG, MRI/fMRI, PET, genetics of
brain disorders, clinical neuro cohorts, BCI).
Out of scope: non-neuro organs, animal-only with no translational framing,
climate/geo/engineering, and anything that is not a reusable dataset.

Base the decision ONLY on the evidence text. Be strict — a false positive
costs the whole downstream pipeline.`,
      { label: `scope:${item.id}`, phase: 'Scope', schema: SCOPE, effort: 'low' }
    );
    return { item, scope };
  },

  // -- Etapa 2: redactor. Sólo ve la evidencia. -----------------------------
  async (prev) => {
    if (!prev?.scope?.in_scope) return { ...prev, skipped: 'out_of_scope' };
    const { item } = prev;

    const draft = await agent(
      `Read ${REPO}/drafts/${item.id}.evidence.json and draft a catalog record.

Read ${REPO}/data/databases.yml first to see the exact field conventions.

RULES — these are absolute:
1. Every field value MUST be accompanied by a VERBATIM quote copied
   character-for-character from one of the evidence sources, with its src id.
2. If a value is NOT stated in the evidence, set value to null and fill
   "needs" with the name of the page that would answer it.
   NEVER infer, estimate, or fill from your own knowledge. An empty field is
   correct and useful; a guessed field is a defect.
3. access must be one of: open | registration | credentialed | dua | application.
   Judge from the LICENSE and access terms in the evidence, not from the vibe.
4. short_desc_en AND short_desc_es: write both, one sentence, factual.
   These two are the only fields you may compose rather than quote, but they
   must not assert anything the evidence does not support.

Also draft access_steps (ordered, each {step_en, step_es, eta}) and
starter_code {python, r} ONLY if the evidence shows the actual file layout.
Omit them entirely otherwise.`,
      { label: `draft:${item.id}`, phase: 'Draft', schema: DRAFT }
    );
    return { ...prev, draft };
  },

  // -- Etapas 3 y 4 en paralelo: literatura e ideación ----------------------
  async (prev) => {
    if (prev?.skipped || !prev?.draft) return prev;
    const { item, draft } = prev;
    const doi = draft.fields?.doi?.value || item.doi || '';

    const [literature, ideas] = await parallel([
      () => agent(
        `Map what has ALREADY been published using this dataset: "${draft.name}".
${doi ? `Its DOI is ${doi}.` : ''}

Preferred method — the citation graph, not keyword guessing:
1. Resolve the DOI to an OpenAlex work id:
   curl -s "https://api.openalex.org/works/doi:${doi}"
2. List the works that CITE it — those are the papers that actually USED it:
   curl -s "https://api.openalex.org/works?filter=cites:<WORK_ID>&per_page=25&select=id,doi,title,publication_year,cited_by_count"
If there is no DOI, fall back to a Europe PMC search on the dataset name.

Classify citing works by task (outcome-prediction, biomarker, segmentation,
subtyping, causal, external-validation, foundation-model) and method.
Set saturation: high if the obvious analyses are clearly done, low if barely used.
n_citing_works must be the real number you observed, 0 if none.`,
        { label: `lit:${item.id}`, phase: 'Context', schema: LITERATURE }
      ),
      () => agent(
        `Read ${REPO}/drafts/${item.id}.evidence.json and ${REPO}/PLAN.md (section 6).

Propose 3-5 research projects a bioengineering or medical STUDENT could
actually do with this dataset, using the six gap lenses in PLAN.md §6:
generalization, multimodal, causal, equity, neuromodulation, foundation-models.

HARD REQUIREMENT: every project must list required_variables, and each one
must name a variable/file that the evidence SHOWS this dataset contains
(cite the src id). If you cannot ground a variable in the evidence, do not
propose the project. Ideas that need data the dataset lacks are worse than
no ideas — they waste a student's semester.

difficulty is 1-5. effort_weeks must be realistic for one student.
Write question_en and question_es for each.`,
        { label: `ideas:${item.id}`, phase: 'Context', schema: IDEAS }
      ),
    ]);
    return { ...prev, literature, ideas };
  },

  // -- Etapa 5: panel adversarial. Los críticos SÓLO pueden vetar. ----------
  async (prev) => {
    if (prev?.skipped || !prev?.draft) return prev;
    const { item, draft, ideas, literature } = prev;
    const projects = ideas?.projects || [];

    const critics = await parallel([
      // C1 — fundamentación. Además del juicio del modelo, ingest_records.py
      // vuelve a comprobar cada cita por subcadena en Python.
      () => agent(
        `Adversarial grounding check. Your job is to REFUTE, not to agree.

Read ${REPO}/drafts/${item.id}.evidence.json.
Here is a drafted record:
${JSON.stringify(draft.fields).slice(0, 6000)}

For EVERY field, verify:
 (a) does the quoted text appear VERBATIM in the cited source? and
 (b) does that quote actually SUPPORT the value, or merely sit near it?

SUPPORTED    = quote is verbatim AND genuinely establishes the value
UNSUPPORTED  = quote missing, paraphrased, or does not establish the value
CONTRADICTED = the evidence states something different

Default to UNSUPPORTED when uncertain. A field wrongly marked SUPPORTED
puts an unverified claim in front of students.`,
        { label: `c1-grounding:${item.id}`, phase: 'Critics', schema: GROUNDING }
      ),

      // C2 — acceso, derivado A CIEGAS. No ve la respuesta del redactor.
      () => agent(
        `Read ${REPO}/drafts/${item.id}.evidence.json.

Independently determine the ACCESS TERMS of this dataset from the evidence
alone. Report the license verbatim and classify:

  open          anyone can download immediately, no account
  registration  free account, no approval step
  credentialed  training/credentialing required (e.g. CITI + PhysioNet)
  dua           signed data use agreement
  application   formal application reviewed by a committee

Quote the exact licence/access sentence you relied on.
If the evidence does not state the terms, answer "unknown" with confidence
low. Do NOT infer from the repository's general reputation — some datasets
on otherwise-open repositories carry their own restrictions.`,
        { label: `c2-access:${item.id}`, phase: 'Critics', schema: ACCESS }
      ),

      // C3 — novedad, por proyecto.
      // El project_id se estampa AQUÍ, desde la variable del bucle, y pisa lo
      // que devuelva el modelo. Pedirle a un agente que repita una clave de
      // correlación que el orquestador ya conoce es pedirle que se la invente:
      // en la primera corrida los críticos generaron ids propios y el join se
      // rompió en silencio, tirando vetos INFEASIBLE reales.
      () => parallel(projects.map((p) => () => agent(
        `Has this research question ALREADY been published?

Question: "${p.question_en}"
Dataset: "${draft.name}"

Search actively, do not speculate:
  curl -s "https://api.openalex.org/works?search=<terms>&per_page=10&select=id,doi,title,publication_year"
  curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<terms>&format=json&pageSize=10"
Run at least 2 differently-worded searches and report them in queries_run.

PUBLISHED = someone has clearly done this (give prior_doi)
PARTIAL   = done in adjacent form; then still_open_because MUST state the
            specific remaining delta, citing the prior work
NOVEL     = no close prior work found

Be skeptical: a question that is already answered wastes a student's time,
so lean toward PUBLISHED/PARTIAL when you find close work.`,
        { label: `c3-novelty:${p.id}`, phase: 'Critics', schema: NOVELTY }
      ).then((v) => (v ? { ...v, project_id: p.id } : v)))),

      // C4 — viabilidad, por proyecto.
      () => parallel(projects.map((p) => () => agent(
        `Read ${REPO}/drafts/${item.id}.evidence.json.

Can a student actually DO this project with this dataset as distributed?

Question: "${p.question_en}"
Claimed required variables: ${JSON.stringify(p.required_variables)}
Claimed difficulty: ${p.difficulty}, effort: ${p.effort_weeks} weeks

Check EACH required variable against the evidence (file listing, README,
modalities, subject count). List any that you cannot confirm exist in
missing_variables.

INFEASIBLE if a required variable is absent, or the sample is far too small
for the claimed analysis, or it cannot fit in one 15-week semester including
access latency.

Assign your OWN difficulty and effort_weeks. Be pessimistic: students
consistently underestimate, and an over-optimistic rating is what makes them
abandon a project halfway.`,
        { label: `c4-feasibility:${p.id}`, phase: 'Critics', schema: FEASIBILITY }
      ).then((v) => (v ? { ...v, project_id: p.id } : v)))),
    ]);

    return {
      ...prev,
      critics: {
        grounding: critics[0],
        access: critics[1],
        novelty: (critics[2] || []).filter(Boolean),
        feasibility: (critics[3] || []).filter(Boolean),
      },
    };
  },

  // -- Ensamblado: aplicar los vetos y escribir el borrador ----------------
  async (prev) => {
    if (prev?.skipped) {
      log(`✗ ${prev.item.id}: fuera de alcance — ${prev.scope?.reason || ''}`);
      return { id: prev.item.id, status: 'out_of_scope' };
    }
    if (!prev?.draft) return { id: prev?.item?.id, status: 'failed' };

    const { item, draft, literature, ideas, critics } = prev;

    const payload = {
      id: item.id,
      name: draft.name,
      scope: prev.scope,
      fields: draft.fields,
      access_steps: draft.access_steps || [],
      starter_code: draft.starter_code || {},
      literature,
      projects: ideas?.projects || [],
      critics,
      pipeline_version: 'enrich/1.0',
    };

    await agent(
      `Write this JSON verbatim to ${REPO}/drafts/${item.id}.record.json
using the Write tool. Do not reformat, summarise, or alter any value —
downstream Python re-verifies every field and any edit you make would
corrupt the audit trail.

${JSON.stringify(payload)}

Then reply with exactly: written`,
      { label: `write:${item.id}`, phase: 'Assemble', effort: 'low' }
    );

    const g = critics.grounding?.verdicts || [];
    const bad = g.filter((v) => v.verdict !== 'SUPPORTED').length;
    const killed = (critics.novelty || []).filter((n) => n.verdict === 'PUBLISHED').length
      + (critics.feasibility || []).filter((f) => f.verdict === 'INFEASIBLE').length;
    log(`✓ ${item.id}: ${g.length - bad}/${g.length} campos fundamentados, ` +
        `acceso=${critics.access?.access}(${critics.access?.confidence}), ` +
        `${payload.projects.length - killed}/${payload.projects.length} proyectos sobreviven`);

    return { id: item.id, status: 'drafted', ungrounded: bad, killed };
  }
);

const ok = results.filter((r) => r?.status === 'drafted');
log(`${ok.length}/${items.length} registros redactados -> drafts/*.record.json`);
log('Siguiente: python3 scripts/ingest_records.py  (re-verifica TODO en Python)');

return {
  drafted: ok.length,
  out_of_scope: results.filter((r) => r?.status === 'out_of_scope').length,
  results,
};
