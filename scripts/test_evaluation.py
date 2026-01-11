#!/usr/bin/env python3
"""
Comprehensive test suite for the evaluation script.

Tests all edge cases for execution-based SQL comparison:
- Column order permutations
- Row order (with/without ORDER BY)
- Duplicate rows
- Empty results
- NULL handling
- Type coercion
- 50/50 validation with real Spider queries
"""

import os
import sys
import json
import sqlite3
import tempfile
import random
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from evaluation import (
    result_eq, multiset_eq, normalize_value, normalize_row,
    eval_exec_match, EvalResult, execute_query
)


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def record(self, name: str, passed: bool, details: str = ""):
        if passed:
            self.passed += 1
            print(f"  ✓ {name}")
        else:
            self.failed += 1
            self.failures.append((name, details))
            print(f"  ✗ {name}")
            if details:
                print(f"    {details}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed ({100*self.passed/total:.1f}%)")
        if self.failures:
            print(f"\nFailures:")
            for name, details in self.failures:
                print(f"  - {name}: {details}")
        print(f"{'='*60}")
        return self.failed == 0


def create_test_db(tables_sql: str, data_sql: str) -> str:
    """Create a temporary SQLite database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    for stmt in tables_sql.split(';'):
        if stmt.strip():
            cursor.execute(stmt)

    for stmt in data_sql.split(';'):
        if stmt.strip():
            cursor.execute(stmt)

    conn.commit()
    conn.close()
    return path


# =============================================================================
# Test 1: Basic Functionality Tests
# =============================================================================

def test_basic_functionality(results: TestResults):
    """Test basic comparison functionality."""
    print("\n[Test 1: Basic Functionality]")

    # Test multiset_eq
    results.record(
        "multiset_eq: identical lists",
        multiset_eq([1, 2, 3], [1, 2, 3])
    )
    results.record(
        "multiset_eq: reordered lists",
        multiset_eq([1, 2, 3], [3, 1, 2])
    )
    results.record(
        "multiset_eq: with duplicates same",
        multiset_eq([1, 2, 2, 3], [2, 1, 3, 2])
    )
    results.record(
        "multiset_eq: with duplicates different",
        not multiset_eq([1, 2, 2, 3], [1, 2, 3, 3])
    )
    results.record(
        "multiset_eq: different lengths",
        not multiset_eq([1, 2], [1, 2, 3])
    )
    results.record(
        "multiset_eq: empty lists",
        multiset_eq([], [])
    )

    # Test normalize_value
    results.record(
        "normalize: float to int",
        normalize_value(5.0) == 5
    )
    results.record(
        "normalize: string number to int",
        normalize_value("42") == 42
    )
    results.record(
        "normalize: string float to number",
        normalize_value("3.14") == 3.14
    )
    results.record(
        "normalize: None stays None",
        normalize_value(None) is None
    )
    results.record(
        "normalize: regular string unchanged",
        normalize_value("hello") == "hello"
    )


# =============================================================================
# Test 2: Column Order Permutation Tests
# =============================================================================

def test_column_order(results: TestResults):
    """Test that column order differences are handled correctly."""
    print("\n[Test 2: Column Order Permutation]")

    # Same data, columns in different order
    result1 = [(1, 'a', 100), (2, 'b', 200)]
    result2 = [('a', 100, 1), ('b', 200, 2)]

    results.record(
        "column reorder: 3 columns swapped",
        result_eq(result1, result2, order_matters=False),
        f"Expected match: {result1} vs {result2}"
    )

    # Same data, 2 columns swapped
    result1 = [(1, 'x'), (2, 'y')]
    result2 = [('x', 1), ('y', 2)]

    results.record(
        "column reorder: 2 columns swapped",
        result_eq(result1, result2, order_matters=False)
    )

    # Columns in same order
    result1 = [(1, 2), (3, 4)]
    result2 = [(1, 2), (3, 4)]

    results.record(
        "column order: same order matches",
        result_eq(result1, result2, order_matters=False)
    )

    # Different values should not match regardless of permutation
    result1 = [(1, 2), (3, 4)]
    result2 = [(5, 6), (7, 8)]

    results.record(
        "column reorder: different values don't match",
        not result_eq(result1, result2, order_matters=False)
    )


# =============================================================================
# Test 3: Row Order Tests (ORDER BY handling)
# =============================================================================

def test_row_order(results: TestResults):
    """Test row order handling with and without ORDER BY."""
    print("\n[Test 3: Row Order (ORDER BY)]")

    # Same rows, different order - without ORDER BY should match
    result1 = [(1, 'a'), (2, 'b'), (3, 'c')]
    result2 = [(3, 'c'), (1, 'a'), (2, 'b')]

    results.record(
        "row order: different order, order_matters=False",
        result_eq(result1, result2, order_matters=False)
    )

    # Same rows, different order - with ORDER BY should NOT match
    results.record(
        "row order: different order, order_matters=True",
        not result_eq(result1, result2, order_matters=True)
    )

    # Same rows, same order - both should match
    result1 = [(1, 'a'), (2, 'b')]
    result2 = [(1, 'a'), (2, 'b')]

    results.record(
        "row order: same order, order_matters=False",
        result_eq(result1, result2, order_matters=False)
    )
    results.record(
        "row order: same order, order_matters=True",
        result_eq(result1, result2, order_matters=True)
    )


# =============================================================================
# Test 4: Duplicate Row Tests
# =============================================================================

def test_duplicate_rows(results: TestResults):
    """Test that duplicate rows are handled correctly."""
    print("\n[Test 4: Duplicate Rows]")

    # Same duplicates
    result1 = [(1,), (1,), (2,)]
    result2 = [(1,), (2,), (1,)]

    results.record(
        "duplicates: same count, different order",
        result_eq(result1, result2, order_matters=False)
    )

    # Different duplicate counts
    result1 = [(1,), (1,), (2,)]
    result2 = [(1,), (2,), (2,)]

    results.record(
        "duplicates: different counts should not match",
        not result_eq(result1, result2, order_matters=False)
    )

    # All duplicates
    result1 = [(1,), (1,), (1,)]
    result2 = [(1,), (1,), (1,)]

    results.record(
        "duplicates: all same values",
        result_eq(result1, result2, order_matters=False)
    )


# =============================================================================
# Test 5: Empty Results Tests
# =============================================================================

def test_empty_results(results: TestResults):
    """Test handling of empty result sets."""
    print("\n[Test 5: Empty Results]")

    results.record(
        "empty: both empty",
        result_eq([], [], order_matters=False)
    )
    results.record(
        "empty: first empty, second not",
        not result_eq([], [(1,)], order_matters=False)
    )
    results.record(
        "empty: first not empty, second empty",
        not result_eq([(1,)], [], order_matters=False)
    )


# =============================================================================
# Test 6: NULL Handling Tests
# =============================================================================

def test_null_handling(results: TestResults):
    """Test handling of NULL values."""
    print("\n[Test 6: NULL Handling]")

    # NULLs in same positions
    result1 = [(1, None), (2, 'b')]
    result2 = [(1, None), (2, 'b')]

    results.record(
        "NULL: same positions",
        result_eq(result1, result2, order_matters=False)
    )

    # NULLs vs non-NULLs
    result1 = [(1, None)]
    result2 = [(1, 'a')]

    results.record(
        "NULL: NULL vs value should not match",
        not result_eq(result1, result2, order_matters=False)
    )

    # Multiple NULLs
    result1 = [(None, None)]
    result2 = [(None, None)]

    results.record(
        "NULL: multiple NULLs",
        result_eq(result1, result2, order_matters=False)
    )


# =============================================================================
# Test 7: Type Coercion Tests
# =============================================================================

def test_type_coercion(results: TestResults):
    """Test handling of type differences."""
    print("\n[Test 7: Type Coercion]")

    # Integer vs float (whole number)
    result1 = [(1, 2)]
    result2 = [(1.0, 2.0)]

    results.record(
        "type: int vs float (whole)",
        result_eq(result1, result2, order_matters=False)
    )

    # String number vs int
    result1 = [(1, 2)]
    result2 = [("1", "2")]

    results.record(
        "type: int vs string number",
        result_eq(result1, result2, order_matters=False)
    )


# =============================================================================
# Test 8: Real SQL Execution Tests
# =============================================================================

def test_sql_execution(results: TestResults):
    """Test with actual SQL queries against a database."""
    print("\n[Test 8: SQL Execution]")

    # Create test database
    tables_sql = """
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)
    """
    data_sql = """
        INSERT INTO users VALUES (1, 'Alice', 30);
        INSERT INTO users VALUES (2, 'Bob', 25);
        INSERT INTO users VALUES (3, 'Charlie', 35);
        INSERT INTO orders VALUES (1, 1, 100.0);
        INSERT INTO orders VALUES (2, 1, 200.0);
        INSERT INTO orders VALUES (3, 2, 150.0)
    """

    db_path = create_test_db(tables_sql, data_sql)

    try:
        # Identical queries
        result = eval_exec_match(
            db_path,
            "SELECT name, age FROM users",
            "SELECT name, age FROM users"
        )
        results.record("SQL exec: identical queries", result.match)

        # Same result, different column order
        result = eval_exec_match(
            db_path,
            "SELECT age, name FROM users",
            "SELECT name, age FROM users"
        )
        results.record("SQL exec: column order swap", result.match)

        # Same result, different row order (no ORDER BY)
        result = eval_exec_match(
            db_path,
            "SELECT name FROM users ORDER BY age DESC",
            "SELECT name FROM users"  # No ORDER BY in gold
        )
        results.record("SQL exec: row order differs, no ORDER BY in gold", result.match)

        # Different row order with ORDER BY in gold
        result = eval_exec_match(
            db_path,
            "SELECT name FROM users ORDER BY age DESC",
            "SELECT name FROM users ORDER BY name"  # Different ORDER BY
        )
        results.record(
            "SQL exec: different ORDER BY should not match",
            not result.match,
            f"Got match={result.match}"
        )

        # Aggregate query
        result = eval_exec_match(
            db_path,
            "SELECT COUNT(*) FROM users",
            "SELECT COUNT(*) FROM users"
        )
        results.record("SQL exec: aggregate COUNT", result.match)

        # Wrong result
        result = eval_exec_match(
            db_path,
            "SELECT name FROM users WHERE age > 30",
            "SELECT name FROM users WHERE age < 30"
        )
        results.record("SQL exec: wrong WHERE clause", not result.match)

        # Syntax error in predicted
        result = eval_exec_match(
            db_path,
            "SELEC name FROM users",  # Typo
            "SELECT name FROM users"
        )
        results.record("SQL exec: syntax error returns False", not result.match)
        results.record("SQL exec: syntax error has error message", result.error is not None)

    finally:
        os.unlink(db_path)


# =============================================================================
# Test 9: 50/50 Validation with Real Spider Data
# =============================================================================

def test_50_50_validation(results: TestResults, spider_path: Path):
    """
    Test with 50 correct queries and 50 intentionally broken queries.
    Should get exactly 50% accuracy.
    """
    print("\n[Test 9: 50/50 Validation with Spider Data]")

    # Load Spider dev data - check multiple possible locations
    possible_paths = [
        (spider_path / 'spider_extracted' / 'spider_data' / 'dev.json',
         spider_path / 'spider_extracted' / 'spider_data' / 'database'),
        (spider_path / 'spider' / 'evaluation_examples' / 'examples' / 'dev.json',
         spider_path / 'spider' / 'evaluation_examples' / 'examples' / 'database'),
    ]

    dev_path = None
    db_base = None
    for dp, db in possible_paths:
        if dp.exists():
            dev_path = dp
            db_base = db
            break

    if dev_path is None:
        results.record("50/50: Spider data available", False, "Spider data not found in expected locations")
        return

    with open(dev_path) as f:
        dev_data = json.load(f)

    # Find 100 queries with accessible databases
    valid_queries = []
    for item in dev_data:
        db_path = db_base / item['db_id'] / f"{item['db_id']}.sqlite"
        if db_path.exists():
            valid_queries.append({
                'db_path': str(db_path),
                'gold_sql': item['query'],
                'question': item['question'],
                'db_id': item['db_id']
            })
        if len(valid_queries) >= 100:
            break

    if len(valid_queries) < 100:
        results.record(
            "50/50: enough queries found",
            False,
            f"Only found {len(valid_queries)} valid queries"
        )
        return

    results.record("50/50: found 100 valid queries", True)

    # Split into 50 correct and 50 with errors
    correct_queries = valid_queries[:50]
    error_queries = valid_queries[50:100]

    # Introduce errors into the error queries
    def introduce_error(sql: str, db_path: str) -> str:
        """
        Introduce an error that GUARANTEES a different result.

        Strategy: Execute the original query first, then craft an error
        that produces a definitely-different result.
        """
        # First, see what the original query returns
        orig_results, err = execute_query(db_path, sql)
        if err:
            # Original query has errors, just make it worse
            return "SELECT 'BROKEN_QUERY_ERROR'"

        # Choose error strategy based on original results
        if orig_results and len(orig_results) > 0:
            # Original has results - use LIMIT 0 to get empty result
            # But we need to handle queries that already have LIMIT
            if 'LIMIT' in sql.upper():
                # Replace existing LIMIT with LIMIT 0
                import re
                return re.sub(r'LIMIT\s+\d+', 'LIMIT 0', sql, flags=re.IGNORECASE)
            else:
                return sql + ' LIMIT 0'
        else:
            # Original returns empty - make query return something
            # Use a simple query that always returns a result
            return "SELECT 'FORCED_DIFFERENT_RESULT' AS col1"

    # Evaluate correct queries (should all match)
    correct_matches = 0
    for q in correct_queries:
        result = eval_exec_match(q['db_path'], q['gold_sql'], q['gold_sql'])
        if result.match:
            correct_matches += 1

    results.record(
        f"50/50: correct queries accuracy ({correct_matches}/50)",
        correct_matches == 50,
        f"Expected 50, got {correct_matches}"
    )

    # Evaluate error queries (should all fail)
    error_matches = 0
    for q in error_queries:
        broken_sql = introduce_error(q['gold_sql'], q['db_path'])
        result = eval_exec_match(q['db_path'], broken_sql, q['gold_sql'])
        if result.match:
            error_matches += 1

    results.record(
        f"50/50: error queries accuracy ({error_matches}/50)",
        error_matches == 0,
        f"Expected 0 matches, got {error_matches}"
    )

    # The evaluator should correctly identify:
    # - All 50 correct queries as matching (correct_matches = 50)
    # - All 50 broken queries as NOT matching (error_matches = 0)
    # This means evaluator accuracy is 100% (correctly classified all 100)
    evaluator_correct = correct_matches + (50 - error_matches)
    evaluator_accuracy = evaluator_correct / 100

    results.record(
        f"50/50: evaluator accuracy ({evaluator_accuracy*100:.1f}%)",
        evaluator_accuracy == 1.0,
        f"Expected 100% evaluator accuracy, got {evaluator_accuracy*100:.1f}%"
    )

    # Also verify the simulated "model accuracy" would be 50%
    # (50 correct out of 100 if we submitted these as predictions)
    simulated_model_accuracy = correct_matches / 100
    results.record(
        f"50/50: simulated model accuracy ({simulated_model_accuracy*100:.1f}%)",
        simulated_model_accuracy == 0.5,
        f"Expected 50%, got {simulated_model_accuracy*100:.1f}%"
    )


# =============================================================================
# Test 10: Edge Cases with Column Permutations
# =============================================================================

def test_column_permutation_edge_cases(results: TestResults):
    """Test edge cases in column permutation logic."""
    print("\n[Test 10: Column Permutation Edge Cases]")

    # Same values in multiple columns
    result1 = [(1, 1), (2, 2)]
    result2 = [(1, 1), (2, 2)]

    results.record(
        "permutation: identical columns",
        result_eq(result1, result2, order_matters=False)
    )

    # Ambiguous permutation (both columns have same values)
    result1 = [('a', 'a'), ('b', 'b')]
    result2 = [('a', 'a'), ('b', 'b')]

    results.record(
        "permutation: ambiguous same values",
        result_eq(result1, result2, order_matters=False)
    )

    # Many columns
    result1 = [(1, 2, 3, 4, 5)]
    result2 = [(5, 4, 3, 2, 1)]

    results.record(
        "permutation: 5 columns reversed",
        result_eq(result1, result2, order_matters=False)
    )

    # Single column
    result1 = [(1,), (2,), (3,)]
    result2 = [(3,), (1,), (2,)]

    results.record(
        "permutation: single column",
        result_eq(result1, result2, order_matters=False)
    )


# =============================================================================
# Main Test Runner
# =============================================================================

def main():
    print("=" * 60)
    print("EVALUATION SCRIPT TEST SUITE")
    print("=" * 60)

    results = TestResults()

    # Determine Spider path
    script_dir = Path(__file__).parent
    spider_path = script_dir.parent.parent  # Go up to spider1 directory

    # Run all tests
    test_basic_functionality(results)
    test_column_order(results)
    test_row_order(results)
    test_duplicate_rows(results)
    test_empty_results(results)
    test_null_handling(results)
    test_type_coercion(results)
    test_sql_execution(results)
    test_column_permutation_edge_cases(results)
    test_50_50_validation(results, spider_path)

    # Print summary
    all_passed = results.summary()

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
