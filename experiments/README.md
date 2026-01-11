# NL2Malloy Optimization Experiments

This directory tracks experiments to improve NL2Malloy accuracy.

## Current Status

| Experiment | Accuracy | Notes |
|------------|----------|-------|
| Baseline (original layers) | 8.7% (4/46) | Starting point |
| Heuristic enrichment | 17.4% (8/46) | +100% improvement |
| Expert + fixed syntax | 19.6% (9/46) | +125% from baseline |
| Entity lookup + layer fixes | 21.7% (10/46) | +150% from baseline |
| Order_by output requirement | 50.0% (23/46) | +475% from baseline |
| No subqueries + count deprecation | 54.3% (25/46) | +524% from baseline |
| Nested join path fixes | 56.5% (26/46) | +549% from baseline |
| Deep join paths (keyphrase, highlow, student) | 63.0% (29/46) | +624% from baseline |
| count(joined.field) fix | 60.9% (28/46) | LLM variance |
| **Gold SQL bug fixes (Q6, Q162)** | **65.2% (30/46)** | **+649% from baseline** |

## Cross-Model Comparison

See [cross_model_analysis.md](cross_model_analysis.md) for detailed error analysis.

| Model | Compile Rate | Execution Accuracy | Cost |
|-------|--------------|-------------------|------|
| **Gemini 3 Flash** | **95.7%** | **80.4% (37/46)** | 50% batch discount |
| **Gemini 3 Pro** | 91.3% | **80.4% (37/46)** | 50% batch discount |
| Claude Sonnet 4.5 | 82.6% | 71.7% (33/46) | 50% batch discount |
| DeepSeek v3.2 | 73.9% | 65.2% (30/46) | Very cheap |
| Gemini 2.5 Pro | 78.3% | 65.2% (30/46) | 50% batch discount |
| Claude Opus 4.5 | 73.9% | 63.0% (29/46) | 50% batch discount |
| Gemini 2.5 Flash | 71.7% | 60.9% (28/46) | 50% batch discount |

**Key Insights:**
- **Gemini 3 Flash** ties with Gemini 3 Pro at 80.4% accuracy but has best compile rate (95.7%)
- 5 questions still fail ALL models (systematic issues)
- With targeted improvements, we estimate potential to reach **90%+ accuracy**

## Extended Test Sets

See [extended_test_report.md](extended_test_report.md) for detailed analysis.

| Test Set | Questions | Compile Rate | Accuracy | Notes |
|----------|-----------|--------------|----------|-------|
| Original (curated) | 44 | 95.7% | 88.6% | Hand-selected, 2 skipped |
| Hard/Extra | 100 | 82.0% | 65.0% | Only hard/extra difficulty |
| Stratified | 100 | 87.0% | 75.0% | Proportional sample |

**Accuracy by Difficulty (Stratified Set):**
| Difficulty | Accuracy |
|------------|----------|
| Easy | 89.5% |
| Medium | 80.0% |
| Hard | 37.5% |
| Extra | 22.2% |

## Experiment Plan

### Phase 1: Expert Semantic Layer Enrichment
- [ ] Manually enrich 10 test databases with expert descriptions
- [ ] Add meaningful column descriptions, relationships, common query patterns
- [ ] Test and measure improvement

### Phase 2: Error Analysis & Categorization
- [ ] Analyze all errors from Phase 1
- [ ] Categorize by error type (syntax, schema linking, logic, etc.)
- [ ] Identify top 3-5 error patterns

### Phase 3: Targeted Prompt Improvements
- [ ] Form hypotheses for each error category
- [ ] Test prompt modifications iteratively
- [ ] Document what works and what doesn't

### Phase 4: Advanced Techniques
- [ ] Chain-of-thought reasoning (think before coding)
- [ ] Constrained decoding exploration
- [ ] Malloy documentation integration

## Test Databases (10)

1. game_1 - Students, video games, sports
2. scholar - Academic papers, authors, venues
3. movie_1 - Movies, ratings, reviewers
4. manufactory_1 - Products, manufacturers
5. ship_1 - Ships, captains
6. gas_company - Companies, gas stations
7. activity_1 - Students, faculty, activities
8. geo - US geography (states, rivers, mountains)
9. customers_and_products_contacts - E-commerce
10. behavior_monitoring - Schools, students, teachers

## Budget

- DeepSeek v3.2: ~$0.01 per 46 questions
- Gemini Batch API: 50% discount vs real-time API
- Total spent so far: ~$0.03
- Budget remaining: Unlimited (very cheap!)

## Gemini Batch API

For testing with frontier models at reduced cost, use the Gemini Batch API:

```bash
# Submit batch job
python scripts/gemini_batch.py submit --model gemini-2.5-pro

# Check status
python scripts/gemini_batch.py status <job_name>

# Wait for completion (polls automatically)
python scripts/gemini_batch.py wait <job_name>

# Get results
python scripts/gemini_batch.py results <job_name>

# Evaluate results
python scripts/gemini_batch.py evaluate results_<job_name>.json

# List all jobs
python scripts/gemini_batch.py list
```

Available models: `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-pro-preview`, `gemini-3-flash-preview`

## Anthropic Batch API

For Claude models at 50% discount:

```bash
# Submit batch job
python scripts/anthropic_batch.py submit --model sonnet  # or opus, haiku

# Check status / wait / evaluate (same as Gemini)
python scripts/anthropic_batch.py status <batch_id>
python scripts/anthropic_batch.py wait <batch_id>
python scripts/anthropic_batch.py evaluate results_anthropic_<batch_id>.json
```

## Opik Experiment Tracking

We use [Opik by Comet](https://www.comet.com/site/products/opik/) to track experiments over time:

```bash
# Log all experiment results to Opik
python scripts/opik_tracker.py
```

View results at: https://www.comet.com/opik
