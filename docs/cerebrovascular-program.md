# Cerebrovascular programme — hypotheses, analysis plans, appraisal and gaps

*Rama `cerebrovascular`. Este documento acompaña a las 25 preguntas de subespecialidad
`vascular` añadidas al catálogo. Contiene lo que el YAML no puede contener: la hipótesis
detrás de cada pregunta, el plan estadístico, la crítica y —sobre todo— lo que el catálogo
**no** puede responder hoy.*

Generated with `/scientific-brainstorming`, `/hypothesis-generation`, `/statistical-analysis`,
`/scientific-critical-thinking` and `/peer-review`. Every prior-work claim below was checked
against the literature on 2026-07-22; the DOIs cited are carried into `data/databases.yml`
as `prior_work` so a student can check the novelty claim rather than trust it.

---

## 1. What the catalogue can actually answer

| Track | Datasets | What makes it possible | n reachable |
|---|---|---|---|
| **A. Neuro-ICU decisions** | `mimic-iv` | ICD-9/10 I60–I63, drug-level `prescriptions`/`emar`/`inputevents`, minute-level `chartevents`, procedure codes, discharge disposition | hundreds–low thousands of SAH/ICH ICU stays |
| **B. Between-hospital variation** | `eicu-crd` (+ `mimic-iv`) | ~200 hospitals with site metadata, APACHE severity, code-status fields | thousands of haemorrhagic-stroke admissions |
| **C. Cerebrovascular genetics** | `uk-biobank` | ~470k exomes + array genotypes, HES/ICD linkage, death registry, ~100k brain MRI incl. SWI and WMH IDPs | population-scale; carrier counts are the limiting factor |
| **D. Imaging inventory** | `openneuro` | BIDS metadata queryable through the API | unknown — that is the question |

Nothing in the catalogue contains angiography, aneurysm morphology, Hunt-Hess/Fisher grades,
mRS at 90 days, or an AVM imaging cohort. Every question below was written to stay inside
that boundary; §5 lists what would have to be harvested to cross it.

---

## 2. Track A — Neuro-ICU decisions (13 questions, `mimic-iv`)

**Framing hypothesis.** The outcome after aneurysmal SAH and spontaneous ICH is shaped less
by the initial bleed — which is fixed by the time the patient reaches the unit — than by a
small number of reversible ICU decisions: whether nimodipine survives the first hypotensive
episode, how anaemia and sodium are handled, how fast anticoagulation is reversed, and how
early the goals of care are narrowed.

| # | Question id | H₁ (directional) | Falsifier |
|---|---|---|---|
| A1 | `vascular-icu-nimodipine-interruption` | Holding nimodipine for hypotension, rather than supporting the pressure, is associated with worse disposition | Null or reversed association after clone-censor-weighting, with adequate precision |
| A2 | `vascular-icu-sah-transfusion-threshold` | The brain at risk of delayed ischaemia benefits from a liberal threshold, unlike other organs | No difference across the Hb 8–10 g/dL contrast |
| A3 | `vascular-icu-sah-fever-burden` | Fever burden predicts outcome beyond severity, and the association is not explained by infection | Association vanishes under negative-control/infection adjustment |
| A4 | `vascular-icu-sah-hyponatremia-strategy` | Active sodium correction beats fluid restriction in a vasospasm-prone patient | No difference in mortality or vasopressor days |
| A5 | `vascular-icu-sah-cardiac-effect-modification` | Neurogenic cardiac injury modifies the risk–benefit of induced hypertension | Interaction term indistinguishable from zero |
| A6 | `vascular-icu-ich-early-dnr` | A measurable part of the early-DNR mortality association runs through reduced treatment intensity | Mediated proportion ≈ 0: the order tracks severity, not care |
| A7 | `vascular-icu-ich-bp-target-emulation` | Achieved-target strategy, not variability, is what matters | Emulated strategies do not separate |
| A8 | `vascular-icu-ich-reversal-timing` | Door-to-reversal time predicts mortality, more steeply for DOAC than warfarin | Flat time–outcome gradient |
| A9 | `vascular-icu-ich-evacuation-emulation` | Evacuation shifts disposition even where it does not shift mortality | Neither endpoint moves after matching |
| A10 | `vascular-icu-ivh-evd-shunt` | Early drain placement changes shunt conversion risk | Timing is unrelated once severity is matched |
| A11 | `vascular-icu-stroke-glucose-strategy` | Infusion-based tight control buys no benefit and costs hypoglycaemia | Route makes no safety difference |
| A12 | `vascular-icu-stroke-sedation-exam` | More frequent exams detect deterioration earlier | No difference in time-to-detection after staffing adjustment |
| A13 | `vascular-icu-cvt-feasibility` | Cerebral venous thrombosis is too rare in open ICU data to support inference | A usable cohort exists |

**Shared analysis plan (A1, A2, A4, A7, A9, A11).**

1. *Estimand.* Per-protocol effect of a treatment **strategy**, not of a baseline exposure.
   State it as a target trial: eligibility, treatment strategies, assignment procedure,
   follow-up start, outcome, causal contrast, analysis plan.
2. *Design.* Clone-censor-weight for strategies defined by a decision that happens after
   admission (A1, A7); propensity-score matching or overlap weights where the decision is
   effectively made at a single time (A2, A9, A11).
3. *Model.* Pooled logistic regression for in-hospital mortality with inverse-probability-of-
   censoring weights; multinomial or ordinal model for discharge disposition
   (home / rehab / skilled facility / death) — an ordinal disposition endpoint is the closest
   ICU proxy for a shifted mRS, and it should be analysed as ordinal, not dichotomised away.
4. *Confounder set.* Age, admission GCS, first-24h vitals and labs, comorbidity index,
   ventilation, vasopressors, injury/haemorrhage coding, admission year (practice drift).
5. *Reporting.* Risk difference **and** risk ratio with 95% CI, plus an E-value for the
   primary estimate. STROBE, and RECORD for the routinely-collected-data items.
6. *Precision first.* Compute the minimum detectable risk difference from the realised cohort
   size **before** looking at the estimate, and report it whatever the result. A null with a
   stated MDE is a finding; a null without one is a wasted semester.

**Sensitivity analyses to prespecify.** (i) Negative-control outcome — an endpoint the
exposure cannot plausibly affect (e.g. hospital-acquired urinary infection); a "significant"
effect there indicts the confounding control. (ii) Negative-control exposure. (iii) E-value
for unmeasured confounding. (iv) Immortal-time check: re-run with follow-up starting at the
decision time rather than at admission — for A9 and A10 this is the single most likely way
to manufacture a false benefit. (v) Missing-data mechanism: chart data are MAR at best;
multiple imputation with the outcome in the imputation model, never complete-case-only.

---

## 3. Track B — Between-hospital variation (5 questions, `eicu-crd`)

**Framing hypothesis.** For haemorrhagic stroke, a measurable share of outcome variance sits
at the hospital, not the patient — and the mechanism is process (time to intervention,
withdrawal culture, procedure availability), not case mix.

- `vascular-eicu-ich-site-variation` — hierarchical logistic model with a hospital random
  intercept; report the **ICC** and the **median odds ratio** (the MOR is the interpretable
  one: the median increase in odds when moving a patient from a lower- to a higher-mortality
  hospital). Then add site covariates and report how much residual variance they absorb.
- `vascular-eicu-volume-outcome` — volume as a site-level covariate with a restricted cubic
  spline; the denominator caveat (eICU spans ~2 years) goes in the abstract, not the appendix.
- `vascular-eicu-external-validation-ich-model` — TRIPOD reporting; per-hospital AUC,
  calibration slope and intercept, calibration plots for the worst and best sites, then a
  meta-regression of calibration slope on site characteristics.
- `vascular-eicu-equity-wlst` — the key analytical move is fitting the disparity **with and
  without** the hospital random effect. If the coefficient collapses once site is in the
  model, the disparity is between hospitals (a policy problem); if it survives, it is within
  hospitals (a bedside-conversation problem). Prespecify this decomposition; do not let the
  data choose the framing afterwards. Race in eICU is coarse and partly imputed — report the
  misclassification, and do not model race as a biological variable.
- `vascular-eicu-offhours-intervention` — time-to-event with admission hour as a cyclic term;
  the process endpoint is primary because mortality is underpowered.

---

## 4. Track C — Cerebrovascular genetics (6 questions, `uk-biobank`)

This is the track the ICU data cannot reach, and the one that answers the AVM question.

**Framing hypothesis (ascertainment).** Everything clinicians quote about cavernoma, HHT and
familial aneurysm risk comes from families that were sequenced *because* someone bled.
Penetrance measured in an unselected population must therefore be lower — possibly much
lower — and the gap between the two numbers is the finding.

| # | Question id | The number that changes practice |
|---|---|---|
| C1 | `vascular-genetics-ccm-penetrance` | Population penetrance of `KRIT1`/`CCM2`/`PDCD10` LoF, versus the ~80–90 % quoted from pedigrees |
| C2 | `vascular-genetics-hht-avm-penetrance` | Phenotypic penetrance of `ENG`/`ACVRL1`/`SMAD4` LoF, and the fraction of carriers with no HHT diagnosis at all |
| C3 | `vascular-genetics-connective-tissue-aneurysm` | Absolute aneurysm/SAH risk in unselected `COL3A1`/`PKD1`/`PKD2`/`FBN1` carriers — the input a screening guideline needs |
| C4 | `vascular-genetics-aneurysm-prs-interaction` | Whether genetic risk changes the *absolute* benefit of quitting smoking or treating BP |
| C5 | `vascular-genetics-wmh-mediation` | How much of the stroke-PRS effect runs through visible small-vessel damage |
| C6 | `vascular-genetics-rnf213-europeans` | A European population baseline for a gene currently interpreted from East Asian data |

**Analysis plan for the penetrance questions (C1–C3).**

1. *Variant calling.* Predicted loss-of-function (nonsense, frameshift, canonical splice) via
   a fixed annotation pipeline; ClinVar pathogenic/likely-pathogenic as a separate, stricter
   stratum. Prespecify the two strata — sliding between them after seeing counts is p-hacking
   with a genomics accent. Missense is excluded for CCM genes (almost all causative variants
   are truncating) and handled separately for the connective-tissue genes.
2. *Phenotype.* HES/ICD + death registry + primary care where available; for C1, add
   imaging-visible lesions in the SWI subsample, which raises penetrance relative to the
   ICD-only definition and gives an honest range rather than a point estimate.
3. *Estimator.* Cumulative incidence by age with **death as a competing risk** (Aalen–Johansen,
   not 1 − Kaplan–Meier), carriers versus matched non-carriers; report penetrance by age 60
   and by age 75 with CIs.
4. *Ancestry.* Restrict the primary analysis to the largest genetically-inferred ancestry
   group, then report others separately with their own CIs — never pooled with a single
   principal-component adjustment and never silently dropped.
5. *Power first, again.* With plausible carrier frequencies (order 1 in 5,000–20,000 for these
   genes), the expected carrier count is tens to low hundreds. Compute and report the
   **minimum detectable penetrance** and the width of the CI at the expected count *before*
   running the outcome model. If the CI will span 5–60 %, say so in the abstract; that is
   still a more honest number than the pedigree estimate it replaces.
6. *Healthy-volunteer bias.* UK Biobank participants are healthier than the population and
   were recruited at 40–69, so anyone who died of a bleed at 25 is absent. This biases
   penetrance **down**, in the same direction as the hypothesis — which means a low estimate
   is partly design, and must be stated as a bound, not a measurement.

**C4/C5 specifics.** PRS weights from published GWAS summary statistics with the UK Biobank
contribution removed where possible (sample overlap inflates the score's apparent
performance — winner's curse). For C5, mediation via WMH volume requires no unmeasured
mediator–outcome confounding, which is not credible on its own; report the E-value-style
sensitivity for the mediated proportion and present it as a bound.

---

## 5. What the catalogue cannot answer — the honest gap list

This is the part the user asked for directly: **AVMs**. There is no arteriovenous-malformation
imaging or angiographic dataset in the catalogue, and there is no aneurysm-morphology dataset
either. The genetics track (C2) reaches AVM biology through HHT carriers and ICD code Q28.2,
and that is genuinely the best the current catalogue can do — but it can only count diagnoses,
never look at a nidus.

To close the gap, these resources are worth putting through the normal harvest→evidence→ingest
pipeline (they are **candidates, not verified records** — none has been link-audited yet):

| Candidate | Why it matters | Note |
|---|---|---|
| ATLAS v2.0 (stroke lesion masks, n = 1,271, BIDS) | The largest curated stroke-lesion resource; enables lesion-symptom and segmentation projects | Lives at ICPSR / Grand Challenge, **not** OpenNeuro — which is why `vascular-openneuro-imaging-inventory` will come back thin |
| ISLES challenge series | Acute ischaemic stroke lesion segmentation with perfusion/DWI | Challenge-hosted, licence per edition |
| Aneurysm imaging challenges (ADAM, CADA, IntrA and similar) | Would unlock morphology-based rupture-risk questions the ICU data cannot touch | Verify hosting and licence before cataloguing |
| An AVM/cavernoma imaging cohort | **No credible open candidate identified.** This is a real hole in the open-data landscape, not an oversight of this catalogue | Worth recording as a standing want |
| GIGASTROKE / MEGASTROKE summary statistics | Would give C4/C5 proper stroke GWAS weights without leaning on PGC (which is psychiatric only) | Summary-stat download, low access friction |

Two catalogue records also deserve a note: `enigma` is listed with psychiatric and
neurological working groups but no vascular one, and `pgc` is psychiatric-only — so neither
supports a cerebrovascular question on its own today, and C4/C5 list them as `extra_datasets`
only for the summary-statistics workflow, not as the source of stroke weights.

---

## 6. Referee pass — what a reviewer would say before this goes on the site

**Recommendation: publish with the caveats below made visible on each card** (they are, via
`still_open_because` and `feasibility`).

**Major.**

1. *Confounding by indication is the shared fatal risk in Track A.* A9 (evacuation) is the
   worst case: the patients who get operated on differ from those who do not in ways no ICU
   table records (clot location and volume, brainstem compression, surgeon judgement). It is
   marked `feasible_with_caveat` and its `still_open_because` names the limitation, but a
   student must be told at the start that the honest deliverable is a well-characterised
   association with an E-value, not a causal claim.
2. *The MIMIC-SAH literature is saturated with "biomarker X versus mortality" papers* — sodium,
   anion gap, platelet-to-RDW ratio, SpO₂, plasma volume status, first-day ICP. Every question
   here was written to avoid that genre by making a **decision**, not a lab value, the
   exposure. A3 (fever burden) is the closest to the genre and is the one most in need of the
   negative-control analysis to justify its existence.
3. *Power is the binding constraint in Track C and in A13, and it is under the student's
   control only through honesty.* Each of these carries an explicit instruction to report the
   minimum detectable effect. Reviewers should refuse any of these write-ups that reports a
   null without one.
4. *A6 (early DNR) is the strongest question in the set and also the most ethically loaded.*
   Mediation through treatment intensity is the right design, but code-status documentation in
   MIMIC is imperfect and timestamps may reflect charting, not decision. Prespecify a
   quantitative-bias analysis for exposure misclassification.

**Minor.**

5. A11 (glucose) is labelled `well-studied` on the site rather than open — SHINE answered the
   randomised question; what is left is a delivery-route safety comparison. Kept because it is
   an excellent starter project with a known answer to check against, and the label says so.
6. C6 (RNF213 in Europeans) will very likely return a null. It is kept deliberately, framed as
   a precision statement, because a documented European baseline is useful and because
   students should see one project where the anticipated answer is "we cannot tell, and here
   is how precisely we cannot tell."
7. A13 and D1 (`vascular-openneuro-imaging-inventory`) are inventory/feasibility projects.
   They are cheap, publishable as resources, and they protect the next student from a doomed
   project — which is why they sit at difficulty 2.
8. Multiplicity: within each question the primary outcome is single and named. Across the 25,
   nobody should treat the set as a family — but a student running several must not report the
   best one as if it were the only one.

**What was rejected during drafting.** Aneurysm-morphology rupture-risk prediction, Hunt-Hess
or Fisher-grade-stratified vasospasm questions, 90-day mRS as an endpoint, angiographic
vasospasm as an outcome, and any AVM imaging project — all require data the catalogue does
not have. They are listed in §5 as harvest targets rather than dressed up as answerable.

---

## 7. Reproducing this

```bash
git checkout cerebrovascular
python3 scripts/merge_neurosurgery.py --dry-run   # revalida drafts/ns-parts/vascular.json
python3 scripts/merge_neurosurgery.py
python3 scripts/build.py                          # 22 bases, 97 proyectos, 56 páginas
```

`drafts/ns-parts/vascular.json` is the source of truth for these questions; `data/databases.yml`
is generated from it by the same Python validator that guards every other contribution — the
model never wrote to the catalogue directly.
