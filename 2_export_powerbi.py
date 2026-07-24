"""
Cleans the raw loyalty-program CSV files and exports a star schema
(dim_members + fact_activity) ready for Power BI.

Independent from the EDA in notebooks/1.EDA_clean.ipynb: this starts from the
raw CSV files (not the merged dataframe used in the notebook) and produces two
separate files instead of a single merged one.
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------
# Path configuration
# --------------------------------------------------------------------------
RAW_DIR = Path("data/Raw")
OUT_DIR = Path("data/Processed")

FLIGHT_ACTIVITY_FILE = RAW_DIR / "Customer Flight Activity.csv"   # grain: member-month -> fact
LOYALTY_HISTORY_FILE = RAW_DIR / "Customer Loyalty History.csv"   # grain: member -> dim

DIM_OUT_FILE = OUT_DIR / "dim_members.csv"
FACT_OUT_FILE = OUT_DIR / "fact_activity.csv"
ANOMALIES_OUT_FILE = OUT_DIR / "member_anomalies.csv"

EXPECTED_MONTHS_PER_MEMBER = 24

ORPHAN_ACTIVITY_OUT_FILE = OUT_DIR / "orphan_activity.csv"

# Canadian postal code: Letter-Digit-Letter Digit-Letter-Digit. D, F, I, O, Q, U
# are never used in any position; W and Z are additionally excluded from the
# first position only.
_POSTAL_FIRST_LETTER = "ABCEGHJKLMNPRSTVXY"
_POSTAL_OTHER_LETTER = "ABCEGHJKLMNPRSTVWXYZ"
CANADIAN_POSTAL_CODE_PATTERN = re.compile(
    rf"^[{_POSTAL_FIRST_LETTER}]\d[{_POSTAL_OTHER_LETTER}] \d[{_POSTAL_OTHER_LETTER}]\d$"
)


def to_snake_case(column_name: str) -> str:
    text = unicodedata.normalize("NFKD", column_name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_")
    return text.lower()


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n", na_rep="")


def format_bool_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        df[col] = df[col].map({True: "TRUE", False: "FALSE"})
    return df


def format_date_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    return df


def cascade_exclude_members(fact_df: pd.DataFrame, excluded_ids: set, orphan_path: Path) -> tuple[pd.DataFrame, int]:
    """Remove every fact row belonging to a member excluded from the dimension.

    Members can only be removed from dim_members via a validated anomaly (see
    the cancellation-before-enrollment check). Silently keeping their fact
    rows would leave foreign keys in fact_activity pointing at a member that
    no longer exists, breaking the star schema in Power BI. Removed rows are
    written to orphan_path rather than discarded, so nothing disappears
    without a trace.
    """
    if not excluded_ids:
        return fact_df, 0

    orphan_mask = fact_df["loyalty_number"].isin(excluded_ids)
    orphans = fact_df.loc[orphan_mask].copy()
    fact_clean = fact_df.loc[~orphan_mask].reset_index(drop=True)

    if len(orphans):
        orphans_out = orphans.copy()
        orphans_out = format_date_columns(orphans_out, ["date_key"])
        write_csv(orphans_out, orphan_path)

    return fact_clean, len(orphans)


def check_referential_integrity(fact_df: pd.DataFrame, dim_df: pd.DataFrame, expected_months_per_member: int) -> None:
    """Assert the star schema relationship holds in both directions.

    Direction 1 (every fact row has a home): every loyalty_number in fact_df
    exists in dim_df. Direction 2 (every dimension row has its full history):
    every loyalty_number in dim_df has exactly expected_months_per_member
    rows in fact_df. The second direction is the weaker guarantee - a member
    can silently lose rows (e.g. via an upstream filter bug) without ever
    producing an orphan, so it must be checked explicitly rather than assumed
    from direction 1 alone. Raises SystemExit on failure so a broken schema
    never gets exported.
    """
    fact_ids = set(fact_df["loyalty_number"].unique())
    dim_ids = set(dim_df["loyalty_number"].unique())

    orphans_in_fact = fact_ids - dim_ids
    if orphans_in_fact:
        raise SystemExit(
            f"Referential integrity FAILED: {len(orphans_in_fact)} loyalty_number values in "
            f"fact_activity do not exist in dim_members: {sorted(orphans_in_fact)[:20]}"
        )

    rows_per_member = fact_df.groupby("loyalty_number").size()
    incomplete_members = rows_per_member[rows_per_member != expected_months_per_member]
    members_with_no_rows = dim_ids - fact_ids
    if len(incomplete_members) or members_with_no_rows:
        raise SystemExit(
            f"Referential integrity FAILED: {len(incomplete_members)} members do not have exactly "
            f"{expected_months_per_member} activity rows and {len(members_with_no_rows)} members have "
            f"zero activity rows.\n{incomplete_members}"
        )

    print(
        f"OK: every loyalty_number in fact_activity exists in dim_members, AND every one of the "
        f"{len(dim_ids)} members in dim_members has exactly {expected_months_per_member} activity rows."
    )


# --------------------------------------------------------------------------
# 1. Load
# --------------------------------------------------------------------------
print("=" * 70)
print("LOADING RAW FILES")
print("=" * 70)

flights_raw = pd.read_csv(FLIGHT_ACTIVITY_FILE, encoding="utf-8-sig")
loyalty_raw = pd.read_csv(LOYALTY_HISTORY_FILE, encoding="utf-8-sig")

flights_raw.columns = [to_snake_case(c) for c in flights_raw.columns]
loyalty_raw.columns = [to_snake_case(c) for c in loyalty_raw.columns]

n_flights_in = len(flights_raw)
n_loyalty_in = len(loyalty_raw)
print(f"Customer Flight Activity.csv (fact): {n_flights_in} rows")
print(f"Customer Loyalty History.csv (dim):  {n_loyalty_in} rows")


# ==========================================================================
# 2. FACT_ACTIVITY — processed first because dim_members needs to know which
#    members were affected by the duplicate-key aggregation.
# ==========================================================================
print("\n" + "=" * 70)
print("FACT_ACTIVITY")
print("=" * 70)

fact = flights_raw.copy()
key_cols = ["loyalty_number", "year", "month"]

# --- 2.1 Exact duplicates (full identical row): load duplicates ---
n_exact_dupes = fact.duplicated().sum()
fact = fact.drop_duplicates().reset_index(drop=True)
print(f"Exact duplicate rows removed: {n_exact_dupes}")

# --- 2.2 Duplicate keys (member, year, month) with differing values ---
# After removing exact duplicates, any group that still shares a key must
# differ in at least one non-key value (identical rows would already have
# been collapsed in the previous step). User decision: sum the metrics rather
# than keep a single row, since the pattern (the same ~135 members repeating
# a double record in almost every one of their months) points to two parallel
# activity streams rather than load corruption.
dup_key_mask = fact.duplicated(subset=key_cols, keep=False)
affected_loyalty_numbers = set(fact.loc[dup_key_mask, "loyalty_number"].unique())
n_affected_groups = fact.loc[dup_key_mask].groupby(key_cols).ngroups
n_affected_rows = int(dup_key_mask.sum())

print(f"Groups (member, year, month) with a duplicate key and differing values: {n_affected_groups}")
print(f"Rows involved in those groups: {n_affected_rows}")
print(f"Members affected: {len(affected_loyalty_numbers)}")

before_flights_affected = fact.loc[fact["loyalty_number"].isin(affected_loyalty_numbers), "total_flights"].sum()
before_distance_affected = fact.loc[fact["loyalty_number"].isin(affected_loyalty_numbers), "distance"].sum()

fact = fact.groupby(key_cols, as_index=False).sum(numeric_only=True)

after_flights_affected = fact.loc[fact["loyalty_number"].isin(affected_loyalty_numbers), "total_flights"].sum()
after_distance_affected = fact.loc[fact["loyalty_number"].isin(affected_loyalty_numbers), "distance"].sum()

grand_total_flights = fact["total_flights"].sum()
grand_total_distance = fact["distance"].sum()

print("\nImpact of the aggregation (affected members only):")
print(f"  Total Flights  before: {before_flights_affected}  after: {after_flights_affected}")
print(f"  Distance       before: {before_distance_affected}  after: {after_distance_affected}")
print(f"  The {len(affected_loyalty_numbers)} affected members represent "
      f"{after_flights_affected / grand_total_flights * 100:.2f}% of Total Flights "
      f"and {after_distance_affected / grand_total_distance * 100:.2f}% of Distance in the final fact table.")

# --- 2.3 Validation: Total Flights = Booked + Companions after aggregation ---
formula_ok = (fact["total_flights"] == fact["flights_booked"] + fact["flights_with_companions"])
if not formula_ok.all():
    bad = fact.loc[~formula_ok]
    print(f"\nWARNING! After aggregation, total_flights = flights_booked + "
          f"flights_with_companions fails on {len(bad)} rows. Stopping before export:")
    print(bad)
    raise SystemExit("Fix required before continuing: flight formula violated after aggregating duplicates.")
else:
    print("\nValidation OK: total_flights = flights_booked + flights_with_companions holds for 100% of rows after aggregation.")

# --- 2.4 Validation: every member must have exactly 24 records ---
rows_per_member = fact.groupby("loyalty_number").size()
bad_counts = rows_per_member[rows_per_member != EXPECTED_MONTHS_PER_MEMBER]
if len(bad_counts) > 0:
    print(f"\nWARNING! {len(bad_counts)} members do not have exactly "
          f"{EXPECTED_MONTHS_PER_MEMBER} records after cleaning:")
    print(bad_counts)
else:
    print(f"Validation OK: all {fact['loyalty_number'].nunique()} members have exactly "
          f"{EXPECTED_MONTHS_PER_MEMBER} records each.")

# --- 2.5 date_key, points rounding, column cleanup ---
fact["date_key"] = pd.to_datetime(dict(year=fact["year"], month=fact["month"], day=1))
fact["points_accumulated"] = fact["points_accumulated"].round(0).astype(int)
fact = fact.drop(columns=["year", "month"])

n_zero_flight_rows = (fact["total_flights"] == 0).sum()
print(f"\nRows with total_flights = 0 (inactive months, kept): {n_zero_flight_rows}")

fact = fact[[
    "loyalty_number", "date_key", "flights_booked", "flights_with_companions",
    "total_flights", "distance", "points_accumulated", "points_redeemed",
    "dollar_cost_points_redeemed",
]]

print(f"\nfact_activity rows after deduplication: {n_flights_in} -> {len(fact)} "
      f"(removed as exact duplicates: {n_exact_dupes}; "
      f"rows consolidated by duplicate-key aggregation: {n_affected_rows - n_affected_groups}). "
      f"This total does not yet reflect the referential-integrity cascade in section 4.")


# ==========================================================================
# 3. DIM_MEMBERS
# ==========================================================================
print("\n" + "=" * 70)
print("DIM_MEMBERS")
print("=" * 70)

dim = loyalty_raw.copy()

# --- 3.1 Salary: negatives -> absolute value (reported), nulls kept as-is ---
neg_salary_mask = dim["salary"] < 0
n_neg_salary = int(neg_salary_mask.sum())
if n_neg_salary:
    print(f"Negative salaries corrected to absolute value: {n_neg_salary}")
    print(dim.loc[neg_salary_mask, ["loyalty_number", "salary"]])
    dim.loc[neg_salary_mask, "salary"] = dim.loc[neg_salary_mask, "salary"].abs()

dim["salary_reported"] = dim["salary"].notna()
n_salary_null = int(dim["salary"].isna().sum())
print(f"Null salaries (kept as null, not imputed): {n_salary_null}")

# --- 3.2 Enrollment and cancellation dates ---
dim["enrollment_date"] = pd.to_datetime(dict(
    year=dim["enrollment_year"], month=dim["enrollment_month"], day=1
))

has_cancellation = dim["cancellation_year"].notna()
dim["cancellation_date"] = pd.NaT
dim.loc[has_cancellation, "cancellation_date"] = pd.to_datetime(dict(
    year=dim.loc[has_cancellation, "cancellation_year"],
    month=dim.loc[has_cancellation, "cancellation_month"],
    day=1,
))

# --- 3.3 Anomaly: cancellation before enrollment -> excluded from final file ---
anomaly_mask = dim["cancellation_date"].notna() & (dim["cancellation_date"] < dim["enrollment_date"])
n_anomalies = int(anomaly_mask.sum())
anomalies = dim.loc[anomaly_mask].copy()
if n_anomalies:
    print(f"\nWARNING! {n_anomalies} members have a cancellation date before their enrollment date. "
          f"Excluded from the final file and saved to {ANOMALIES_OUT_FILE.name}:")
    print(anomalies[["loyalty_number", "enrollment_date", "cancellation_date"]])
else:
    print("\nValidation OK: no cancellation date is earlier than the enrollment date.")

excluded_loyalty_numbers = set(anomalies["loyalty_number"].unique())
dim = dim.loc[~anomaly_mask].reset_index(drop=True)

# --- 3.4 Postal code format validation (flagged, not corrected) ---
dim["postal_code_valid"] = dim["postal_code"].str.match(CANADIAN_POSTAL_CODE_PATTERN)
n_invalid_postal = int((~dim["postal_code_valid"]).sum())
print(f"\nPostal codes failing the Canadian format (Letter-Digit-Letter Digit-Letter-Digit, "
      f"excluding D/F/I/O/Q/U in any position and W/Z as first letter): "
      f"{n_invalid_postal} ({n_invalid_postal / len(dim) * 100:.2f}%)")
if n_invalid_postal:
    invalid_postal = dim.loc[~dim["postal_code_valid"]]
    per_city = invalid_postal.groupby("city")["postal_code"].agg(distinct_codes="nunique", members="count")
    print("Per affected city (distinct invalid codes and member count):")
    print(per_city)
    print("Provinces of invalid rows:")
    print(invalid_postal["province"].value_counts())

# --- 3.5 Remaining derived columns ---
dim["is_active"] = dim["cancellation_date"].isna()

dim["enrollment_type"] = dim["enrollment_type"].replace({"2018 Promotion": "Promotion"})

dim["enrollment_cohort"] = dim["enrollment_date"].dt.strftime("%Y-%m")

months_diff = (
    (dim["cancellation_date"].dt.year - dim["enrollment_date"].dt.year) * 12
    + (dim["cancellation_date"].dt.month - dim["enrollment_date"].dt.month)
)
dim["months_to_cancellation"] = months_diff.astype("Int64")

dim["has_multiple_activity"] = dim["loyalty_number"].isin(affected_loyalty_numbers)
n_multi_activity = int(dim["has_multiple_activity"].sum())
print(f"\nMembers flagged has_multiple_activity = TRUE: {n_multi_activity}")

# --- 3.6 Column cleanup ---
dim = dim.drop(columns=["enrollment_year", "enrollment_month", "cancellation_year", "cancellation_month"])

dim = dim[[
    "loyalty_number", "country", "province", "city", "postal_code", "postal_code_valid",
    "gender", "education", "salary", "salary_reported", "marital_status", "loyalty_card",
    "clv", "enrollment_type", "enrollment_date", "cancellation_date", "is_active",
    "enrollment_cohort", "months_to_cancellation", "has_multiple_activity",
]]

n_dim_out = len(dim)
print(f"\ndim_members rows: input {n_loyalty_in} -> output {n_dim_out} "
      f"(excluded due to date anomaly: {n_anomalies})")


# ==========================================================================
# 4. Referential integrity cascade fact -> dim
# ==========================================================================
# Members removed from dim_members (section 3.3) must not leave orphaned rows
# in fact_activity - without this cascade, those loyalty_number values would
# still be present in the fact table with no matching dimension row.
print("\n" + "=" * 70)
print("REFERENTIAL INTEGRITY CASCADE")
print("=" * 70)

fact, n_orphans_removed = cascade_exclude_members(fact, excluded_loyalty_numbers, ORPHAN_ACTIVITY_OUT_FILE)
if n_orphans_removed:
    print(f"Removed {n_orphans_removed} fact_activity rows belonging to the {len(excluded_loyalty_numbers)} "
          f"member(s) excluded via the date anomaly. Saved to {ORPHAN_ACTIVITY_OUT_FILE.name}.")
else:
    print("No members were excluded from dim_members, so no cascade was needed.")

check_referential_integrity(fact, dim, EXPECTED_MONTHS_PER_MEMBER)

n_fact_out = len(fact)


# ==========================================================================
# 5. Write final files
# ==========================================================================
fact_out = fact.copy()
fact_out = format_date_columns(fact_out, ["date_key"])
write_csv(fact_out, FACT_OUT_FILE)

dim_out = dim.copy()
dim_out = format_date_columns(dim_out, ["enrollment_date", "cancellation_date"])
dim_out = format_bool_columns(dim_out, ["postal_code_valid", "salary_reported", "is_active", "has_multiple_activity"])
write_csv(dim_out, DIM_OUT_FILE)

if n_anomalies:
    anomalies_out = anomalies.copy()
    anomalies_out = format_date_columns(anomalies_out, ["enrollment_date", "cancellation_date"])
    write_csv(anomalies_out, ANOMALIES_OUT_FILE)

print(f"\nFiles written to {OUT_DIR}/:")
print(f"  {DIM_OUT_FILE.name}  ({n_dim_out} rows)")
print(f"  {FACT_OUT_FILE.name} ({n_fact_out} rows)")
if n_anomalies:
    print(f"  {ANOMALIES_OUT_FILE.name} ({n_anomalies} rows)")
if n_orphans_removed:
    print(f"  {ORPHAN_ACTIVITY_OUT_FILE.name} ({n_orphans_removed} rows)")
