"""Load and merge the OSPAR 100 m beach litter surveys.

Two sources, same underlying database:

  * the survey portal (beachlitter.ospar.org), exported as CSV in five-year
    chunks, covering 2001-01-01 to 2014-12-29
  * ODIMS (odims.ospar.org), one .xlsx per OSPAR year, covering 2014-12-07
    to 2023-10-31

They overlap in December 2014 (14 surveys, identical Survey IDs in both), so
the merge deduplicates on ``Survey ID``.

See data/raw/SOURCE.md for how to obtain the raw files.

Typical use::

    from src.data import load_panel
    df = load_panel()            # 5,879 surveys x 247 beaches, 2001-2023

Works from a fresh clone: with no raw files present it reads the committed
``data/processed/panel.csv.gz`` instead.
"""

from __future__ import annotations

import glob
import os
import re

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")

# The cleaned panel, committed to the repository. The raw files are not (they
# are large and the portal CSVs carry personal data), so a fresh clone has this
# and nothing else. load_panel falls back to it, which means a teammate can
# clone and start work without downloading anything.
PROCESSED_PATH = os.path.join(DATA_DIR, "processed", "panel.csv.gz")

# Surveyor name and address. Present in the portal CSVs, absent from ODIMS.
# Dropped on load: we have no use for them and they are personal data.
PII_COLUMNS = ["Email", "Survey entered by"]

# Litter codes introduced in 2015 that subdivide an older code. They sum to
# exactly zero before 2015 and coexist with their parents afterwards, so
# including them alongside the parents double-counts. Excluded from the total.
SUBCODE_COLUMNS = [
    "Plastic: Food_plastic [610]", "Plastic: Food_eps [620]",
    "Plastic: Cups_plastic [211]", "Plastic: Cups_eps [212]",
    "Plastic: Fishboxes_plastic [341]", "Plastic: Fishboxes_eps [342]",
    "Plastic: Plastic_s [1171]", "Plastic: Eps_s [1172]",
    "Plastic: Plastic_m [461]", "Plastic: Eps_m [462]",
    "Plastic: Plastic_l [471]", "Plastic: Eps_l [472]",
    "Plastic: String_cord [321]", "Plastic: Dolly_rope [322]",
    "Plastic: Tangled_string [331]", "Plastic: Tangled_dolly_rope [332]",
    "San: Buds_plastic [981]", "San: Buds_cardboard [982]",
    "Plastic: Biofilm [481]", "Glass: Jars [931]",
]

# Free-text fields where a surveyor sometimes left contact details. At least
# one Divert specify note ends with a name and work email address, so emails
# are stripped from every text column before the panel is shared.
_EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.\w+")

# Every litter count column starts with one of these.
MATERIAL_PREFIXES = (
    "Plastic:", "Rubber:", "Cloth:", "Paper:", "Wood:", "Metal:",
    "Glass:", "Pottery:", "San:", "Med:", "Faeces:", "Pollutants:",
)

# Not counts, despite sitting among them: Pellets is Yes/No, Remarks is free
# text, and the Survey: Old_* items belong to a separate "old litter" protocol.
NON_COUNT_PREFIXES = ("Survey:",)


def count_columns(df: pd.DataFrame) -> list[str]:
    """The columns that make up the litter total, on the pre-2015 convention.

    Uses the original aggregate codes only, so the definition is consistent
    across the whole 2001-2023 panel.
    """
    return [
        c for c in df.columns
        if str(c).startswith(MATERIAL_PREFIXES)
        and not str(c).startswith(NON_COUNT_PREFIXES)
        and str(c) not in SUBCODE_COLUMNS
    ]


def redact_emails(df: pd.DataFrame) -> pd.DataFrame:
    """Replace email addresses in free-text columns with a placeholder.

    Dropping the ``Email`` column is not enough: surveyors occasionally left
    contact details inside ``Divert specify`` and ``Survey: Remarks``, which
    are otherwise worth keeping (one note records a 135 m survey stretch, a
    real data-quality signal). Names left in prose are not detectable by
    pattern and may remain, so skim those columns before quoting them.
    """
    df = df.copy()
    for column in df.columns:
        if df[column].dtype == object:
            df[column] = df[column].apply(
                lambda v: _EMAIL_RE.sub("[email removed]", v)
                if isinstance(v, str) else v
            )
    return df


def _read_portal(data_dir: str) -> pd.DataFrame:
    """Read the portal CSV chunks (2001-2014)."""
    paths = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not paths:
        return pd.DataFrame()
    frames = []
    for path in paths:
        frame = pd.read_csv(path, low_memory=False)
        frame["source"] = "portal"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _read_odims(data_dir: str) -> pd.DataFrame:
    """Read the ODIMS annual spreadsheets (2015-2023)."""
    paths = sorted(glob.glob(os.path.join(data_dir, "raw", "*.xlsx")))
    if not paths:
        return pd.DataFrame()
    frames = []
    for path in paths:
        frame = pd.read_excel(path, sheet_name=0, engine="openpyxl")
        # Unnamed spillover columns in the 2016, 2018, 2019 and 2021 files.
        frame = frame.loc[:, [c for c in frame.columns
                              if not str(c).startswith("Column")]]
        frame["source"] = "odims"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _read_processed(path: str) -> pd.DataFrame:
    """Read the committed panel, already merged, cleaned and redacted."""
    df = pd.read_csv(path, low_memory=False)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def load_panel(data_dir: str = DATA_DIR, min_surveys: int = 0,
               rebuild: bool = False) -> pd.DataFrame:
    """Return one row per survey, sorted by beach then date.

    Builds the panel from the raw files when they are present. When they are
    not — a fresh clone of the repository — falls back to the committed
    ``data/processed/panel.csv.gz``, which is byte-for-byte the same panel.

    Parameters
    ----------
    data_dir
        Directory holding the portal CSVs and a ``raw/`` subdirectory of
        ODIMS spreadsheets. Defaults to the project's ``data/``.
    min_surveys
        Drop beaches with fewer than this many surveys. Lagged features need
        history, so models will want something above 1; 0 keeps everything.
    rebuild
        Require a rebuild from the raw files, raising if they are missing
        instead of falling back to the committed panel.

    Added columns
    -------------
    ``date``    parsed ``Survey date`` (the raw field is day-first)
    ``total``   litter items, summed over :func:`count_columns`
    ``log_total``  ``log1p(total)``, the modelling target
    ``source``  ``"portal"`` or ``"odims"``
    """
    portal, odims = _read_portal(data_dir), _read_odims(data_dir)
    frames = [f for f in (portal, odims) if not f.empty]
    if not frames:
        processed = os.path.join(data_dir, "processed", "panel.csv.gz")
        if not rebuild and os.path.exists(processed):
            df = _read_processed(processed)
            if min_surveys > 1:
                keep = df.groupby("Beach ID")["Survey ID"].transform("size")
                df = df[keep >= min_surveys].reset_index(drop=True)
            return df
        raise FileNotFoundError(
            f"No survey files under {data_dir}, and no committed panel at "
            f"{processed}. See data/raw/SOURCE.md for how to obtain the raw files."
        )

    # Keep the columns every source has, minus the personal ones.
    shared = set(frames[0].columns)
    for frame in frames[1:]:
        shared &= set(frame.columns)
    columns = [c for c in frames[0].columns
               if c in shared and c not in PII_COLUMNS]
    df = pd.concat([f[columns] for f in frames], ignore_index=True)

    # December 2014 is in both sources with matching Survey IDs (14 surveys,
    # all 14 IDs present on both sides). Deduplicate on Survey ID first.
    df = df.drop_duplicates(subset=["Survey ID"], keep="first")

    df["date"] = pd.to_datetime(df["Survey date"], errors="coerce",
                                dayfirst=True)

    counts = count_columns(df)
    df[counts] = df[counts].apply(pd.to_numeric, errors="coerce")
    # One cell is -99, a missing-data sentinel (GRL003, 2020-07-31). Negative
    # litter counts are impossible, so treat any as missing.
    df[counts] = df[counts].mask(df[counts] < 0)

    # A distinct Survey ID is not sufficient on its own. UK057 on 2023-09-23
    # appears twice under IDs 22453 and 22454, identical in every one of the
    # 116 count columns -- a record entered twice, not two surveys. Drop exact
    # repeats of beach + date + counts, which leaves any genuine same-day pair
    # (differing counts) intact. Exactly one group matches in the full panel.
    df = df.drop_duplicates(subset=["Beach ID", "date"] + counts, keep="first")

    # Defragment after the wide column assignment, or pandas warns on each
    # derived column added below.
    df = df.copy()

    df["total"] = df[counts].sum(axis=1)
    df["log_total"] = np.log1p(df["total"])

    # Period -1 marks a survey taken outside the four standard windows
    # (~7% of rows). It is a flag, not a number, so keep it out of models
    # as an integer.
    df["in_standard_period"] = df["Period"].isin([1, 2, 3, 4])

    df = redact_emails(df)
    df = df.sort_values(["Beach ID", "date"]).reset_index(drop=True)

    if min_surveys > 1:
        keep = df.groupby("Beach ID")["Survey ID"].transform("size")
        df = df[keep >= min_surveys].reset_index(drop=True)

    return df


def add_lags(df: pd.DataFrame, lags: int = 1) -> pd.DataFrame:
    """Add previous-survey features, computed within each beach.

    Every feature here uses only surveys that happened *before* the row's own
    survey, which is what keeps the task honest: the current survey's own
    litter breakdown sums to the target and must never be a predictor.
    """
    df = df.sort_values(["Beach ID", "date"]).copy()
    by_beach = df.groupby("Beach ID")

    for lag in range(1, lags + 1):
        df[f"prev_total_{lag}"] = by_beach["total"].shift(lag)
        df[f"prev_log_total_{lag}"] = by_beach["log_total"].shift(lag)

    df["days_since_prev"] = by_beach["date"].diff().dt.days
    # Expanding median of earlier surveys only: shift(1) first so the current
    # survey never contributes to its own baseline.
    df["beach_median_to_date"] = (
        by_beach["total"].apply(lambda s: s.shift(1).expanding().median())
        .reset_index(level=0, drop=True)
    )
    return df
