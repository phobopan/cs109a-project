# CS109a Final Project — Group Plan

**Project:** Forecasting the next standardized 100 m beach-litter count (OSPAR Beach Litter Surveys, Northeast Atlantic)
**Group size:** 3
---

## 1. Deadlines at a glance

| Milestone | Due | Weight | Deliverables |
|---|---|---|---|
| MS2 — Data Wrangling & Project Redefinition | **Fri Nov 13, 9:59 pm ET** (TF presentation during week of Mon Nov 9) | 10% | 8–10 min presentation; slides PDF; cleaning notebook `.ipynb`; revised proposal (1–2 pp PDF) |
| MS3 — EDA, Baseline Model, Pipeline | **Mon Nov 30** | 20% | 10 min presentation + slides; EDA; baseline model; proposed train/test pipeline |
| MS4 — Final Modeling & Deliverables | **Thu Dec 10** | 68% | 2000–2500 word report; 6 min video; commented notebook |

---

## 2. Roles

Three standing workstreams, so nobody waits on a vague "we'll all look at the data." Each person owns their stream across all milestones; the **writing/presentation lead rotates** so presentation load stays even.

| | Member A — Data | Member B — Analysis | Member C — Modeling & Infra |
|---|---|---|---|
| Owns | Acquisition, cleaning, the panel table, data dictionary | Missingness, distributions, EDA, error analysis | Repo, pipeline code, CV harness, baselines & models |
| MS2 | Download + clean + build survey-level panel | Missingness/outlier/scale audit, diagnostic plots | Repo setup, environment, leakage audit, notebook assembly |
| MS3 | Feature engineering (lags, seasonality, gaps) | Full EDA, figures | Baseline + first real model, time-aware CV |
| MS4 | Final feature table, reproducibility check | Error analysis by beach/season, limitations | Final model tuning, results tables |

---

## 3. Milestone 2 — Data Wrangling & Project Redefinition (now → Nov 13)

### 3.1 Handling the Data

> The milestone spec is explicit: *"A project that only has a plan to collect data will not receive credit."* Data downloaded is the gate for this week.

#### Data Download

The export lives at **[beachlitter.ospar.org](https://beachlitter.ospar.org/) → Survey data → Survey data export**. Four facts from the portal that shape the project:

- **Coverage ends 31-12-2020.** The form states *"Latest survey date available is 31-12-2020."* This is a closed historical record, not a live feed. The question is unaffected — forecasting the next survey from prior surveys works fine on historical data — but the revised proposal must state the coverage as 2001–2020 and avoid language implying current monitoring.
- **OSPAR "years" are not calendar years.** The form notes: *"Year = Periods 1, 2, 3 & 4 e.g. 2011 = Dec 2010 to Oct 2011."* Surveys run in four seasonal periods and a survey year spans December to October. The period number is the ready-made seasonality feature; the Dec–Oct boundary is a trap for any year-based train/test split.
- **Beach IDs are stable codes** (`BE001`, `DK001`, `GRL001`, …), listed with country, region and beach name on the Beach list page. Key the panel on the **ID, never the name**. One quirk: Greenland and Faroe beaches are filed under "Denmark (incl. the Faeroe Islands)" but sit in the Arctic Seas region, so country and region are not nested.
- **Scale:** 20 years × up to 4 periods ≈ up to ~80 surveys for a well-monitored beach, across 7 regions and 13 countries. That is comfortably enough history for lagged features.

#### Primary source: ODIMS (downloaded and tested Nov 1)

The survey portal went down on Nov 1, but OSPAR publishes the same monitoring data through **ODIMS** ([odims.ospar.org](https://odims.ospar.org/)) as static files with no form in front of them. Search *beach litter* → **OSPAR Marine Litter Beach Monitoring - 100m sampling units**, published once per year (submissions seen for 2020–2023; the dataset history runs back to March 2015). Each annual submission offers an `.xlsx` of survey data (2023: 349 KB), a shapefile of the sampling units (94 KB), and a metadata XML.

#### Confirmed data issues (verified across all nine ODIMS years)

0. **Corrected Nov 9 — the sub-code rule was incomplete.** Excluding the 20 sub-codes outright loses every row where the parent was left blank and only the newer codes were used: 416 rows. `SE005` switched to the sub-codes in 2021, so one survey read 1,574 items instead of 216,274 and its series showed a collapse that never happened. The loader now uses the parent where recorded and falls back to the sub-codes where not, recovering ~386,000 items (~9% of the panel). Baselines moved to 602 / 699 / 821; the ordering is unchanged.

1. **Columns double-count.** Old aggregate codes and newer sub-codes coexist for the same litter *in every year* — this is a fixed feature of the schema, not drift across releases. In 2023, `Plastic: Food [6]` sums to 3,530 while `Food_plastic [610]` + `Food_eps [620]` sums to 3,463, with 342 rows populating both. The working convention used in testing: keep the 116 main count columns and exclude the 20 newer sub-codes. The same pattern holds for Cups, Fishboxes, Plastic_small, Plastic_large, String and cotton buds. **Summing all numeric columns roughly doubles those categories.** Neither convention is complete alone — about 15 rows carry only the old code, others only the sub-codes. Pick one, document the choice.
2. **`Period` = −1** on 25 rows, all August 2023, one per beach. A sentinel for missing, not a period number — do not let it into a model as a number.
3. **Two non-count columns.** `Survey: Pellets [998]` is Yes/No text and `Survey: Remarks [999]` is free text; exclude both from sums. Worth reading the remarks: several note records revised post hoc during national QC in March 2024, a data-provenance point a TF may probe.
4. **One duplicate record.** `UK057` (Aberdeen North N1) on 23/09/2023, two Survey IDs, identical counts. Handled by the second dedup rule above.
5. **Target is heavily skewed.** Confirms the `log1p` plan from the proposal.
6. **A `-99` sentinel.** One cell — `Pollutants: Other [111]` for beach `GRL003` on 2020-07-31 — is `-99`, which drives that survey's total negative and makes `log1p` return NaN. Screen for negative counts and treat them as missing, not as values.
7. **21 surveys have a total of exactly zero** (10 beaches, on the merged panel). **Resolved Nov 3: keep them.** Six of the ten are Greenland and Icelandic beaches whose *nonzero* surveys have medians of 1–3 items, so a zero there is entirely credible; `GRL004` and `GRL006` are zero across their whole recorded history. One exception to check by hand: `UK046`, 4 zeros out of 11 surveys on a beach with a nonzero median of 26 — read its remarks before trusting it.
8. **`Period` = −1 accounts for 282 of 3,858 surveys (7.3%)** across all nine years, not just 2023 — a persistent category, not a one-off.

- **A:** Export the CSV using exactly these settings, then save it to `data/raw/` untouched:

  | Field | Selection | Why |
  |---|---|---|
  | Select survey type | **`100m`** (the default) | Matches the standardized protocol in the proposal. `1km` is a different protocol with incomparable counts — do not export or merge it |
  | Year | **leave `- None selected -`** | The dropdown takes one year at a time and *overrides* the date range; leaving it blank is what allows a full-history pull |
  | From date | **`01-01-2001`** | Earliest year offered. Format is DD-MM-YYYY, not US order |
  | To date | **`31-12-2020`** | Last date in the database |
  | Region | **leave `- None selected -`** | Full NE Atlantic matches the proposal's scope; filtering only cuts beaches and shortens per-beach histories |
  | Country | **leave `- None selected -`** | Same reason |
  | File name | `ospar_100m_2001_2020` | Self-documenting |

  Record the **download date, the portal URL, and the settings above**, and report the file size in MB — the notebook must state it. *Fallback:* if a 20-year pull times out or returns something malformed, export year by year with the Year dropdown and concatenate the 20 files in pandas.
- **A:** Determine the **unit of a row**. This is the central question of the whole milestone. OSPAR exports are often one row per *litter type per survey*, not one row per survey. If so, you need a documented pivot/aggregation to a survey-level table (one row = one beach × one survey date), and the material/type breakdown becomes a set of columns.
- **B:** Write the **data dictionary**: every column, its meaning, its type, its units, and whether it is available *before* the survey being predicted. That last flag drives the leakage analysis.
- **C:** Set up repo, `requirements.txt`, and `src/data.py` with a `load_raw()` function. Start `CITATIONS.md`.
- **All (Thu session):** Agree on the unit of observation and the target variable definition. Write both down in one sentence each.

**Internal deadline — Sun Nov 1:** raw data in `data/raw/`, data dictionary drafted, one row's meaning agreed.

#### A second code change, in 2010 

The year-median series has an unexplained step: ~200 items per survey in 2007–09, then **370 / 438 / 366** in 2010/11/12, falling back to ~240. Three explanations were possible — new countries, different beaches, or a counting change. The first two are ruled out:

- **Not composition.** Restricting to the 35 beaches surveyed in all three windows barely moves it: median **205 → 386.5 → 232**.
- **Entirely plastic.** On those same beaches the plastic median goes 133 → 307 → 181 while *every other material* is flat or declining. A real environmental pulse would not be plastic-only and would not reverse.
- **Four codes are exactly zero through 2009 and nonzero from 2010**: `Plastic: Rope [31]`, `Plastic: Bag_ends [112]`, `Plastic: Fish_tags [114]`, `Wood: Fish_boxes [119]`. That is the same signature as the 2015 sub-code change — **OSPAR expanded the code list in 2010 as well.** Nothing in the documentation told us; the data did.

**Honest limit:** the new codes do not explain the whole step. `Rope [31]` adds ~19 items per survey against a mean jump of ~190. Most of the remainder sits in `String [32]` and the plastic fragment codes, which existed before 2010 but are counted several times more often after it — consistent with broader counting guidance changing, which we cannot prove from the data alone.

**Consequence for the modeling:** calendar year is confounded across this boundary. Prefer **within-beach** features over cross-sectional ones, and make sure no train/test split straddles 2010 or 2015.

#### Empirical results that change the modeling plan 

These were run on 3,641 beach-survey transitions across 207 beaches. They are preliminary — a quick pass, not the Milestone 3 analysis — but each one changes a decision already written into this plan.

**1. Survey spacing does not drive the count.** On the full 22.8-year panel (5,633 transitions, 239 beaches): **−0.001 pooled, +0.031 within beach**. Gaps are regular anyway (median 92 days, IQR 82–110; the long tail comes from beaches that skip a year, max 1,130). Keep `days since previous survey` as a feature — it is cheap and the proposal commits to it — but expect it to carry almost no weight, and say so rather than letting a reader assume it matters.

**2. Most of the apparent predictability is cross-sectional, not temporal.** Previous count vs. next count, on logs, modeling set: **+0.702 pooled but only +0.277 within beach**. (The within-beach figure rose from +0.218 on the nine-year panel — more history, better estimate.) The pooled figure mostly says some beaches are consistently dirtier than others. A model given beach identity will post a respectable R² while having learned almost nothing about *change over time*. Report both, and treat the within-beach number as the honest measure of what the lag features add.

**3. The naive previous-value baseline is the worst of the three.** Mean absolute error on the stacked panel:

| Baseline | MAE (full panel) |
|---|---|
| Beach historical median | **602** |
| Global median | 699 |
| Previous survey's count | 821 |

Single surveys are volatile, so last-quarter's count is a noisier predictor than the beach's own median. **Make the beach historical median the primary benchmark**, not the previous value — the proposal offers both, and this says which one a model actually has to beat. Expect beating it to be harder than it sounds.

**3b. The protocol change is dated precisely: 2015.** The 20 newer sub-code columns sum to **exactly zero before 2015** and to 918,257 after. The newer codes simply did not exist in the early era. This settles the convention question — the 116 main count columns are the only definition valid across all 22.8 years, so use them and say why.

**3c. A possible second regime around 2010–2012.** Median total per calendar year sits near 140–200 for 2001–2009, jumps to 370 (2010), 438 (2011) and 366 (2012), then settles into 190–305 from 2013 on. That step is large enough to be a reporting or protocol change rather than a real litter trend. Investigate during EDA before reading any long-run trend from this panel.

**4. Seasonality is real and consistent.** Median totals by period across all nine years: P1 (Dec–Jan) 275, P2 (Apr) 250, P3 (Jun–Jul) 177, P4 (Sep–Oct) 206. Winter runs roughly 50% above summer. Note P2's mean (1,193) is far above its median (250) — spring carries extreme outliers worth a look during EDA.

**5. Mild downward trend.** Median total per OSPAR year falls from 232 (2015) to 190 (2023), with a 2018 spike to 327.

### 3.2 Cleaning Data

Work the spec's checklist explicitly — the grade is on *reasoning about the data*, so each decision needs a recorded "why."

**Member A — cleaning and the panel table**
- Parse survey dates; sort surveys **chronologically within each beach**.
- Resolve beach identity: are beach names/IDs stable across years? Watch for renamed sites, duplicate IDs, and country/region inconsistencies.
- De-duplicate: identical beach + date rows, and surveys logged twice under different IDs.
- Standardize the survey length (the 100 m protocol) — drop or flag surveys of non-standard length, since counts aren't comparable otherwise.
- Build `data/processed/panel.csv`: one row per beach-survey, with the **total litter count** target plus the columns needed later.
- Report final **rows × columns** — the revised proposal requires this number.

**Member B — the data audit**
- **Missingness:** percent missing per column, plus whether missingness is patterned — by country, by region, by year. A column that is 60% missing before 2015 and complete after is a finding that changes the plan.
- **Unusual values:** zero-count surveys (real or a recording convention?), extreme counts, negative or impossible values, implausible dates.
- **Scale:** range of every numeric column. Count features and any area/length features will be on wildly different scales — note which models will need standardization.
- **Target distribution:** histogram of total litter count. The proposal already anticipates skew; check it and decide whether `log1p(count)` is the modeling target. Decide now, record the reason.
- **Survey cadence:** distribution of days between consecutive surveys at the same beach, and surveys-per-beach. Beaches with 1–2 surveys cannot support lag features — decide the minimum-history cutoff and report how many beaches it drops.
- Produce 3–5 clean, labeled plots for the notebook and slides.

**Member C — leakage, pipeline scaffolding, notebook assembly**
- **Leakage audit, in writing.** For this project the prediction is *the next survey's total count using only information available before that survey*. Therefore:
  - The current survey's own litter-type breakdown **cannot** be a feature (it is recorded at the same moment as the target, and the type columns sum to the total — trivially leaky).
  - All composition/count features must be **lagged** to prior surveys at that beach.
  - Any column recorded after the survey (cleanup actions, post-hoc corrections, annual summaries) is out.
  - Running totals or per-beach means computed over the whole dataset leak future information into the training set — compute them from past surveys only.
- Define the **time-aware split** now, even though modeling is MS3: a global date cutoff (train on surveys before date *T*, test after), so no later survey predicts an earlier one. Note that per-beach repeated observations create dependence, and say how you'll handle it.
  - **Split on the actual survey date, never on the OSPAR year label.** Because an OSPAR year runs Dec–Oct, a split on the year column puts December surveys on the wrong side of the cutoff and leaks future information into training.
- Assemble `01_acquire_clean.ipynb` in the required order: group number + names → **Getting the data** (with size in MB) → **Understanding the data** (row meaning, column meanings, shape, dtypes, summary stats) → **Cleaning and preprocessing** (each step + why) → **Project question** (stated so it is checkable at the end).

**Revised proposal (1–2 pages) — rotating lead drafts Thu Nov 5, all edit by Sun Nov 8.** It must cover:
1. The revised question, and how/why it changed — or, if unchanged, what in the data shows it can be answered.
2. The data source with a link, and rows × columns **after cleaning**.
3. What you learned that changes the plan (missingness, dropped beaches, leaky columns).
4. The plan for the rest of the project: features, models, evaluation.
5. **If conditionally approved:** each staff condition taken in turn, with how you meet it.

A likely sharpening of the question, based on the proposal: *"For OSPAR-monitored beaches with at least N prior surveys, how accurately can the total litter count of the next 100 m survey be predicted from lagged counts, lagged composition, season, time since the previous survey, and location — relative to a previous-value baseline?"* Pin the N and the beach set from what you actually find.

---

## 4. Milestone 3 — EDA, Baseline, Pipeline (Nov 13 → Nov 30)

Goal: motivated EDA that *refines the project goals*, a baseline model as a benchmark, and a full proposed pipeline. Finish by **Tue Nov 24** — Thanksgiving is Nov 26.

### Week of Nov 16 – Nov 22
- **A — features:** build `src/features.py`. Lagged target (previous count, mean of previous *k*), lagged composition shares, days since previous survey, **OSPAR period (1–4)** and month/season, beach ID and country/region encodings, trailing beach-level statistics computed **from past surveys only**. Every feature documented with the timestamp of the information it uses.
- **B — EDA:** target distribution by beach, country, season, and year; trend over time; autocorrelation of counts within a beach — the preliminary answer is +0.22 within beach against +0.72 pooled (§4.1), so decompose between- and within-beach variance explicitly rather than reporting a single pooled number; seasonality; variance across beaches; relationships between candidate features and the target. Each figure must answer a question, not just exist — the spec asks for *well-motivated* EDA whose findings refine the goals.
- **C — pipeline + baselines:** 
  - Baselines, in the order they actually perform (see §4.1): **(i) beach historical median — the one to beat (MAE 602), (ii) global median (699), (iii) previous survey's count (821)** (modeling set: 197 beaches with >=8 surveys, 5,471 transitions). Report all three; the previous-value baseline is worth keeping precisely because it is the intuitive choice and it loses.
  - Time-aware CV harness: expanding-window splits by date, with the test fold always later than train.
  - Metrics: **MAE primary, R² secondary**, per the proposal; add RMSE and a baseline-relative skill score. If modeling `log1p(count)`, report errors back on the count scale.
  - A `sklearn` `Pipeline` with imputation → scaling → model, so preprocessing is fit on train folds only (this is itself a leakage guard).
- **All:** one real model beyond baseline (multiple linear regression) to validate the pipeline end to end.

### Week of Nov 23 – Nov 30
- **Mon Nov 23:** results consolidated; decide what the EDA changed about the plan.
- **Tue Nov 24:** slides done; dry run; rotating lead (A) assembles.
- **Deliverable framing:** EDA findings → refined goals → baseline numbers → the navigation plan for MS4 (which models, which features, what success looks like).
- **Present and submit by Sun Nov 29**, one day before the Mon Nov 30 deadline.

---

## 5. Milestone 4 — Final Modeling & Deliverables (Nov 30 → Dec 10)

68% of the grade, in ten days. The report and video are not afterthoughts — budget the last four days for them.

### Nov 30 – Dec 4: modeling
- **C:** Random Forest regression (per the proposal) with hyperparameter tuning inside the time-aware CV. Optionally one more model family for comparison (gradient boosting or regularized regression) — only if the pipeline is stable.
- **A:** final feature table frozen by **Wed Dec 2**. After that, no new features — the remaining time is for interpretation and writing.
- **B:** error analysis, which the proposal names as a secondary goal: *where* are errors largest, by beach and by season. Feature importances / coefficients, interpreted in context rather than just listed.
- **Fri Dec 4:** results frozen. Final numbers tabulated: every model × every metric, against the baselines.

### Dec 5 – Dec 9: deliverables
- **Report, 2000–2500 words** (B edits, all write). Suggested allocation: question and motivation (250) · data and cleaning (400) · EDA findings (400) · methods and pipeline (450) · results (500) · interpretation in context (300) · limitations (300). The limitations section should draw directly on the original proposal's concerns: OSPAR beaches are selected rather than randomly sampled so results apply to monitored sites only; cleaning, storms and protocol changes are unobserved confounders; repeated observations create dependence; the findings are predictive associations, not causal drivers, and are not operational cleanup recommendations.
- **Video, 6 minutes** — tight, so script it. Two minutes each. Record Mon Dec 7, leaving two days to re-record.
- **Notebook** — organized and commented. **C** does a from-scratch run on a clean kernel to confirm it executes top to bottom. 
- **`CITATIONS.md` folded into the notebook/report**, covering all generative-AI use and outside resources.
- **Wed Dec 9:** submit. One full day of buffer before the Dec 10 deadline.

---

## 6. Risk register

| Risk | Early signal | Mitigation |
|---|---|---|
| OSPAR export is item-level, not survey-level | Row count far exceeds plausible number of surveys | Settle the aggregation in week 1 of MS2; it changes everything downstream |
| Too few beaches with enough survey history for lags | Median surveys-per-beach is low | **Resolved** — the stacked panel gives a median of 17 surveys per beach, with 172 beaches at ≥8 (§4.1). Still set a minimum-history cutoff and report how many beaches it drops |
| Split leaks across the Dec–Oct OSPAR year boundary | Suspiciously strong test performance | Split on survey date, not the year column (see MS2 leakage audit) |
| Beaches tracked by name rather than ID | Duplicate or vanishing beaches after a rename | Key on the OSPAR beach ID; treat the name as a label only |
| Protocol or methodology changes across years | Step changes in counts by year in the EDA | **Largely resolved** — all 166 columns are common to all nine ODIMS years, so there is no cross-year schema drift. The old/new code overlap is a fixed within-file feature (see §4.1) |
| Model looks good but only learned beach identity | High pooled R², weak within-beach correlation | Report between- and within-beach performance separately; benchmark against the beach-median baseline, not the global one |
| Personal data in the portal export | `Email` and `Survey entered by` columns | Drop on load; correct the "non-personal" claim in the revised proposal; never commit the raw CSVs unstripped |
| Duplicate surveys where the sources overlap | Dec 2014 appears in both | Deduplicate on `Survey ID`, never on beach + date (see §4.1) |
| Step change in counts around 2010–2012 | Year medians jump then settle | Investigate in EDA; consider a regime indicator or restricting the window before reading any trend |
| Litter total double-counted | Totals roughly twice plausible values; suspiciously high model accuracy | Never sum all numeric columns. Choose the old-code or sub-code convention explicitly and apply it uniformly |
| Source portal unavailable near a deadline | Export 524s while ordinary pages also time out | Happened Nov 1. Do not chunk — chunking does not help a site-wide outage. Retry later; the ODIMS fallback (§4.1) is verified and downloadable |
| Leakage via composition columns | Suspiciously high R² on the first model | Leakage audit written in MS2; all composition features lagged |
| Target too skewed for MAE/R² to be informative | Long right tail, few huge counts | `log1p` target decided in MS2; report errors on the original scale |
| Deliverables compress into the final weekend | MS3 slipping past Nov 24 | Internal deadlines are 1–3 days early throughout; feature freeze Dec 2, results freeze Dec 4 |
| Uneven contribution | One stream consistently blocked at stand-up | Standing roles plus a rotating lead; equal speaking time is a grading requirement, not a courtesy |