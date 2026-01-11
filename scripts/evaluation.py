#!/usr/bin/env python3
"""
Execution-based evaluation for NL2SQL.

Compares query results by execution rather than SQL structure,
enabling evaluation of Malloy-generated SQL against ground truth.

Based on the test-suite-sql-eval approach from Spider.
"""

import sqlite3
import itertools
from collections import defaultdict
from typing import List, Tuple, Any, Optional
from dataclasses import dataclass


@dataclass
class EvalResult:
    """Result of evaluating a single query pair."""
    match: bool
    predicted_sql: str
    gold_sql: str
    db_path: str
    error: Optional[str] = None
    pred_results: Optional[List[Tuple]] = None
    gold_results: Optional[List[Tuple]] = None


def multiset_eq(l1: List, l2: List) -> bool:
    """
    Compare two lists as multisets (bags that preserve duplicate counts).

    Returns True if both lists contain the same elements with the same counts.
    """
    if len(l1) != len(l2):
        return False

    d = defaultdict(int)
    for e in l1:
        d[e] += 1
    for e in l2:
        d[e] -= 1
        if d[e] < 0:
            return False
    return True


def normalize_value(val: Any) -> Any:
    """
    Normalize a value for comparison.

    Handles type coercion issues (e.g., int vs float, string numbers).
    """
    if val is None:
        return None

    # Convert floats that are whole numbers to int for comparison
    if isinstance(val, float) and val.is_integer():
        return int(val)

    # Try to convert string numbers to numbers
    if isinstance(val, str):
        try:
            # Try int first
            return int(val)
        except ValueError:
            try:
                f = float(val)
                if f.is_integer():
                    return int(f)
                return f
            except ValueError:
                pass

    return val


def normalize_row(row: Tuple) -> Tuple:
    """Normalize all values in a row."""
    return tuple(normalize_value(v) for v in row)


def quick_reject(result1: List[Tuple], result2: List[Tuple]) -> bool:
    """
    Quick rejection test - if the sets of values per column don't overlap,
    results can't possibly match under any permutation.
    """
    if len(result1) == 0 or len(result2) == 0:
        return True

    # Check if value sets are compatible
    set1 = set(normalize_value(v) for row in result1 for v in row)
    set2 = set(normalize_value(v) for row in result2 for v in row)

    # If there's no overlap at all, reject
    if len(set1) > 0 and len(set2) > 0 and len(set1 & set2) == 0:
        return False

    return True


def get_column_permutations(result1: List[Tuple], result2: List[Tuple]) -> List[Tuple[int, ...]]:
    """
    Generate candidate column permutations that could make result2 match result1.

    Uses constraint propagation to reduce the search space.
    """
    if len(result1) == 0 or len(result2) == 0:
        return [tuple(range(len(result2[0]) if result2 else 0))]

    num_cols = len(result1[0])

    # For each column in result1, find which columns in result2 have compatible values
    candidates = []
    for i in range(num_cols):
        col1_values = set(normalize_value(row[i]) for row in result1)
        compatible = []
        for j in range(num_cols):
            col2_values = set(normalize_value(row[j]) for row in result2)
            # Column j is compatible if it has the same value set
            if col1_values == col2_values:
                compatible.append(j)
        candidates.append(compatible)

    # Generate permutations that use each column exactly once
    def generate_perms(idx, used, current):
        if idx == num_cols:
            yield tuple(current)
            return
        for c in candidates[idx]:
            if c not in used:
                yield from generate_perms(idx + 1, used | {c}, current + [c])

    perms = list(generate_perms(0, set(), []))

    # If no valid permutations found, fall back to all permutations (for small col counts)
    if not perms and num_cols <= 6:
        perms = list(itertools.permutations(range(num_cols)))

    return perms if perms else [tuple(range(num_cols))]


def permute_row(row: Tuple, perm: Tuple[int, ...]) -> Tuple:
    """Apply a column permutation to a row."""
    return tuple(row[perm[i]] for i in range(len(perm)))


def result_eq(result1: List[Tuple], result2: List[Tuple], order_matters: bool) -> bool:
    """
    Compare two query result sets for equivalence.

    Args:
        result1: First result set (typically gold/reference)
        result2: Second result set (typically predicted)
        order_matters: If True, row order must match (for ORDER BY queries)

    Returns:
        True if the results are equivalent under the given constraints.
    """
    # Handle empty results
    if len(result1) == 0 and len(result2) == 0:
        return True

    if len(result1) == 0 or len(result2) == 0:
        return False

    # Check row counts
    if len(result1) != len(result2):
        return False

    # Check column counts
    if len(result1[0]) != len(result2[0]):
        return False

    num_cols = len(result1[0])

    # Normalize values for comparison
    result1_norm = [normalize_row(row) for row in result1]
    result2_norm = [normalize_row(row) for row in result2]

    # Quick rejection test
    if not quick_reject(result1_norm, result2_norm):
        return False

    # Single column case - no permutation needed
    if num_cols == 1:
        if order_matters:
            return result1_norm == result2_norm
        else:
            return multiset_eq(result1_norm, result2_norm)

    # Try column permutations
    for perm in get_column_permutations(result1_norm, result2_norm):
        if len(perm) != num_cols:
            continue
        if len(set(perm)) != num_cols:  # Must use each column exactly once
            continue

        result2_perm = [permute_row(row, perm) for row in result2_norm]

        if order_matters:
            if result1_norm == result2_perm:
                return True
        else:
            if multiset_eq(result1_norm, result2_perm):
                return True

    return False


def execute_query(db_path: str, sql: str) -> Tuple[Optional[List[Tuple]], Optional[str]]:
    """
    Execute a SQL query and return results or error.

    Returns:
        (results, None) on success
        (None, error_message) on failure
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()
        return results, None
    except Exception as e:
        return None, str(e)


def eval_exec_match(db_path: str, predicted_sql: str, gold_sql: str) -> EvalResult:
    """
    Evaluate if predicted SQL produces the same results as gold SQL.

    Args:
        db_path: Path to SQLite database
        predicted_sql: The SQL query to evaluate
        gold_sql: The reference SQL query

    Returns:
        EvalResult with match status and details
    """
    # Execute predicted query
    pred_results, pred_error = execute_query(db_path, predicted_sql)
    if pred_error:
        return EvalResult(
            match=False,
            predicted_sql=predicted_sql,
            gold_sql=gold_sql,
            db_path=db_path,
            error=f"Predicted SQL error: {pred_error}"
        )

    # Execute gold query
    gold_results, gold_error = execute_query(db_path, gold_sql)
    if gold_error:
        return EvalResult(
            match=False,
            predicted_sql=predicted_sql,
            gold_sql=gold_sql,
            db_path=db_path,
            error=f"Gold SQL error: {gold_error}"
        )

    # Determine if order matters (presence of ORDER BY in gold query)
    order_matters = 'order by' in gold_sql.lower()

    # Compare results
    match = result_eq(gold_results, pred_results, order_matters)

    return EvalResult(
        match=match,
        predicted_sql=predicted_sql,
        gold_sql=gold_sql,
        db_path=db_path,
        pred_results=pred_results,
        gold_results=gold_results
    )


def evaluate_predictions(
    predictions: List[Tuple[str, str, str]],  # (db_path, predicted_sql, gold_sql)
    verbose: bool = False
) -> dict:
    """
    Evaluate a list of predictions against gold queries.

    Returns:
        Dictionary with accuracy metrics and detailed results
    """
    results = []
    correct = 0
    errors = 0

    for db_path, predicted_sql, gold_sql in predictions:
        result = eval_exec_match(db_path, predicted_sql, gold_sql)
        results.append(result)

        if result.match:
            correct += 1
        if result.error:
            errors += 1

        if verbose:
            status = "✓" if result.match else "✗"
            print(f"{status} {db_path}")
            if result.error:
                print(f"  Error: {result.error}")

    total = len(predictions)
    accuracy = correct / total if total > 0 else 0.0

    return {
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'errors': errors,
        'results': results
    }


if __name__ == '__main__':
    # Quick self-test
    print("Running self-test...")

    # Test multiset_eq
    assert multiset_eq([1, 2, 2], [2, 1, 2]) == True
    assert multiset_eq([1, 2], [1, 2, 2]) == False
    assert multiset_eq([], []) == True

    # Test normalize_value
    assert normalize_value(1.0) == 1
    assert normalize_value("5") == 5
    assert normalize_value(None) is None

    print("Self-test passed!")
