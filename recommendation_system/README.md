# Apriori Betting Recommendation System

Python implementation of the Apriori algorithm for discovering betting patterns and generating market recommendations from Polymarket data.

## Overview

Analyzes user betting patterns to discover which markets users bet on together and generate recommendations.

**Example Output:**
```
{trump-2024_YES, inflation-high_YES} → {recession-2024_YES}
Confidence: 67%, Lift: 2.3x, Support: 8%
```

## Installation

```bash
pip install psycopg[binary] pandas
```

**Files:**
- `apriori.py` - Apriori algorithm implementation
- `main.py` - CLI script to run the analysis and generate recommendations
- `config.json` - Optional configuration file for database connection and custom parameters

## Configuration

### Option 1: Environment Variable
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
```

### Option 2: Config File
Create `config.json`:
```json
{
  "connection": "postgresql://user:password@host:port/database",
  "mode": "trades",
  "min_items": 2,
  "days_back": 60,
  "min_support": 0.02,
  "min_confidence": 0.4,
  "min_lift": 1.3
}
```

### Required Tables
- `UserPosition`: `proxyWallet`, `size`, `endDate`, `slug`, `outcome`
- `UserTrade`: `proxyWallet`, `timestamp`, `slug`, `outcome`, `eventSlug`

## Usage

**Runs the complete workflow:**
- loads parameters
- connects to the database
- fetches transactions
- generates frequent itemsets
- generates association rules
- prints a summary
- exports rules to CSV
- enters interactive recommendation mode

**Default mode:**

This loads transactions, generates frequent itemsets, produces association rules, prints a summary, exports a CSV of rules, and optionally produces recommendations for selected users.

```bash
python main.py
```

**Command-line recommendation mode:**

Runs only the recommendation function for a single user (name, pseudonym, or wallet):

```bash
python main.py --user USERNAME
```

**Examples:**
```bash
python main.py --user completion
python main.py -u "0xfeb581080aee6dc26c264a647b30a9cd44d5a393"
python main.py -u somePseudonym
```

## Parameters

### Transaction Modes

| Mode | Description            |
|------|------------------------|
| `positions` | Current user holdings |
| `trades` | All markets traded |
| `sessions` | Markets traded same day |
| `events` | Markets in same event  |

### Algorithm Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_support` | 0.01    | Minimum pattern frequency (1-20%) |
| `min_confidence` | 0.30    | Minimum rule reliability (20-70%) |
| `min_lift` | 1.1     | Minimum correlation strength (1.0-3.0) |
| `min_items` | 3       | Minimum markets per user |
| `days_back` | 90      | Days of history (for trades/sessions/events) |

### Metrics Explained

- **Support**: Fraction of transactions containing an item set
- **Confidence**: Reliability of the rule (0-1). "X% of users with A also have B", P(A ∪ B) / P(A)
- **Lift**: Correlation strength. >1.0 = positive correlation, 2.0+ = strong, confidence divided by the baseline probability of the consequent
- **Conviction**: Rule independence measure. >2.0 = moderate, >5.0 = strong, (1 - P(B)) / (1 - confidence)

## Algorithm Overview

**The Apriori algorithm discovers frequent patterns through iterative steps:**

1. Find frequent 1-item_sets (individual markets with min support)
2. Generate candidate 2-item_sets from frequent 1-item_sets
3. Test candidates and keep frequent 2-item_sets
4. Repeat for k=3, 4, ... until no more frequent item_sets
5. Generate association rules from frequent item_sets
6. Filter rules by confidence and lift
7. Produce recommendations based on matched antecedents

**Key principle:** "If an item_sets is frequent, all subsets must be frequent"

## Project Structure

```
apriori.py
  ├─ fetch_user_transactions()
  ├─ generate_frequent_item_sets()
  ├─ generate_association_rules()
  ├─ get_recommendations()
  ├─ export_rules_to_dataframe()
  └─ print_summary()

main.py
config.json
README.md
```

## Parameter Optimizer

A parameter optimizer is available to automatically test combinations of support, confidence, lift, minimum items, and transaction modes.
It outputs a ranked table and exports results to a CSV file. It requires code modifications to use. It needs to be called with the PostreSQL connection as a parameter.

```
    conn_str = get_connection_string()
    conn = psycopg.connect(conn_str)

    best = optimize_apriori_parameters(conn)
    print("\nRecommended best parameters:")
    print(best)
```
