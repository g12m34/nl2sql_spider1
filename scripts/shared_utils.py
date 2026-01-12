#!/usr/bin/env python3
"""
Shared utilities for NL2Malloy evaluation.

This module consolidates common functions used across evaluation scripts
to ensure consistency and maintainability.
"""

import json
import itertools
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Value Normalization
# =============================================================================

def normalize_value(val: Any) -> Any:
    """
    Normalize a value for comparison.

    Handles type coercion issues (e.g., int vs float, string numbers).
    This ensures that 1.0 == 1 and "5" == 5 for result comparison.
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


# =============================================================================
# Result Comparison Functions
# =============================================================================

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


def quick_reject(result1: List[Tuple], result2: List[Tuple]) -> bool:
    """
    Quick rejection test - if the sets of values per column don't overlap,
    results can't possibly match under any permutation.

    Returns True if results COULD match, False if they definitely can't.
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


def results_match(
    result1: List[Tuple],
    result2: List[Tuple],
    order_matters: bool = False
) -> bool:
    """
    Compare two query result sets for equivalence.

    This is the canonical function for comparing query results.
    It handles:
    - Column reordering (columns may appear in different order)
    - Value normalization (1.0 == 1, "5" == 5)
    - Multiset comparison (preserving duplicate counts)
    - Order sensitivity (for ORDER BY queries)

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


# =============================================================================
# Malloy Code Extraction
# =============================================================================

def extract_malloy_code(response: str) -> str:
    """
    Extract Malloy code from model response.

    Removes markdown code blocks and other formatting that LLMs
    may include in their responses.
    """
    text = response.strip()

    # Remove markdown code blocks
    if text.startswith("```malloy"):
        text = text[9:]
    elif text.startswith("```sql"):
        text = text[6:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# =============================================================================
# Batch Job Metadata Management
# =============================================================================

class BatchJobManager:
    """
    Manages batch job metadata for different API providers.

    Provides consistent save/load/results functionality across
    Anthropic, OpenAI, and Gemini batch APIs.
    """

    def __init__(self, batch_dir: Path, provider: str):
        """
        Initialize batch job manager.

        Args:
            batch_dir: Directory to store batch job files
            provider: Provider name ('anthropic', 'openai', 'gemini')
        """
        self.batch_dir = batch_dir
        self.provider = provider
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    def _get_job_id_key(self) -> str:
        """Get the key name for job ID based on provider."""
        if self.provider == 'anthropic':
            return 'batch_id'
        elif self.provider == 'openai':
            return 'job_id'
        elif self.provider == 'gemini':
            return 'job_name'
        return 'job_id'

    def _get_info_filename(self, job_id: str) -> str:
        """Get the filename for job info based on provider."""
        if self.provider == 'gemini':
            return f"{job_id.replace('/', '_')}.json"
        return f"{self.provider}_{job_id}.json"

    def _get_results_filename(self, job_id: str) -> str:
        """Get the filename for results based on provider."""
        if self.provider == 'gemini':
            return f"results_{job_id.replace('/', '_')}.json"
        return f"results_{self.provider}_{job_id}.json"

    def save_job_info(
        self,
        job_id: str,
        questions: Dict,
        model: str,
        display_name: Optional[str] = None
    ) -> Path:
        """
        Save batch job info for later retrieval.

        Args:
            job_id: The batch job ID from the API
            questions: Mapping of request IDs to question metadata
            model: Model name used for the batch
            display_name: Optional human-readable name for the job

        Returns:
            Path to the saved info file
        """
        id_key = self._get_job_id_key()
        info = {
            id_key: job_id,
            'model': model,
            'submitted_at': datetime.now().isoformat(),
            'questions': questions
        }

        if display_name:
            info['display_name'] = display_name

        info_file = self.batch_dir / self._get_info_filename(job_id)
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)

        print(f"Job info saved to: {info_file}")
        return info_file

    def load_job_info(self, job_id: str) -> Optional[Dict]:
        """
        Load saved batch job info.

        Args:
            job_id: The batch job ID

        Returns:
            Job info dict or None if not found
        """
        info_file = self.batch_dir / self._get_info_filename(job_id)
        if info_file.exists():
            with open(info_file) as f:
                return json.load(f)
        return None

    def save_results(
        self,
        results: List[Dict],
        job_id: str,
        model: str
    ) -> Path:
        """
        Save batch results for evaluation.

        Args:
            results: List of result dictionaries
            job_id: The batch job ID
            model: Model name

        Returns:
            Path to the saved results file
        """
        id_key = self._get_job_id_key()
        output = {
            id_key: job_id,
            'model': model,
            'completed_at': datetime.now().isoformat(),
            'num_results': len(results),
            'results': results
        }

        results_file = self.batch_dir / self._get_results_filename(job_id)
        with open(results_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"Results saved to: {results_file}")
        return results_file


# =============================================================================
# Evaluation Helpers
# =============================================================================

def check_order_matters(sql: str) -> bool:
    """
    Determine if row order matters for a query based on ORDER BY clause.

    Args:
        sql: The SQL query string

    Returns:
        True if ORDER BY is present (order matters)
    """
    return 'order by' in sql.lower()


# =============================================================================
# Self-test
# =============================================================================

if __name__ == '__main__':
    print("Running self-tests...")

    # Test normalize_value
    assert normalize_value(1.0) == 1
    assert normalize_value("5") == 5
    assert normalize_value("3.0") == 3
    assert normalize_value(None) is None
    assert normalize_value("hello") == "hello"
    print("  normalize_value: OK")

    # Test multiset_eq
    assert multiset_eq([1, 2, 2], [2, 1, 2]) == True
    assert multiset_eq([1, 2], [1, 2, 2]) == False
    assert multiset_eq([], []) == True
    print("  multiset_eq: OK")

    # Test results_match
    assert results_match([(1, 2)], [(1, 2)]) == True
    assert results_match([(1, 2)], [(2, 1)]) == True  # Column permutation
    assert results_match([(1,), (2,)], [(2,), (1,)]) == True  # Row reorder
    assert results_match([(1,), (2,)], [(2,), (1,)], order_matters=True) == False
    assert results_match([], []) == True
    assert results_match([(1,)], []) == False
    print("  results_match: OK")

    # Test extract_malloy_code
    assert extract_malloy_code("```malloy\nrun: foo\n```") == "run: foo"
    assert extract_malloy_code("run: foo") == "run: foo"
    assert extract_malloy_code("```sql\nSELECT *\n```") == "SELECT *"
    print("  extract_malloy_code: OK")

    # Test check_order_matters
    assert check_order_matters("SELECT * FROM foo ORDER BY bar") == True
    assert check_order_matters("SELECT * FROM foo") == False
    print("  check_order_matters: OK")

    print("\nAll self-tests passed!")
