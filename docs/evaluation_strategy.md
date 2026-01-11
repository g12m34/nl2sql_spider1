# Evaluation Strategy: Execution-Based Accuracy

## Overview

For our NL2SQL with Malloy project, we use **execution-based evaluation** rather than SQL string matching. This is essential because Malloy compiles to SQL that looks different from the Spider ground truth SQL, but should produce identical results.

## Why Execution-Based Evaluation?

| Approach | Description | Problem for Malloy |
|----------|-------------|-------------------|
| **Exact Match** | Compare SQL strings character-by-character | Malloy SQL looks completely different |
| **Component Match** | Parse SQL and compare AST components | Requires parsing Malloy-generated SQL into Spider's format |
| **Execution Match** | Run both queries, compare results | Works regardless of SQL syntax |

**Our choice: Execution Match** - If two queries return the same results on the same database, they are semantically equivalent.

## Evaluation Logic

### Core Algorithm

```python
def eval_exec_match(db_path, predicted_sql, gold_sql):
    # 1. Execute both queries
    pred_results = execute(predicted_sql)
    gold_results = execute(gold_sql)

    # 2. Determine if row order matters
    order_matters = 'ORDER BY' in gold_sql.upper()

    # 3. Compare results with appropriate handling
    return result_eq(gold_results, pred_results, order_matters)
```

### Result Comparison Rules

1. **Row counts must match** - Different number of rows = no match
2. **Column counts must match** - Different number of columns = no match
3. **Column order can differ** - We try all column permutations
4. **Row order depends on ORDER BY**:
   - If gold has `ORDER BY`: row order must match exactly
   - If no `ORDER BY`: rows compared as multisets (order-independent)
5. **Duplicate rows preserved** - Multiset comparison counts duplicates
6. **Values normalized** - `1` == `1.0` == `"1"` for comparison

## Edge Cases Handled

### Column Order Permutation

Malloy might generate `SELECT age, name` while ground truth has `SELECT name, age`. Both are correct if they contain the same data.

```
Gold:      [(Alice, 30), (Bob, 25)]
Predicted: [(30, Alice), (25, Bob)]
Result:    MATCH (columns swapped but same data)
```

### Row Order (ORDER BY Detection)

```sql
-- Gold query WITHOUT ORDER BY
SELECT name FROM users

-- These all match (row order ignored):
SELECT name FROM users ORDER BY id
SELECT name FROM users ORDER BY name DESC
```

```sql
-- Gold query WITH ORDER BY
SELECT name FROM users ORDER BY age

-- Only matches if rows in same order
```

### Duplicate Rows

```
Gold:      [(1,), (1,), (2,)]
Predicted: [(1,), (2,), (1,)]
Result:    MATCH (same multiset: two 1s, one 2)

Gold:      [(1,), (1,), (2,)]
Predicted: [(1,), (2,), (2,)]
Result:    NO MATCH (different counts)
```

### Empty Results

```
Gold:      []
Predicted: []
Result:    MATCH

Gold:      []
Predicted: [(1,)]
Result:    NO MATCH
```

### NULL Values

```
Gold:      [(1, None), (2, 'b')]
Predicted: [(1, None), (2, 'b')]
Result:    MATCH

Gold:      [(1, None)]
Predicted: [(1, 'a')]
Result:    NO MATCH (NULL != 'a')
```

### Type Coercion

SQLite can return values as different types. We normalize:
- `1.0` → `1` (whole floats to int)
- `"42"` → `42` (numeric strings to numbers)

```
Gold:      [(1, 2)]
Predicted: [(1.0, "2")]
Result:    MATCH (after normalization)
```

## Test Suite

We implemented a comprehensive test suite (`scripts/test_evaluation.py`) with 47 tests across 10 categories:

### Test Categories

| Category | Tests | What It Validates |
|----------|-------|-------------------|
| Basic Functionality | 11 | `multiset_eq`, `normalize_value` functions |
| Column Order Permutation | 4 | Different column orderings match correctly |
| Row Order (ORDER BY) | 4 | ORDER BY detection and enforcement |
| Duplicate Rows | 3 | Multiset comparison preserves counts |
| Empty Results | 3 | Empty set handling |
| NULL Handling | 3 | NULL comparison semantics |
| Type Coercion | 2 | Int/float/string normalization |
| SQL Execution | 8 | Real query execution against SQLite |
| Column Permutation Edge Cases | 4 | Ambiguous permutations, many columns |
| 50/50 Spider Validation | 5 | Real Spider queries (50 correct + 50 broken) |

### Test Details

#### 1. Basic Functionality (11 tests)
```
✓ multiset_eq: identical lists
✓ multiset_eq: reordered lists
✓ multiset_eq: with duplicates same
✓ multiset_eq: with duplicates different
✓ multiset_eq: different lengths
✓ multiset_eq: empty lists
✓ normalize: float to int
✓ normalize: string number to int
✓ normalize: string float to number
✓ normalize: None stays None
✓ normalize: regular string unchanged
```

#### 2. Column Order Permutation (4 tests)
```
✓ column reorder: 3 columns swapped
✓ column reorder: 2 columns swapped
✓ column order: same order matches
✓ column reorder: different values don't match
```

#### 3. Row Order / ORDER BY (4 tests)
```
✓ row order: different order, order_matters=False
✓ row order: different order, order_matters=True
✓ row order: same order, order_matters=False
✓ row order: same order, order_matters=True
```

#### 4. Duplicate Rows (3 tests)
```
✓ duplicates: same count, different order
✓ duplicates: different counts should not match
✓ duplicates: all same values
```

#### 5. Empty Results (3 tests)
```
✓ empty: both empty
✓ empty: first empty, second not
✓ empty: first not empty, second empty
```

#### 6. NULL Handling (3 tests)
```
✓ NULL: same positions
✓ NULL: NULL vs value should not match
✓ NULL: multiple NULLs
```

#### 7. Type Coercion (2 tests)
```
✓ type: int vs float (whole)
✓ type: int vs string number
```

#### 8. SQL Execution (8 tests)
```
✓ SQL exec: identical queries
✓ SQL exec: column order swap
✓ SQL exec: row order differs, no ORDER BY in gold
✓ SQL exec: different ORDER BY should not match
✓ SQL exec: aggregate COUNT
✓ SQL exec: wrong WHERE clause
✓ SQL exec: syntax error returns False
✓ SQL exec: syntax error has error message
```

#### 9. Column Permutation Edge Cases (4 tests)
```
✓ permutation: identical columns
✓ permutation: ambiguous same values
✓ permutation: 5 columns reversed
✓ permutation: single column
```

#### 10. 50/50 Spider Validation (5 tests)
```
✓ 50/50: found 100 valid queries
✓ 50/50: correct queries accuracy (50/50)
✓ 50/50: error queries accuracy (0/50)
✓ 50/50: evaluator accuracy (100.0%)
✓ 50/50: simulated model accuracy (50.0%)
```

This test validates the evaluator against real Spider data:
- 50 queries executed as-is (should all match) → 50/50 matched
- 50 queries intentionally broken (should all fail) → 0/50 matched
- Evaluator correctly classified all 100 queries

## Usage

### Basic Usage

```python
from scripts.evaluation import eval_exec_match

result = eval_exec_match(
    db_path="path/to/database.sqlite",
    predicted_sql="SELECT name, age FROM users",
    gold_sql="SELECT age, name FROM users"  # Different column order
)

print(f"Match: {result.match}")        # True
print(f"Error: {result.error}")        # None
print(f"Predicted results: {result.pred_results}")
print(f"Gold results: {result.gold_results}")
```

### Batch Evaluation

```python
from scripts.evaluation import evaluate_predictions

predictions = [
    ("db1.sqlite", "SELECT ...", "SELECT ..."),
    ("db2.sqlite", "SELECT ...", "SELECT ..."),
    # ...
]

metrics = evaluate_predictions(predictions, verbose=True)
print(f"Accuracy: {metrics['accuracy']:.2%}")
print(f"Correct: {metrics['correct']}/{metrics['total']}")
```

### Running Tests

```bash
cd local_workspace
python3 scripts/test_evaluation.py
```

## Comparison with Spider's Official Evaluation

| Feature | Spider `evaluation.py` | Spider `test-suite-sql-eval` | Our Implementation |
|---------|----------------------|------------------------------|-------------------|
| Requires SQL parsing | Yes | No | No |
| Column permutation | Limited | Full | Full |
| Row order handling | Yes | Yes | Yes |
| Multiset comparison | No | Yes | Yes |
| Type normalization | No | Limited | Yes |
| Works with Malloy SQL | No | Yes | Yes |

Our implementation is based on `test-suite-sql-eval` but adds type normalization for robustness.

## References

- [Spider Dataset](https://yale-lily.github.io/spider)
- [test-suite-sql-eval](https://github.com/taoyds/test-suite-sql-eval) - Official test suite evaluation
- [Spider evaluation.py](https://github.com/taoyds/spider/blob/master/evaluation.py) - Original evaluation script

---

*Last updated: January 2025*
