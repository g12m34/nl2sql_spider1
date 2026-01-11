# ADR-002: Sample Size of 200 Questions

**Status:** Accepted

**Date:** 2025-01-11

## Context

After deciding to focus on hard+extra questions (ADR-001), we needed to determine how many questions to sample for evaluation. Key considerations:

- **Statistical power**: Ability to detect meaningful differences between models
- **Cost**: API costs scale linearly with question count
- **Available data**: 1,801 hard + 510 extra = 2,311 questions in Spider train

## Decision

Sample 200 questions total: 100 hard + 100 extra-hard (balanced).

## Rationale

### Statistical Power Analysis

To detect a 10% accuracy difference between models with:
- Significance level (α): 0.05
- Statistical power: 80%
- Two-proportion z-test

Required sample size: ~150 questions minimum

We chose 200 to provide margin for:
- Subset analysis by difficulty (hard vs extra)
- Potential invalid questions or execution errors
- Slightly smaller effect sizes (can detect ~8% differences)

### Cost Analysis

Estimated costs per model (at ~$0.02/question for GPT-4o/Claude):

| Sample Size | Cost per Model | 5 Models |
|-------------|----------------|----------|
| 100 | $2 | $10 |
| 200 | $4 | $20 |
| 500 | $10 | $50 |
| 1000 | $20 | $100 |

200 questions provides good statistical power at minimal cost.

### Balance Between Difficulties

Equal split (100/100) rather than proportional (78%/22%) because:
- Extra-hard questions have unique challenges (set operations)
- Want sufficient sample of each type for analysis
- Avoid underrepresenting the hardest category

## Consequences

**Positive:**
- Sufficient statistical power to detect 10% differences
- Low cost (~$20 for 5-model comparison)
- Balanced representation of hard and extra categories
- Fast iteration cycle

**Negative:**
- Cannot detect very small differences (<8%)
- Limited database coverage (87 of 160+ databases)
- May need larger sample for final publication

**Future consideration:**
- Scale up to 500-1000 for final model selection if needed
