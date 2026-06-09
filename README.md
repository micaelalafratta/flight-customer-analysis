# Airline Loyalty Customer Analysis: End-to-end EDA project

Exploratory data analysis and visualisation of a Canadian airline's loyalty programme — profiling customer behaviour, flight activity, and programme engagement across 400K+ records.

---

## Project Structure

```
├── data/
│   ├── Clean/
│   │   └── Customer Flight Profile_clean.csv
│   └── Raw/
│       ├── Customer Flight Activity.csv
│       └── Customer Loyalty History.csv
├── notebooks/
│   ├── 1.EDA_clean.ipynb
│   └── 2.Viz.ipynb
├── outputs/
│   ├── figures/
│   │   ├── monthly_flight_activity.png
│   │   ├── distance_vs_points.png
│   │   └── loyalty_card_distribution.png
│   ├── 1.documentation_EDA.md
│   └── Airline_Loyalty_Analysis_Report.docx
├── src/
│   ├── colour_palettes_support.py
│   ├── EDA_support.py
│   └── soporte_correlacion.py
├── .gitignore
└── README.md
```

---

## Datasets

Two source datasets merged on `Loyalty Number`:

**Customer Flight Activity** — 405,624 rows · monthly flight records per customer. Variables include flights booked, distance, points accumulated, points redeemed, and dollar cost points redeemed.

**Customer Loyalty History** — customer profile data including province, country, education, marital status, gender, salary, loyalty card tier, enrollment type, enrollment year, and cancellation data.

---

## Phase 1: EDA & Data Cleaning (`1.EDA_clean.ipynb`)

### Exploration

- Initial inspection of both datasets independently: shape, dtypes, nulls, duplicates.
- The 95.87% duplicate rate on `Loyalty Number` in the flight dataset was expected — one row per customer per month of activity, not per customer.
- Datasets merged with a left join on `Loyalty Number`, preserving all flight activity records and adding profile columns. Result: 405,624 rows, combined column set.

### Cleaning decisions

**`Salary` nulls — segmented imputation:**
The `Education` column had no "College" category — salary values for College-level customers were null. Rather than imputing the global mean, the median between the adjacent education levels (High School or Below and Bachelor) was calculated and assigned to all College rows. This preserves the salary-education gradient visible in the data.

**`Cancellation Year` and `Cancellation Month` nulls:**
Null values represent active customers (no cancellation has occurred). Imputed with `0` and converted to `int` — encoding "cancellation has not happened yet" without losing the ability to filter or operate on the column.

**`Points Accumulated` type correction:**
Values were stored as floats despite representing whole loyalty points. Rounded to nearest integer and converted to `int` to match the logic of `Points Redeemed`, which was already integer.

---

## Phase 2: Visualisation & Descriptive Statistics (`2.Viz.ipynb`)

Six analytical questions explored on the cleaned dataset:

### 1. How are booked flights distributed across months?
**Line plot.** Clear seasonal pattern: peak in July–August (summer holidays), trough in January–February. Steady growth from March through the summer peak.

### 2. Is there a relationship between flight distance and points accumulated?
**Scatter plot (dual: by Loyalty Card and by Enrollment Type).** Strong positive correlation with low dispersion — points accumulation is directly tied to miles flown. Multiple diagonal lines reflect different accumulation rates by loyalty tier and enrollment type. The "2018 promotion" enrollment type accumulates points at a higher rate than standard enrollment.

### 3. How are customers distributed by province and country?
**Bar plot (province) + pie chart (country).** Ontario, British Columbia, and Quebec account for the majority of customers by a significant margin. All customers are Canadian — the country pie chart confirms a single-country dataset.

### 4. How does average salary compare across education levels?
**Bar plot + box plot.** Clear positive gradient: higher education correlates with higher salary. The largest salary gap is between Master's and Doctorate level — doctorate holders earn approximately double the lowest tier. The College category shows only a median line (no range) because it was imputed with a single value in Phase 1.

### 5. What is the proportion of customers by loyalty card type?
**Pie chart.** Nearly half of all customers hold the entry-level "Star" card. Understanding the distribution across tiers is relevant for assessing whether the programme's progression incentives are effective.

### 6. How are customers distributed by marital status and gender?
**Count plot.** Married customers are the largest segment, roughly double the single segment. Gender distribution is broadly even across marital status categories.

---

## Stack

`Python` `Pandas` `NumPy` `Matplotlib` `Seaborn`
