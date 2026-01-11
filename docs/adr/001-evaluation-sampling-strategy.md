# ADR-001: Evaluation Sampling Strategy

**Status:** Accepted

**Date:** 2025-01-11

## Context

We need to evaluate LLM performance on the Spider NL2SQL benchmark to identify the best models for our Malloy-based approach. Key decisions:

1. Which questions to include (difficulty levels)
2. How many questions to sample
3. How to ensure reproducibility

Spider questions span four difficulty levels:

| Difficulty | Characteristics | Train Set |
|------------|-----------------|-----------|
| Easy | Single table, no complex ops | 2,383 |
| Medium | Joins OR GROUP BY/ORDER BY | 3,965 |
| Hard | Multiple joins + GROUP BY, subqueries | 1,801 |
| Extra | Set operations (UNION, INTERSECT, EXCEPT) | 510 |

## Decision

**Sample 200 questions (100 hard + 100 extra) using fixed random seed 42, saved to a JSON file.**

### Difficulty Selection: Hard+Extra Only

- Current LLMs achieve 80-90%+ on easy/medium questions—not discriminative
- Our goal is Spider 2.0 (complex enterprise SQL)—easy questions irrelevant
- Hard questions better separate model capabilities

### Sample Size: 200 Questions

Statistical power analysis for detecting 10% accuracy difference:
- α = 0.05, power = 80% → minimum ~150 samples needed
- 200 provides margin for subset analysis and edge cases
- Cost: ~$4/model at $0.02/question (GPT-4o/Claude rates)

### Balance: 100/100 Split

Equal hard/extra rather than proportional because:
- Extra-hard has unique challenges (set operations)
- Want sufficient sample of each for analysis
- Avoid underrepresenting hardest category

### Reproducibility: Seed 42 + Saved File

- Fixed seed ensures identical sampling across runs
- Questions saved to `evaluation/hard_extra_sample_200.json`
- Metadata includes seed, timestamp, counts

## Consequences

**Positive:**
- Fast model iteration (~$20 for 5-model comparison)
- Sufficient statistical power for 10% differences
- Fair comparison (same questions for all models)
- Reproducible by anyone with the saved file

**Trade-offs:**
- May miss regressions on easy/medium queries
- Not comparable to full Spider leaderboard numbers
- Cannot detect differences <8%
- Fixed sample may have unintended biases

**Mitigations:**
- Run full evaluation on final candidates if needed
- Document that metrics are for hard+extra subset
- Sample size large enough to average out biases
