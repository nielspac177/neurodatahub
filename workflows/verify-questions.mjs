export const meta = {
  name: 'neurodatahub-verify-questions',
  description: 'Run the adversarial critic panel over existing unverified project questions',
  whenToUse: 'To upgrade questions marked "unverified idea" to critic-reviewed, or after a run died before critics finished',
  phases: [
    { title: 'Load',    detail: 'read unverified questions from the catalog' },
    { title: 'Critics', detail: 'clinical relevance, novelty, data feasibility — blind to each other' },
    { title: 'Emit',    detail: 'write verdicts for a Python update pass' },
  ],
};

const REPO = '/Users/nielspacheco/neurodatahub';
const PARTS = `${REPO}/drafts/verify-parts`;

// Por defecto verifica sólo las preguntas con subespecialidad (las clínicas
// neuroquirúrgicas). args.all=true incluiría todas las 'unverified'.
const ONLY_SUBSPECIALTY = !(args && args.all);

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

const LIST = {
  type: 'object', required: ['questions'],
  properties: {
    questions: { type: 'array', items: {
      type: 'object',
      required: ['id', 'question_en', 'dataset_id'],
      properties: {
        id: { type: 'string' }, question_en: { type: 'string' },
        dataset_id: { type: 'string' },
        clinical_rationale: { type: 'string' },
        outcome_measure: { type: 'string' },
        required_variables: { type: 'array', items: { type: 'string' } },
      } } },
  },
};

// ---------------------------------------------------------------------------
phase('Load');
const list = await agent(
  `Read ${REPO}/data/databases.yml. Collect every project that has
"unverified: true"${ONLY_SUBSPECIALTY ? ' AND a "subspecialty:" field' : ''}.
For each, return its id, question_en, dataset_id, and (if present)
clinical_rationale, outcome_measure and required_variables. Return them all.`,
  { label: 'load-unverified', phase: 'Load', schema: LIST, model: 'sonnet' }
);

const questions = list?.questions || [];
log(`${questions.length} preguntas sin verificar a revisar`);

// ---------------------------------------------------------------------------
// Cada pregunta pasa por los tres críticos, ciegos entre sí. Igual que en la
// generación: sólo pueden vetar.
const verdicts = await pipeline(
  questions,
  async (q) => {
    const [clinical, novelty, feasible] = await parallel([
      () => agent(
        `You are a practising neurosurgeon / neurointensivist reviewing a
student project. REFUSE weak proposals.

Question: "${q.question_en}"
Rationale: "${q.clinical_rationale || '(none given)'}"
Outcome: "${q.outcome_measure || 'unstated'}"

Verdict: RELEVANT | MARGINAL | IRRELEVANT
RELEVANT only if the answer could change management at the bedside. Most
"predict outcome with ML" proposals are MARGINAL. Say which decision changes.`,
        { label: `clinical:${q.id}`, phase: 'Critics', schema: VERDICT }
      ).then((v) => (v ? { ...v, question_id: q.id } : v)),

      () => agent(
        `Has this been published already?
Question: "${q.question_en}"
Search, do not speculate — at least two differently-worded queries:
  curl -s "https://api.openalex.org/works?search=<terms>&per_page=10&select=id,doi,title,publication_year"
  curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<terms>&format=json&pageSize=10"
Verdict: NOVEL | PARTIAL | PUBLISHED. If PARTIAL, still_open_because must name
the remaining delta and prior_doi the closest work.`,
        { label: `novelty:${q.id}`, phase: 'Critics', schema: VERDICT }
      ).then((v) => (v ? { ...v, question_id: q.id } : v)),

      () => agent(
        `Read ${REPO}/data/databases.yml.
Question: "${q.question_en}"
Dataset: ${q.dataset_id}
Required variables: ${JSON.stringify(q.required_variables || [])}
Does that dataset, as distributed, contain these variables?
Verdict: FEASIBLE | FEASIBLE_WITH_CAVEAT | INFEASIBLE.
If the outcome scale the question needs is not in the dataset, INFEASIBLE.
Assign your own difficulty (1-5) and effort_weeks, pessimistically.`,
        { label: `feasible:${q.id}`, phase: 'Critics', schema: VERDICT, model: 'sonnet' }
      ).then((v) => (v ? { ...v, question_id: q.id } : v)),
    ]);

    const rec = {
      id: q.id,
      clinical: clinical?.verdict,
      novelty: novelty?.verdict,
      novelty_still_open: novelty?.still_open_because,
      novelty_prior_doi: novelty?.prior_doi,
      feasible: feasible?.verdict,
      difficulty: feasible?.difficulty,
      effort_weeks: feasible?.effort_weeks,
    };

    // Se escribe una parte por pregunta, en cuanto termina: si el límite corta
    // la corrida, lo ya verificado no se pierde.
    await agent(
      `Write this JSON verbatim to ${PARTS}/${q.id}.json using Write ` +
      `(create the directory if needed). Do not alter any value.\n\n` +
      JSON.stringify(rec),
      { label: `emit:${q.id}`, phase: 'Emit', model: 'haiku', effort: 'low' }
    );
    return rec;
  }
);

const survived = verdicts.filter((v) => v &&
  v.clinical !== 'IRRELEVANT' && v.feasible !== 'INFEASIBLE' && v.novelty !== 'PUBLISHED');
log(`${survived.length}/${verdicts.length} preguntas sobreviven a los críticos`);
log('Siguiente: python3 scripts/apply_verification.py');
return { reviewed: verdicts.length, survived: survived.length };
