# Data Cleaning Log — Power BI Star Schema Export

Source: `2_export_powerbi.py`. Covers the transformation from the two raw CSV
files (`Customer Flight Activity.csv`, `Customer Loyalty History.csv`) into
the two star-schema outputs (`dim_members.csv`, `fact_activity.csv`) used in
Power BI. Independent from the exploratory notebook
(`notebooks/1.EDA_clean.ipynb`), which is kept as EDA documentation only and
makes different, pandas-analysis-oriented choices (single merged file,
imputed salary, cancellation filled with 0) that were deliberately **not**
carried over here.

Row counts refer to the raw files as loaded: `Customer Flight Activity.csv` =
405,624 rows (grain: member-month, becomes `fact_activity`);
`Customer Loyalty History.csv` = 16,737 rows (grain: member, becomes
`dim_members`). Note this is the opposite of what was initially assumed in
the request — verified directly against the raw files before writing any
code.

---

## 1. Input file identity mismatch

- **Finding:** the row counts for the two raw files were stated backwards in
  the original request (16,737 attributed to the flight activity file,
  405,624 to the loyalty history file).
- **Options considered:** trust the stated counts vs. verify against the raw
  files.
- **Decision:** verified directly (`pd.read_csv(...).shape`) before writing
  any transformation code; used the confirmed grain (member-month for flight
  activity, member for loyalty history) throughout.
- **Justification:** building the star schema on the wrong grain assumption
  would have silently produced an invalid model (e.g. treating the fact
  table as the dimension).
- **Impact:** no rows affected; this only corrected which file plays which
  role in the schema.

## 2. Exact duplicate rows in flight activity

- **Finding:** 1,864 fully identical rows (all 10 columns match) in
  `Customer Flight Activity.csv`.
- **Options considered:** keep (would double-count flights/points for those
  member-months) vs. drop.
- **Decision:** dropped with `drop_duplicates()`.
- **Justification:** a fully identical row is by definition a load artifact,
  not a second real transaction — there is no information lost by keeping
  only one copy.
- **Impact:** 1,864 rows removed (0.46% of 405,624). No columns affected,
  no member lost entirely (every affected member still has other distinct
  rows).

## 3. Remaining duplicate keys (member, year, month) with differing values

- **Finding:** after removing the exact duplicates above, 2,066
  (member, year, month) groups — 4,138 rows, 135 distinct members — still
  shared a key but had **different** values across the columns (not load
  copies). Pattern: the same ~135 members had a second record in nearly every
  one of their 24 months, suggesting two parallel activity streams for those
  members rather than random corruption.
- **Options considered:** (a) sum the metrics per (member, year, month), (b)
  keep only the row with the higher activity and discard the other, (c)
  leave both rows and let those members exceed 24 rows/year in the fact
  table, (d) export separately for manual, case-by-case review.
- **Decision:** sum all numeric columns per (member, year, month) — option
  (a). Confirmed by the user after being shown 10 concrete examples.
- **Justification:** dropping either row would silently discard real
  activity; summing preserves the total flights/points/distance recorded for
  that member-month while restoring the required one-row-per-month grain.
  Verified post-aggregation that `total_flights = flights_booked +
  flights_with_companions` still holds for 100% of rows, and that every
  member ends up with exactly 24 rows — the script hard-stops (`SystemExit`)
  if either check fails on a future re-run with different data.
- **Impact:** 2,072 rows removed (4,138 rows collapsed into 2,066); grand
  totals for Total Flights and Distance are unchanged by construction (sum is
  conservative). The 135 affected members represent 1.51% of Total Flights
  and 1.54% of Distance in the final fact table. Flagged via
  `has_multiple_activity = TRUE` on those 135 members in `dim_members.csv`
  so they can be isolated/audited in Power BI.

## 4. Negative Salary values

- **Finding:** 20 negative salaries in `Customer Loyalty History.csv`
  (minimum -58,486), all otherwise plausible in magnitude.
- **Options considered:** treat as null vs. take absolute value vs. leave
  as-is.
- **Decision:** replaced with their absolute value.
- **Justification:** magnitudes are consistent with the rest of the salary
  distribution (mean ~79k, max ~407k) — this looks like a sign-capture error,
  not a fabricated or out-of-range value, so recovering the value is more
  informative than nulling it out.
- **Impact:** 20 rows changed (0.12% of 16,737). No rows removed.

## 5. Null Salary values

- **Finding:** 4,238 null salaries (25.3%), matching **exactly** — in both
  directions — the 4,238 members with `Education = "College"`. No non-College
  member has a null salary, and no College member has a non-null one.
- **Options considered:** impute with group mean (the notebook's approach)
  vs. leave null.
- **Decision:** left null; added a boolean `salary_reported` flag.
- **Justification:** the perfect correspondence with `Education = "College"`
  indicates a systematic capture gap or business rule, not missing-at-random
  data — imputing would fabricate values for a quarter of the member base and
  hide a pattern that is itself a business finding worth analyzing in Power
  BI (e.g. via `salary_reported` and `has_multiple_activity`-style flags).
- **Impact:** 4,238 rows keep `salary` blank; `salary_reported = FALSE` for
  all of them, `TRUE` for the remaining 12,499 (74.7%).

## 6. Cancellation Year / Month nulls

- **Finding:** 14,670 members (87.65%) have no cancellation year/month —
  they are still active.
- **Options considered:** fill with 0 (the notebook's approach, which
  produces an invalid year-0 date) vs. leave the derived date null.
- **Decision:** `cancellation_date` left null (`NaT` → empty cell in the
  CSV) for active members; added a separate `is_active` boolean instead of
  overloading the date field.
- **Justification:** a year-0 date breaks Power BI's calendar-table
  relationships and date hierarchies; a null date with an explicit boolean is
  the standard modeling pattern for "not yet occurred" events in a star
  schema.
- **Impact:** 14,670 rows have `cancellation_date` blank and
  `is_active = TRUE`; 2,067 rows have a populated `cancellation_date` and
  `is_active = FALSE`.

## 7. Enrollment Type normalization

- **Finding:** `Enrollment Type` contains `"Standard"` (15,766 rows) and
  `"2018 Promotion"` (971 rows).
- **Decision:** `"2018 Promotion"` renamed to `"Promotion"`.
- **Justification:** the year is redundant with `enrollment_date` /
  `enrollment_cohort` and makes the category harder to reuse if a future
  promotion cohort is added; a plain `"Promotion"` label is stable regardless
  of which year it happened.
- **Impact:** 971 rows relabeled (5.8% of 16,737). No rows removed.

## 8. Points Accumulated rounding

- **Finding:** `Points Accumulated` in flight activity is a float with
  fractional values (e.g. 230.04, 143.64).
- **Decision:** rounded to the nearest integer, applied **after** the
  duplicate-key summation in item 3 (so the rounding reflects the final
  consolidated monthly total, not the pre-aggregation fragments).
- **Justification:** carried over from the notebook's reasoning — points are
  redeemed as whole numbers elsewhere in the data, so fractional accumulation
  is very likely a display/precision artifact rather than a meaningful
  decimal.
- **Impact:** all 401,688 output rows affected in representation; no row
  changes value by more than 0.5 points.

## 9. Cancellation-before-enrollment validation

- **Finding:** checked whether any member has `cancellation_date` earlier
  than `enrollment_date`. Result: **zero** such cases in this dataset.
- **Decision:** implemented as a hard validation gate — any such row would be
  excluded from `dim_members.csv` and written to `member_anomalies.csv`
  instead, rather than silently kept or silently dropped.
- **Justification:** a cancellation before enrollment is logically
  impossible and would indicate a data error that should be surfaced, not
  guessed at.
- **Impact:** 0 rows affected today. This is a standing guardrail for future
  data refreshes, not a correction applied to the current file — see item 14
  below for what now happens to `fact_activity.csv` if this ever triggers.

## 10. Two separate files instead of one merged table

- **Decision:** exported `dim_members.csv` and `fact_activity.csv`
  separately, joined only by `loyalty_number`, instead of the notebook's
  single left-merged table.
- **Justification:** a star schema in Power BI needs the dimension and fact
  tables kept apart so relationships, calendar tables and DAX measures work
  correctly; a pre-merged table would duplicate every member attribute 24×
  (once per month) and break standard distinct-count/average member-level
  measures.
- **Impact:** structural, not row-level — `dim_members.csv` has 16,737 rows,
  `fact_activity.csv` has 401,688 rows, joined 1-to-many.

## 11. Zero-flight rows kept

- **Decision:** all 195,177 rows (48.6% of the final 401,688) where
  `total_flights = 0` were kept.
- **Justification:** these represent genuine inactive months, needed to
  compute dormancy and activation-rate measures in Power BI; removing them
  would make every member look active only in the months they flew.
- **Impact:** no rows removed by this decision (informational — confirms a
  requirement rather than describing a change).

## 12. Output formatting choices

- **Decision:** UTF-8 without BOM, comma separator, `.` decimal, ISO dates
  (`YYYY-MM-DD`), booleans as literal `TRUE`/`FALSE` strings, blank cells for
  nulls (not `"NaN"`/`"NULL"`), `\n` line endings (source files use CRLF; the
  output does not preserve this).
- **Justification:** removes locale ambiguity so Power BI's importer detects
  dates and booleans correctly regardless of the machine's regional settings.
- **Impact:** formatting only, no data values affected.

## 13. Postal code format validation (flagged, not corrected)

- **Finding:** an initial quick check (generic "letter in position 3/6"
  regex) found only 477 non-conforming rows. Re-checked against the actual
  Canada Post rule the user specified — Letter-Digit-Letter Digit-Letter-
  Digit, with `D, F, I, O, Q, U` excluded from every letter position and
  `W, Z` additionally excluded from the first letter — and the real count is
  **2,646 rows (15.81% of `dim_members`)**, roughly 5.5x the initial estimate.
  Breakdown:
  - **9 distinct invalid codes**, each tied to exactly one city, and each
    code covers **100% of that city's invalid rows** (Banff → `T4V 1D4`
    [179], Dawson Creek → `U5I 4F1` [444], Kelowna → `V09 2E9` [88],
    Montreal → `H3J 5I6` [7], Ottawa → `K1F 2R2` [389], Peace River →
    `T9O 2W2` [113], Toronto → `M2P 4F6` [126], Vancouver → `V6E 3D9` [911],
    Victoria → `V10 6T5` [389]).
  - **Province concentration:** British Columbia 1,832, Ontario 515, Alberta
    292, Quebec 7 — spread across 4 provinces, weighted toward BC only
    because BC has 3 of the 9 affected cities (including the largest,
    Vancouver). Not evidence of a province-specific capture problem.
  - **Enrollment cohort concentration:** the invalid-row rate is flat at
    14.8%–16.4% for every enrollment year from 2012 through 2018. It does
    **not** date the capture problem to one intake period — it has been
    present at a constant rate for the program's entire history.
- **Options considered:** correct the codes vs. drop the affected rows vs.
  flag with a boolean and leave the value untouched.
- **Decision:** flagged, not corrected. Added `postal_code_valid` (boolean)
  to `dim_members.csv`; the original `postal_code` value is left exactly as
  in the source.
- **Justification:** the 100%-single-code-per-city pattern, repeated
  identically across 9 unrelated cities and stable across 7 enrollment
  cohorts, is the same signature as the Salary/College pattern in item 5: a
  fixed placeholder value substituted whenever the real postal code wasn't
  captured, not transcription noise (transcription errors would produce many
  distinct near-miss values per city, not one exact repeated value). There is
  no reliable source to reconstruct the real postal code, so correcting it
  would fabricate location data; dropping the rows would discard otherwise
  valid members. Flagging preserves the value for the map visual while
  making the quality gap explicit and filterable.
- **Impact:** 2,646 rows get `postal_code_valid = FALSE`; the remaining
  14,091 (84.19%) get `TRUE`. No rows removed, no values altered.

## 14. Referential integrity cascade from dim_members to fact_activity

- **Finding:** the anomaly filter in item 9 removes members from
  `dim_members.csv` but, as originally written, did not remove their rows
  from `fact_activity.csv` — a future data refresh that actually triggers
  that anomaly would leave orphaned `loyalty_number` foreign keys in the fact
  table with no matching dimension row, breaking the star schema relationship
  in Power BI.
- **Options considered:** leave fact_activity untouched and only report the
  mismatch (the original behavior) vs. cascade the exclusion into
  fact_activity automatically.
- **Decision:** added a reusable `cascade_exclude_members()` function, called
  after the `dim_members` anomaly filter and before writing either output
  file. Any fact row whose `loyalty_number` was excluded from `dim_members`
  is removed and written to `orphan_activity.csv` (not silently dropped).
  Referential integrity is then re-verified with a new
  `check_referential_integrity()` function that **raises `SystemExit`** if
  either direction fails, run strictly after the cascade rather than before
  it, and strictly before the final CSVs are written.
- **Justification:** a star schema must guarantee every fact row resolves to
  a dimension row; reporting the mismatch after export is too late — Power
  BI would already have a broken relationship. Keeping the orphaned rows in a
  separate file (rather than deleting them) preserves the same
  no-silent-data-loss principle used for `member_anomalies.csv` elsewhere in
  this pipeline. Making it a function (not inline code) means it applies
  identically on every future refresh, not just today's zero-anomaly case.
- **Impact:** 0 rows affected in the current data (0 anomalies to cascade).
  Verified the mechanism itself works correctly using synthetic test data
  covering three cases: (1) normal cascade removes the correct rows and
  writes them to the orphan file, (2) a member with fact rows but no
  matching dimension row correctly raises `SystemExit`, (3) a dimension
  member with zero or incomplete fact rows correctly raises `SystemExit`.
  This is a standing guardrail, not a correction applied to the current file.

## 15. Referential integrity — bidirectional check

- **Finding:** the original integrity check only verified one direction
  (every `loyalty_number` in `fact_activity` exists in `dim_members`). This
  is the direction most likely to be violated loudly (an orphaned row is easy
  to spot), but it says nothing about a member silently losing activity rows
  upstream without ever producing an orphan.
- **Decision:** `check_referential_integrity()` now asserts **both**
  directions: (1) no orphans in `fact_activity`, and (2) every member in
  `dim_members` has exactly `EXPECTED_MONTHS_PER_MEMBER` (24) rows in
  `fact_activity` — including members with zero fact rows at all, which
  would not otherwise appear as "incomplete" in a naive row-count groupby.
  The check runs after the cascade in item 14, and raises `SystemExit`
  (rather than printing a warning) if either direction fails.
- **Justification:** direction 2 is the weaker guarantee and the one most
  likely to break silently, per direct request — a bug that filters
  fact_activity rows for one member (e.g. an off-by-one in a future date
  filter) would pass direction 1 undetected, since a missing row is not an
  orphaned row.
- **Impact:** confirmed on the current data: all 16,737 members in
  `dim_members.csv` have exactly 24 rows in `fact_activity.csv`, and every
  `loyalty_number` in `fact_activity.csv` exists in `dim_members.csv`. No
  rows affected — this hardens an existing check rather than changing data.

---

## Documented only — no change made

Per explicit decision, these two items are recorded for the data quality page
but were **not** implemented in `2_export_powerbi.py`.

1. **Enrollment/cancellation day defaults to the 1st of the month.** The
   source only provides year and month, so both derived dates
   (`enrollment_date`, `cancellation_date`) use `day=1`. This is invisible in
   aggregate reporting but means any "days since enrollment" or
   exact-duration measure built directly on these dates in Power BI would
   carry an average bias of about 15 days. **The fix belongs in Power BI, not
   in this export**: the raw data has no day-level precision, so inventing
   one would fabricate precision that doesn't exist and would be worse than
   the bias itself. `months_to_cancellation` is the column that already
   carries the correct grain — any tenure or duration measure should be built
   from it (or from `enrollment_cohort`), not from a day-level subtraction of
   `cancellation_date` − `enrollment_date`.
2. **CLV, Gender, Marital Status, Loyalty Card, Education were checked and
   found clean** — no negative/zero CLV, no unexpected categories (Gender:
   Male/Female; Marital Status: Married/Single/Divorced; Loyalty Card:
   Star/Nova/Aurora; Education: 5 expected levels), no cross-column
   inconsistency between `Distance`/`Total Flights` or between
   `Points Redeemed`/`Dollar Cost Points Redeemed`. Logged here as a
   confirmation rather than a change, so this log serves as evidence these
   were checked, not skipped.
