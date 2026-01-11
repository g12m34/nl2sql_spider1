# ADR-001: Hard+Extra Questions Only

**Status:** Accepted

**Date:** 2025-01-11

## Context

We need to evaluate LLM performance on the Spider NL2SQL benchmark. Spider questions are categorized into four difficulty levels:

| Difficulty | Spider Dev | Spider Train | Characteristics |
|------------|-----------|--------------|-----------------|
| Easy | 329 (31.8%) | 2,383 | Single table, no complex operations |
| Medium | 397 (38.4%) | 3,965 | Joins OR GROUP BY/ORDER BY |
| Hard | 230 (22.2%) | 1,801 | Multiple joins + GROUP BY, or subqueries |
| Extra | 78 (7.5%) | 510 | Set operations (UNION, INTERSECT, EXCEPT) |

We had to decide between:
1. **Stratified sampling**: Sample proportionally from all difficulty levels
2. **Hard-only sampling**: Focus exclusively on hard and extra-hard questions

## Decision

Use only hard and extra-hard questions for LLM evaluation.

## Rationale

1. **Target alignment**: Our goal is Spider 2.0, which focuses on harder, more realistic enterprise SQL. Easy questions don't predict performance on complex queries.

2. **Model separation**: Current LLMs (GPT-4, Claude, etc.) achieve 80-90%+ on easy/medium Spider questions. Hard questions better differentiate model capabilities.

3. **Efficiency**: Fewer questions needed to identify the best-performing models. Testing easy questions wastes compute on tasks where all models succeed.

4. **Cost optimization**: Reducing evaluation set size lowers API costs while maintaining statistical power for meaningful comparisons.

5. **Signal-to-noise ratio**: Hard questions surface genuine capability differences rather than minor implementation variations.

## Consequences

**Positive:**
- Faster model comparison and iteration
- Lower evaluation costs
- Better discrimination between models
- Results more relevant to production use cases

**Negative:**
- May miss regressions on easy/medium queries
- Not directly comparable to published Spider leaderboard numbers (which use full dev set)
- Could overlook models that excel at simple queries but fail on complex ones

**Mitigations:**
- Can run full stratified evaluation on final model candidates
- Document that our metrics are for hard+extra subset only
