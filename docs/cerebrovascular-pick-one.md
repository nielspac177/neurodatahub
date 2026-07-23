# Pick one — the 25 cerebrovascular projects, sorted by what it costs you to start

Companion to [`cerebrovascular-program.md`](cerebrovascular-program.md), which has the
hypotheses, statistics and the referee pass. **This file is for choosing.**

Read §1, pick a row, then read that question's card on the site
(`projects/index.html`, filter *Vascular / aneurysm*) and its section in the programme doc.

---

## 1. The only three things that decide this

**Access latency, not interest, is what kills a semester.**

| Dataset | Cost | Time to first byte | Verdict |
|---|---|---|---|
| `openneuro` | free, open | **minutes** | start today |
| `mimic-iv`, `eicu-crd` | free | **1–3 weeks** — PhysioNet credential + CITI "Data or Specimens Only" course; one credential covers both | start the paperwork today, code while you wait |
| `uk-biobank` | **paid** access fee + institutional application | **6–14 weeks**, and you need a supervisor with an approved project | do not start alone; join an existing application |

**The genetics track (C1–C6) is the most original work in the set and the one you cannot
start this month.** If nobody in your group already holds a UK Biobank application, treat
those six as a proposal to write, not a project to run. The ICU tracks are the ones a single
student can actually finish.

---

## 2. If you want my recommendation

**Start with `vascular-icu-ich-early-dnr`.** It is the best question in the set: the outcome
after intracerebral haemorrhage may partly be produced by the prognostic pessimism that
predicts it, and the mediation design — does the DNR order get *followed* by measurably less
treatment? — is the only way to see it in data. MIMIC-IV has code-status timestamps,
procedure codes, vasopressors and ventilation, so the mediator is measurable rather than
assumed. It is difficulty 5 and ~14 weeks, so it needs a real semester and a supervisor who
knows mediation analysis.

**If you want to be running code in two weeks instead:** `vascular-icu-sah-fever-burden`
(difficulty 3, ~9 weeks) — same database, no causal machinery, and a clean negative-control
analysis you can defend.

**If you have nothing but this week:** `vascular-openneuro-imaging-inventory`. Open data, no
credential, and the honest answer (that the big stroke-lesion resource lives outside
OpenNeuro) is itself publishable as a resource.

---

## 3. Start this week — open access

| id | The question in one line | Diff | Weeks | Main risk |
|---|---|---|---|---|
| `vascular-openneuro-imaging-inventory` | What cerebrovascular imaging actually exists in OpenNeuro, and what could a student finish with it? | 2 | 6 | The answer is "very little" — which is the finding, so write it that way from the start |

---

## 4. Neuro-ICU decisions — MIMIC-IV (credential: 1–3 weeks)

Sorted easiest-first. All use ICD-coded cohorts, chart/lab time series and discharge
disposition; none needs imaging, angiography or 90-day mRS.

| id | The question in one line | Diff | Weeks | What you'd learn to do | Main risk |
|---|---|---|---|---|---|
| `vascular-icu-cvt-feasibility` | Is cerebral venous thrombosis even answerable in open ICU data? | 2 | 6 | Cohort phenotyping, power/minimum-detectable-effect analysis | Anticipated answer is "no" — publishable only if you frame it as precision, not as a failed study |
| `vascular-icu-sah-fever-burden` | Does cumulative fever burden after SAH predict outcome beyond severity? | 3 | 9 | Time-series feature building, negative-control analysis | Confounding by infection; without the negative control it's another biomarker paper |
| `vascular-icu-ivh-evd-shunt` | Who converts from external drain to permanent shunt, and does drain timing matter? | 3 | 10 | Survival analysis on procedure codes | Procedure coding misclassifies some drains — quantify it, don't hide it |
| `vascular-icu-stroke-glucose-strategy` | Insulin infusion vs sliding scale in ICU stroke: benefit, or just hypoglycaemia? | 3 | 10 | Propensity scores, safety endpoints | Labelled *well-studied* on the site — SHINE answered the randomised version. Good starter **because** you can check yourself against a known answer |
| `vascular-icu-sah-hyponatremia-strategy` | Correct the sodium or restrict fluids in SAH? | 4 | 11 | Time-varying exposure, propensity weighting | Salt-wasting vs SIADH are indistinguishable in the chart |
| `vascular-icu-ich-reversal-timing` | Does door-to-reversal time change outcome, and differently for DOACs vs warfarin? | 4 | 11 | Survival analysis, drug-administration timestamps, interaction terms | Reversal-agent capture in `emar` may be patchy — pilot the extraction in week 1 |
| `vascular-icu-stroke-sedation-exam` | Do more frequent neuro exams catch deterioration earlier? | 4 | 11 | Documentation-frequency exposures, time-to-detection | Documentation frequency also tracks nurse staffing — adjust at unit level |
| `vascular-icu-nimodipine-interruption` | Hold nimodipine when the pressure drops, or support the pressure and keep it? | 4 | 12 | Clone-censor-weight target-trial emulation | A MIMIC dose-response paper exists; your contribution is the *decision*, so say so explicitly |
| `vascular-icu-sah-transfusion-threshold` | Liberal vs restrictive transfusion in SAH — is the brain the exception? | 4 | 12 | Threshold-strategy emulation, ordinal disposition outcome | Transfusion indication confounding |
| `vascular-icu-sah-cardiac-effect-modification` | Does a stunned heart change the risk–benefit of induced hypertension? | 4 | 12 | Effect modification, troponin/ECG linkage | Interaction tests are underpowered by design — state the MDE first |
| `vascular-icu-ich-early-dnr` | How much of the early-DNR mortality association runs through *less treatment*? | 5 | 14 | Causal mediation, quantitative bias analysis | Code-status timestamps may reflect charting, not the decision |
| `vascular-icu-ich-bp-target-emulation` | Intensive vs standard BP target in the first hours of ICH | 5 | 14 | Marginal structural models, time-varying confounding | Hardest statistics in the set |
| `vascular-icu-ich-evacuation-emulation` | Evacuation vs medical management, emulated as a trial | 5 | 14 | Propensity matching, immortal-time handling | **Confounding by indication is severe** — clot location and volume aren't in the data. Deliver an association with an E-value, not a causal claim |

---

## 5. Between-hospital variation — eICU (same credential)

The question here is never "which patient" but "which hospital", which makes these unusually
good for someone interested in health systems or quality improvement.

| id | The question in one line | Diff | Weeks | What you'd learn | Main risk |
|---|---|---|---|---|---|
| `vascular-eicu-offhours-intervention` | Do nights and weekends delay intervention in haemorrhagic stroke? | 3 | 9 | Time-to-event with cyclic time terms | Mortality is underpowered — keep the process endpoint primary |
| `vascular-eicu-ich-site-variation` | How much ICH mortality variation is the hospital rather than the patient? | 4 | 11 | Hierarchical models, ICC and median odds ratio | Case-mix adjustment quality is the whole ballgame |
| `vascular-eicu-volume-outcome` | Does hospital volume predict survival — the regionalisation argument | 4 | 11 | Site-level covariates, splines | eICU spans ~2 years; the volume denominator caveat belongs in the abstract |
| `vascular-eicu-external-validation-ich-model` | Where does a MIMIC-trained ICH model decalibrate, and why there? | 4 | 12 | TRIPOD reporting, per-site calibration, meta-regression | Cross-schema feature mapping is tedious; budget two weeks for it |
| `vascular-eicu-equity-wlst` | Is the disparity in withdrawal of care *between* hospitals or *within* them? | 4 | 12 | Mixed models, mediation, disparity decomposition | Race is coarsely coded in eICU; prespecify the with/without-site decomposition and never model race as biological |

---

## 6. Genetics — UK Biobank (application + fee; 6–14 weeks, supervisor required)

The most original questions here, and the ones that answer the AVM and inherited-risk angle.
Each is difficulty 4–5 and 13–15 weeks **after** access. Carrier counts, not sample size, are
the binding constraint — every one of these requires computing the minimum detectable
penetrance *before* looking at the result.

| id | The number that would change practice | Diff | Weeks |
|---|---|---|---|
| `vascular-genetics-ccm-penetrance` | Real population penetrance of the cavernoma genes vs the ~80–90 % quoted from affected families — the number you'd give an incidental carrier | 5 | 15 |
| `vascular-genetics-hht-avm-penetrance` | Penetrance of the HHT genes for coded brain AVM, plus how many carriers are never diagnosed at all | 5 | 15 |
| `vascular-genetics-connective-tissue-aneurysm` | Absolute aneurysm/SAH risk in unselected `COL3A1`/`PKD1`/`PKD2`/`FBN1` carriers — the input aneurysm screening guidelines lack | 5 | 14 |
| `vascular-genetics-aneurysm-prs-interaction` | Whether genetic risk changes the *absolute* benefit of quitting smoking or treating blood pressure | 4 | 13 |
| `vascular-genetics-wmh-mediation` | How much of the stroke-PRS effect runs through visible small-vessel damage — can MRI stand in for genotype? | 4 | 13 |
| `vascular-genetics-rnf213-europeans` | A European baseline for a gene currently interpreted from East Asian data | 5 | 13 |

**On AVMs specifically:** `vascular-genetics-hht-avm-penetrance` is as close as this catalogue
gets. It counts diagnoses; it never looks at a nidus. There is no open AVM imaging cohort in
the catalogue and I found no credible candidate to add — see §5 of the programme doc, where
that gap is recorded as a standing want rather than glossed over.

---

## 7. Once you've chosen

1. Open the card on the site and read `still_open_because` — that is the sentence your
   introduction has to beat.
2. Read the matching section of [`cerebrovascular-program.md`](cerebrovascular-program.md)
   for the analysis plan and the prespecified sensitivity analyses.
3. Start the access paperwork the same day, whatever you picked.
4. Week 1 is always the same: build the cohort, count it, and compute the minimum detectable
   effect. If that number is embarrassing, you have learned it in week 1 instead of week 12.
