# ADR-004: Reproducible Sampling with Fixed Seed

**Status:** Accepted

**Date:** 2025-01-11

## Context

When sampling 200 questions from the Spider train set, we need to ensure:
- Results can be reproduced by others
- Same questions used across all model evaluations
- Comparisons are fair (same test set for all)

## Decision

Use a fixed random seed (42) for all sampling operations and save the sampled questions to a JSON file.

## Rationale

1. **Reproducibility**: Anyone running the sampling script gets identical questions. Critical for:
   - Peer review and verification
   - Debugging evaluation issues
   - Comparing results across time

2. **Fair comparison**: All models evaluated on exactly the same questions. Random re-sampling would introduce variance.

3. **Transparency**: Published results can reference specific question IDs. Others can inspect which questions were used.

4. **Standard practice**: Seed 42 is conventional in ML research (hitchhiker's guide reference). Makes intent clear.

## Implementation

```python
# scripts/sample_hard_questions.py
RANDOM_SEED = 42

random.seed(RANDOM_SEED)
sampled_hard = random.sample(hard_questions, 100)
sampled_extra = random.sample(extra_questions, 100)
```

Output saved to `evaluation/hard_extra_sample_200.json` with metadata:

```json
{
  "metadata": {
    "random_seed": 42,
    "created": "2025-01-11T...",
    "hard_count": 100,
    "extra_count": 100
  },
  "questions": [...]
}
```

## Consequences

**Positive:**
- Fully reproducible sampling
- Questions persisted for future use
- Metadata documents provenance
- Easy to share exact evaluation set

**Negative:**
- Fixed sample may have unintended biases
- Cannot easily add questions without re-sampling
- Single seed means single sample (no bootstrap)

**Mitigations:**
- Sample size (200) large enough to average out biases
- Can create additional samples with different seeds if needed
- Saved file is source of truth (not re-running script)
