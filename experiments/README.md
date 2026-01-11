# NL2Malloy Optimization Experiments

This directory tracks experiments to improve NL2Malloy accuracy.

## Current Status

| Experiment | Accuracy | Notes |
|------------|----------|-------|
| Baseline (original layers) | 8.7% (4/46) | Starting point |
| Heuristic enrichment | 17.4% (8/46) | +100% improvement |

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
- Total spent so far: ~$0.03
- Budget remaining: Unlimited (very cheap!)
