# PHASE 1: Exploration and Cleaning
## EDA
### 1.1. EDA: Initial Exploration. Customer Flight Activity
Flight data. Exploration function.

Numbers only.

Issue detection:

1. NULL VALUES: No nulls found.

2. OUTLIERS:
- 1,864 duplicates found.
- Why is 95.87% of Loyalty Numbers duplicated? Values repeat due to recurring trips. Records are monthly per traveler.
- Why does Loyalty Number reach 999,986 if total rows is 405,624? Are they consecutive? Is half the data missing?

### 1.2. EDA: Initial Exploration. Customer Loyalty History.
Personal data for loyalty program.

Issue detection:

1. NULL VALUES: Nulls present.

- Salary                25.32    How to impute?
    - Salary data was missing for customers with "College" education. Imputed as the mean between the upper value (Bachelor) and lower value (High School and below). "College" was overwritten with this mean.

- Cancellation Year     87.65    - Nulls in Cancellation because customers are still active. High null rate here is a positive signal.
- Cancellation Month    87.65    - Nulls in Cancellation because customers are still active. High null rate is positive.
    - Inactivity imputation for cancellation (active users): replaced with 0.
        - Encodes "cancellation has not yet occurred."
        - Allows NaN-to-0 conversion. Enables float-to-int casting, consistent with enrollment.

2. OUTLIERS:
- No duplicates found.

3. MISSING DATA:
- "College" missing from "Education" column.

### 1.3. CSV Merge

### 1.4. EDA: Initial Exploration — Merged Dataset

- "Points Accumulated":
        - Appears to be float due to a data entry error or because the airline awards decimal points — but can they actually be spent as decimals?
        - Truncate or round to remove decimals.
        - Cast float64 to int64, consistent with "Points Redeemed" (already-spent points are integers, typically in hundreds).


# PHASE 2: Visualization

1. How are booked flights distributed by month throughout the year?
2. Is there a relationship between flight distance and points accumulated by customers?
   - Two variables.
3. What is the distribution of customers by province or state?
4. How does average salary compare across different customer education levels?
5. What is the proportion of customers holding different loyalty card types?
6. How are customers distributed by marital status and gender?


NEXT STEPS:

RELATIONSHIP BETWEEN CLV AND LOYALTY CARD, SALARY — to analyze card type segmentation. Correlation matrix.