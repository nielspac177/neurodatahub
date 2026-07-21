export const meta = {
  name: 'neurodatahub-neurosurgery-map',
  description: 'Map clinically-framed neurosurgical research questions onto the existing catalog',
  whenToUse: 'When you want more clinical questions for medical students, mapped by neurosurgical subspecialty',
  phases: [
    { title: 'Survey',   detail: 'which catalogued datasets can actually answer each subspecialty' },
    { title: 'Generate', detail: 'clinically-framed questions per subspecialty' },
    { title: 'Critics',  detail: 'clinical relevance, novelty, data feasibility — blind to each other' },
    { title: 'Emit',     detail: 'write surviving questions as project parts' },
  ],
};

const REPO = '/Users/nielspacheco/neurodatahub';
const PARTS = `${REPO}/drafts/ns-parts`;

// Subespecialidades neuroquirúrgicas reales, no categorías inventadas. El
// usuario es investigador de aneurismas y sus estudiantes son de medicina, así
// que la vascular va primero y todo se enmarca clínicamente.
const SUBSPECIALTIES = [
  { id: 'vascular',    en: 'Cerebrovascular / aneurysm / subarachnoid haemorrhage / AVM' },
  { id: 'tumor',       en: 'Neuro-oncology: glioma, glioblastoma, meningioma, metastasis' },
  { id: 'epilepsy',    en: 'Epilepsy surgery: resection, SEEG, responsive neurostimulation' },
  { id: 'functional',  en: 'Functional: DBS, movement disorders, pain, psychiatric neurosurgery' },
  { id: 'trauma',      en: 'Neurotrauma: TBI, contusion, ICP, decompressive craniectomy' },
  { id: 'csf-spine',   en: 'Hydrocephalus, CSF dynamics, and spine (degenerative + trauma)' },
];

const MODEL = { survey: { model: 'sonnet' }, ideate: {}, clinical: {}, novelty: {},
                feasible: { model: 'sonnet' }, emit: { model: 'haiku', effort: 'low' } };

const SURVEY = {
  type: 'object', required: ['usable_datasets'],
  properties: {
    usable_datasets: { type: 'array', items: {
      type: 'object', required: ['dataset_id', 'why'],
      properties: {
        dataset_id: { type: 'string' },
        why: { type: 'string' },
        variables_available: { type: 'array', items: { type: 'string' } },
      } } },
    gap_note: { type: 'string' },
  },
};

const QUESTIONS = {
  type: 'object', required: ['questions'],
  properties: {
    questions: { type: 'array', items: {
      type: 'object',
      required: ['id', 'question_en', 'question_es', 'dataset_id', 'clinical_rationale',
                 'difficulty', 'skills', 'required_variables'],
      properties: {
        id: { type: 'string' },
        question_en: { type: 'string' }, question_es: { type: 'string' },
        dataset_id: { type: 'string' },
        extra_datasets: { type: 'array', items: { type: 'string' } },
        clinical_rationale: { type: 'string' },
        lens: { type: 'string' },
        difficulty: { type: 'number' },
        effort_weeks: { type: 'number' },
        skills: { type: 'array', items: { type: 'string' } },
        required_variables: { type: 'array', items: { type: 'string' } },
        outcome_measure: { type: 'string' },
      } } },
  },
};

const VERDICT = {
  type: 'object', required: ['question_id', 'verdict', 'reason'],
  properties: {
    question_id: { type: 'string' },
    verdict: { type: 'string' },
    reason: { type: 'string' },
    prior_doi: { type: 'string' },
    still_open_because: { type: 'string' },
    difficulty: { type: 'number' },
    effort_weeks: { type: 'number' },
  },
};

// ---------------------------------------------------------------------------
phase('Survey');
log(`Mapeando ${SUBSPECIALTIES.length} subespecialidades neuroquirúrgicas contra el catálogo`);

const results = await pipeline(
  SUBSPECIALTIES,

  // -- Qué datasets del catálogo sirven de verdad para esta subespecialidad --
  async (sub) => {
    const survey = await agent(
      `Read ${REPO}/data/databases.yml in full.

Subspecialty: ${sub.en}

List ONLY the catalogued datasets that could genuinely support a research
question in this subspecialty, and for each say which concrete variables make
that possible (cohort, imaging modality, outcome fields, follow-up).

Be strict. A dataset of healthy volunteers doing a colour task cannot answer a
question about aneurysm rupture. If nothing in the catalog fits, return an
empty list and explain the gap in gap_note — an honest gap is more useful than
a forced match, because it tells the maintainer what to go and find.

Use the exact 'id' values from the YAML.`,
      { label: `survey:${sub.id}`, phase: 'Survey', schema: SURVEY, ...MODEL.survey }
    );
    return { sub, survey };
  },

  // -- Preguntas clínicas, enmarcadas para un estudiante de medicina --------
  async (prev) => {
    const { sub, survey } = prev;
    const usable = survey?.usable_datasets || [];
    if (!usable.length) {
      log(`· ${sub.id}: sin dataset adecuado — ${survey?.gap_note || ''}`);
      return { ...prev, questions: [] };
    }

    const ideas = await agent(
      `Read ${REPO}/data/databases.yml and ${REPO}/PLAN.md (section 6).

Subspecialty: ${sub.en}
Datasets judged usable: ${JSON.stringify(usable)}

Write 4-6 research questions for MEDICAL STUDENTS — not for ML engineers.
That distinction drives everything:

 - Frame each question around a CLINICAL decision or outcome a neurosurgeon
   argues about on rounds: who rebleeds, who needs a shunt, who benefits from
   surgery, what predicts a poor mRS at 90 days.
 - Prefer questions answerable with clinical variables, imaging descriptors
   and outcome scales over ones needing a novel deep-learning architecture.
 - State the outcome_measure explicitly (mRS, GOS-E, Engel class, survival,
   shunt dependence, reoperation).
 - clinical_rationale must say WHY a neurosurgeon would care about the answer,
   in one sentence a clinician would recognise as true.
 - skills: short tags only (python, statistics, clinical-data, neuroimaging,
   validation, causal-inference). Never sentences.
 - required_variables must name fields the surveyed dataset actually has.
 - difficulty 1-5, where 2-3 is a motivated medical student with basic stats.

dataset_id must be one of the surveyed ids. Write question_en AND question_es.`,
      { label: `ideate:${sub.id}`, phase: 'Generate', schema: QUESTIONS, ...MODEL.ideate }
    );
    return { ...prev, questions: ideas?.questions || [] };
  },

  // -- Tres críticos ciegos entre sí; sólo pueden vetar ---------------------
  async (prev) => {
    const { sub, questions } = prev;
    if (!questions.length) return { ...prev, verdicts: {} };

    const [clinical, novelty, feasible] = await parallel([
      () => parallel(questions.map((q) => () => agent(
        `You are a practising neurosurgeon reviewing a student project proposal.
Your job is to REFUSE weak proposals, not to encourage.

Question: "${q.question_en}"
Claimed rationale: "${q.clinical_rationale}"
Outcome measure: "${q.outcome_measure || 'unstated'}"

Verdict must be one of:
  RELEVANT   a real clinical uncertainty; the answer could change management
  MARGINAL   true but trivial, or the answer changes nothing in practice
  IRRELEVANT not a question any neurosurgeon is actually asking

Be blunt. Most "predict outcome X with ML" proposals are MARGINAL because the
answer never reaches the bedside. Say which decision the answer would change,
or mark it down.`,
        { label: `clinical:${q.id}`, phase: 'Critics', schema: VERDICT, ...MODEL.clinical }
      ).then((v) => (v ? { ...v, question_id: q.id } : v)))),

      () => parallel(questions.map((q) => () => agent(
        `Has this been published already?

Question: "${q.question_en}"

Search, do not speculate — run at least two differently-worded queries:
  curl -s "https://api.openalex.org/works?search=<terms>&per_page=10&select=id,doi,title,publication_year"
  curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<terms>&format=json&pageSize=10"

Verdict: NOVEL | PARTIAL | PUBLISHED
Neurosurgical outcome prediction is a crowded literature, so lean toward
PARTIAL/PUBLISHED when you find close work. If PARTIAL, still_open_because
must name the specific remaining delta.`,
        { label: `novelty:${q.id}`, phase: 'Critics', schema: VERDICT, ...MODEL.novelty }
      ).then((v) => (v ? { ...v, question_id: q.id } : v)))),

      () => parallel(questions.map((q) => () => agent(
        `Read ${REPO}/data/databases.yml.

Question: "${q.question_en}"
Dataset: ${q.dataset_id}${q.extra_datasets?.length ? ` (+ ${q.extra_datasets.join(', ')})` : ''}
Required variables: ${JSON.stringify(q.required_variables)}

Does that dataset, as distributed, actually contain these variables?

Verdict: FEASIBLE | FEASIBLE_WITH_CAVEAT | INFEASIBLE

Neurosurgical specifics are where this usually fails: MIMIC-IV has ICD codes
and vitals but no Hunt-Hess or Fisher grade; BraTS has segmentations but no
survival for every case and no surgical detail; imaging archives rarely carry
90-day mRS. If the outcome scale the question needs is not in the dataset,
that is INFEASIBLE regardless of how good the question is.

Assign your own difficulty (1-5) and effort_weeks, pessimistically.`,
        { label: `feasible:${q.id}`, phase: 'Critics', schema: VERDICT, ...MODEL.feasible }
      ).then((v) => (v ? { ...v, question_id: q.id } : v)))),
    ]);

    const by = (arr) => Object.fromEntries((arr || []).filter(Boolean).map((v) => [v.question_id, v]));
    return { ...prev, verdicts: { clinical: by(clinical), novelty: by(novelty), feasible: by(feasible) } };
  },

  // -- Aplicar vetos y persistir -------------------------------------------
  async (prev) => {
    const { sub, questions, verdicts } = prev;
    const kept = [];

    for (const q of questions) {
      const c = verdicts.clinical?.[q.id];
      const n = verdicts.novelty?.[q.id];
      const f = verdicts.feasible?.[q.id];

      // Cualquiera de los tres puede matar la pregunta por su cuenta.
      if (c && c.verdict === 'IRRELEVANT') continue;
      if (f && f.verdict === 'INFEASIBLE') continue;
      if (n && n.verdict === 'PUBLISHED') continue;
      if (n && n.verdict === 'PARTIAL' && !(n.still_open_because || '').trim()) continue;

      kept.push({
        ...q,
        subspecialty: sub.id,
        difficulty: Math.max(1, Math.min(5, Math.round(f?.difficulty || q.difficulty || 3))),
        effort_weeks: Math.round(f?.effort_weeks || q.effort_weeks || 10),
        clinical_verdict: c?.verdict || 'UNREVIEWED',
        novelty: n?.verdict === 'NOVEL' ? 'novel' : (n?.verdict === 'PARTIAL' ? 'partial' : undefined),
        still_open_because: n?.still_open_because,
        feasibility: f?.verdict === 'FEASIBLE_WITH_CAVEAT' ? 'feasible_with_caveat' : 'feasible',
      });
    }

    log(`✓ ${sub.id}: ${kept.length}/${questions.length} preguntas sobreviven a los tres críticos`);

    if (kept.length) {
      await agent(
        `Write this JSON verbatim to ${PARTS}/${sub.id}.json using the Write tool ` +
        `(create the directory if needed). Do not alter any value.\n\n` +
        JSON.stringify(kept),
        { label: `emit:${sub.id}`, phase: 'Emit', ...MODEL.emit }
      );
    }
    return { subspecialty: sub.id, generated: questions.length, kept: kept.length };
  }
);

const total = results.reduce((a, r) => a + (r?.kept || 0), 0);
const gen = results.reduce((a, r) => a + (r?.generated || 0), 0);
log(`${total}/${gen} preguntas neuroquirúrgicas sobreviven`);
log(`Siguiente: python3 scripts/merge_neurosurgery.py`);
return { total, generated: gen, per_subspecialty: results };
