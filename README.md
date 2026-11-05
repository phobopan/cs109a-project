# CS109a Final Project — OSPAR Beach Litter

Predicting the total litter count of a beach's **next** OSPAR survey from information
available **before** that survey, and testing whether it beats the beach's running median.

## Start here

```bash
pip install -r requirements.txt
jupyter lab
```

```python
from src.data import load_panel, add_lags, count_columns

df = load_panel()          # 5,879 surveys x 171 columns, 247 beaches, 2001-2023
lagged = add_lags(df)      # leak-free history features
```

**This works straight from a clone.** The raw downloads are not tracked (they are large,
and the portal exports contain personal data), so `load_panel()` falls back to the cleaned
panel committed at `data/processed/panel.csv.gz` — the identical table. To rebuild from the
original files instead, follow `data/raw/SOURCE.md` and call `load_panel(rebuild=True)`.

## Two things to know before you use the data

1. **Never sum the litter columns by hand.** 20 sub-code columns added in 2015 double-count
   their parent codes and are deliberately excluded from `total`. Use `count_columns(df)`.
2. **Never use a column from the row you are predicting.** The current survey's litter
   breakdown sums to the target. Every feature must come from strictly earlier surveys of
   the same beach; that is what `add_lags` does.

## Layout

| Path | What it is |
|---|---|
| `milestone2.ipynb` | The Milestone 2 deliverable. Runs top to bottom. |
| `REVISED_PROPOSAL.md` / `.pdf` | The revised proposal, 2 pages. |
| `src/data.py` | Loading, merging and cleaning. All cleaning rules live here. |
| `data/processed/panel.csv.gz` | The cleaned panel, PII-stripped. Tracked. |
| `data/raw/SOURCE.md` | Where every raw file came from, with export settings. |

## Data

OSPAR Beach Litter Monitoring, 100 m protocol, from two OSPAR front ends serving one
database: the [survey portal](https://beachlitter.ospar.org/) for 2001–2014 and
[ODIMS](https://odims.ospar.org/) for 2015–2023. They overlap in December 2014, where all
14 Survey IDs match — which is how we verified they are the same database.

**Do not commit raw portal exports.** They contain `Email` and `Survey entered by`.
