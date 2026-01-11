# ADR-002: Execution-Based Evaluation

**Status:** Accepted

**Date:** 2025-01-11

## Context

We need to evaluate whether LLM-generated SQL (via Malloy) produces correct results. Three evaluation approaches exist:

| Approach | Description | Limitation |
|----------|-------------|------------|
| **Exact Match** | Compare SQL strings character-by-character | Different SQL can produce same results |
| **Component Match** | Parse SQL AST and compare components | Requires compatible SQL dialects |
| **Execution Match** | Run queries, compare result sets | Requires database access |

Our specific challenge: Malloy compiles to SQL that looks different from Spider ground truth SQL, but should produce identical results.

## Decision

Use execution-based evaluation: run both predicted and gold SQL queries against the database and compare result sets.

## Rationale

1. **Semantic equivalence**: Two queries producing identical results are functionally equivalent, regardless of syntax differences.

2. **Malloy compatibility**: Malloy generates valid SQL but with different structure (CTEs, column ordering, aliases). String/AST comparison would fail.

3. **Established practice**: Spider's official `test-suite-sql-eval` uses execution-based evaluation for this reason.

4. **Robustness**: Handles legitimate SQL variations:
   - Column order differences
   - Table alias variations
   - JOIN order permutations
   - Subquery vs JOIN reformulations

## Implementation Details

Our evaluator handles these cases:

| Case | Handling |
|------|----------|
| Column order differs | Try all column permutations |
| Row order differs | Compare as multisets (unless ORDER BY in gold) |
| Type differences | Normalize (1 == 1.0 == "1") |
| NULL values | Exact NULL matching |
| Duplicates | Multiset comparison preserves counts |

See `docs/evaluation_strategy.md` for full technical specification.

## Consequences

**Positive:**
- Works with any SQL dialect that executes correctly
- Captures semantic correctness, not syntactic similarity
- Industry-standard approach for NL2SQL evaluation
- Handles Malloy's SQL generation naturally

**Negative:**
- Requires database access for every evaluation
- Slower than string comparison
- Some edge cases ambiguous (e.g., floating point precision)
- Cannot evaluate queries on unavailable databases

**Mitigations:**
- All Spider databases available locally
- Evaluation takes seconds per query (acceptable)
- Type normalization handles most precision issues
