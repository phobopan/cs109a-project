# Revised Proposal — Predicting Beach Litter from Survey History

**CS109a Milestone 2 · Canvas project group _[35]_ · _[Cassidy Cheng], [Phoebe Pan], [Eli Su]_**

## 1. The project question

> For beaches in the OSPAR monitoring network with at least eight recorded surveys, can the
> total litter count of a beach's **next** standardized 100 m survey be predicted using only
> information available **before** that survey takes place, with a lower mean absolute error
> than the beach's own running median?

**The question itself has not changed.** The panel
holds 5,879 surveys of 247 beaches over 22.8 years, and 197 beaches have the eight-survey
history the lagged features need. However, we changed four details about the question and how we plan to process the data to answer it.

**First, the question is now stated against a more specific baseline.** The original offered "the previous count or
historical median" as alternatives, which are not all equivalent, so the chosen baseline of a running median is the most specific and representative we could find. 

**Second, our analysis is restricted to beaches with at least 8 surveys.** The original proposal did not say how much history a
beach needed. The distribution is skewed (median 17 surveys, but 22 beaches have fewer than
four), and a beach with two surveys cannot support a lagged feature. The threshold keeps 197
beaches, 5,668 surveys and 5,471 usable survey-to-survey transitions.

**Third, the secondary goal highlights where errors are largest.** Errors should
concentrate on high-count surveys, which are shown in our analysis to be the most unreliably measured overall. 

**We are careful to only use non-personal data, and drop the personal identifiers entirely.** It stated the data are
non-personal. The portal exports carry `Email` and `Survey entered by` which are surveyor names and
addresses. We drop both columns on load, and because a surveyor had left an email address
inside a free-text field, we also redact email patterns from every text column before the panel
is shared.

## 2. The data

OSPAR Beach Litter Monitoring, 100 m protocol, obtained from two OSPAR front ends serving one
database:

- Survey portal — <https://beachlitter.ospar.org/> — three CSV exports, 2001-01-01 to 2014-12-29
- ODIMS — <https://odims.ospar.org/> — nine annual `.xlsx` files, 2014-12-07 to 2023-10-31

The portal was down for two days and, once restored, timed out
on ranges beyond about five years, while ODIMS publishes only from 2015. The two sources share
December 2014, where **all 14 Survey IDs match exactly** which shows that the sources represent one database
rather than two.

**After cleaning: 5,879 rows by 171 columns.** One row is one survey of one beach on one date;
247 beaches, 13 countries, 7 regions. 116 columns are litter counts by type; the rest are
identifiers, location, date, period and survey metadata. Raw files total 4.5 MB.

Scope is the 100 m protocol only.  

## 3. What we learned from the data

**The intuitive baseline is the wrong one.** On the modeling set, predicting the previous
survey's value gives MAE 688; the beach's running median gives **535**; a single global median
gives 630. The original
proposal treated the previous count as the natural benchmark, which would have flattened any
model we built. We'll still report all three, but focus only on beating the running median value with our prediction.

**Most apparent predictability is between beaches, not within them.** The correlation between
previous and current log-total is +0.701 pooled, but only **+0.283 within beach**. A model can
score well simply by learning which beaches are dirty. We will report within-beach performance
as the honest measure of what the model adds.

**The largest counts are estimates, not counts.** 759 surveys have non-integer totals, and the
free-text notes explain why: where litter is too dense to count, surveyors measure narrow
transects and scale up. One note describes two 1 m transects averaged and recalculated to
100 m. The five largest surveys in the dataset are all one Swedish beach measured this way, and
the top 1% of surveys hold **31.2%** of all items recorded. The dataset's own
`Divert from the predetermined 100 metres?` flag does **not** capture this. 741 of the 759
fractional surveys are flagged "No", so we derive our own indicator from the fractional total.
This is the most consequential finding for modeling: the heaviest tail of the response is also
its least reliable part.

**There are two protocol changes, and only one is documented.** OSPAR expanded the litter code
list in 2015 (sub-codes that coexist with their parents and double-count if both are summed,
so we keep the original aggregate codes and exclude the 20 newer ones). It also expanded the
list in **2010**, as four codes are exactly zero through 2009 and non-zero from 2010 onward, the
same signature. This partly explains an otherwise puzzling spike in 2010–2012 medians that
survives restriction to beaches surveyed throughout. Consequence: **no train/test split may
straddle 2010 or 2015**, and calendar year is a confounded feature.

**Missingness is structural.** The litter counts are essentially complete (max 0.09% missing).
What is missing is free text and the 1 km coordinate columns (~45%), the latter because not
every 100 m site sits inside a 1 km site. That is structural absence and we do not impute it.
Coordinates are degree-minute-second strings with inconsistent separators and need parsing.

**Smaller items, each handled and documented in the notebook:** a `-99` sentinel that made one
total negative; `Period = -1` on 450 surveys (7.7%), a flag rather than a season; 21 zero-total
surveys that we keep, since six of the ten beaches involved record 1–3 items when non-zero; and
one duplicate record (`UK057`, 2023-09-23, identical in all 116 count columns under two Survey
IDs).

**Information leakage.** The current survey's litter breakdown *sums to the target*, so no count
column of the row being predicted can ever be a feature. Every feature is computed from strictly
earlier surveys of the same beach, and the running median is shifted so that a survey never
contributes to its own baseline.

## 4. Plan for the rest of the project

**Features** are all available before the survey: previous total and log-total (one and two lags);
the beach's expanding median to date; days since the previous survey; season (`Period` 1–4 with
a separate out-of-window flag); country and region; parsed latitude and longitude; and the
derived transect-estimate indicator.

**Our Target is** `log1p(total)`. Raw totals have skew 34.7; the log transform brings it to -0.13.

**Models:** the three baselines above, then multiple linear regression on the log target, then
Random Forest, as proposed. Linear regression will need standardized features given that
`days_since_prev` ranges 1–3,130 while log-total ranges 0–12.3.

**Evaluation:** a time-aware split by training through 2018 (3,227 transitions), validating 2019–2020 (841),
and testing 2021–2023 (1,403), which keeps both code-change boundaries inside the training period.
Primary metric MAE, chosen over RMSE because of the unreliable upper tail; R-squared secondary. We will
report MAE pooled and within-beach, and break errors down by beach, season and whether the
survey was transect-estimated.

**Limitations, revised.** The original limitations stand: monitored beaches are selected rather
than sampled, so results apply to the OSPAR network and not the Northeast Atlantic generally;
repeated observations create dependence; and we identify predictive associations, not causes. We
added two, first that protocol changes did occur in 2010 and 2015. And the response
is not measured consistently across its range, since its largest values are extrapolations.
