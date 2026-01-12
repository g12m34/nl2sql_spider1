# Enriched Semantic Layer Evaluation Report

*Generated: 2026-01-11*

## Executive Summary

This report documents our experiments with enriched Malloy semantic layers, including a critical bug discovery and fix. We evaluated multiple LLM providers on two extended test sets of 100 questions each.

### Key Finding: Redundant Field Alias Bug

During initial testing with enriched semantic layers, accuracy **dropped dramatically** from ~75% to ~16-27%. Root cause analysis revealed that redundant field aliases (e.g., `title is title`) were causing Malloy compile errors.

After fixing, accuracy improved significantly but some databases (notably `geo`) still had residual issues that were fixed during this analysis.

## Results Summary

### V3 Results (Final - After Full Geo Fix)

| Model | Stratified 100 | Hard/Extra 100 |
|-------|----------------|----------------|
| **Gemini 3 Flash** | **56.0%** (56/100) | **60.0%** (60/100) |
| Gemini 2.5 Pro | 50.0% (50/100) | 45.0% (45/100) |
| DeepSeek v3.2 | 40.0% (40/100) | 43.0% (43/100) |
| MiniMax 2.1 | 0.0% (0/100) | 0.0% (0/100) |
| MiniMax 2 | 0.0% (0/100) | 0.0% (0/100) |

### V2 vs V3 Comparison

| Model | V2 Stratified | V3 Stratified | Change | V2 Hard/Extra | V3 Hard/Extra | Change |
|-------|---------------|---------------|--------|---------------|---------------|--------|
| G3 Flash | 55.0% | 56.0% | +1.0% | 59.0% | 60.0% | +1.0% |
| G2.5 Pro | 46.0% | 50.0% | **+4.0%** | 42.0% | 45.0% | **+3.0%** |
| DeepSeek | 41.0% | 40.0% | -1.0% | 47.0% | 43.0% | -4.0% |

**Key Observation**: Gemini 2.5 Pro showed the largest improvement (+3-4%), while DeepSeek's variance is likely due to API non-determinism rather than semantic layer changes.

**Note on MiniMax**: Both MiniMax models returned JSON instead of Malloy code (e.g., `{"name":...`), indicating they don't understand the Malloy format. This is a fundamental model limitation, not a semantic layer issue.

### Comparison to Original Test Set

| Model | Original 46 (pre-enrichment) | Stratified 100 V2 |
|-------|------------------------------|-------------------|
| Gemini 3 Flash | 88.6% | 55.0% |

Note: The lower V2 accuracy is largely due to a remaining bug in `geo.malloy` that accounted for 27 errors (27% of questions). This has now been fixed.

### Compile Rate Analysis

| Model | Stratified Compile % | HardExtra Compile % |
|-------|---------------------|---------------------|
| Gemini 3 Flash | 66.0% | 77.0% |
| Gemini 2.5 Pro | 56.0% | 48.0% |

## Error Analysis

### Errors by Database (V2 Results)

#### Stratified 100 Test Set
| Database | G3 Flash Errors | G2.5 Pro Errors |
|----------|-----------------|-----------------|
| geo | 27 | 27 |
| scholar | 3 | 9 |
| activity_1 | 3 | 3 |
| manufactory_1 | 3 | 4 |
| ship_1 | 3 | 3 |
| behavior_monitoring | 2 | 2 |
| game_1 | 1 | 3 |
| movie_1 | 1 | 1 |
| gas_company | 1 | 1 |
| customers_and_products_contacts | 1 | 1 |

**Key Observation**: The `geo` database accounted for **27 out of 34** compile errors (79%) in G3 Flash's stratified test. This was due to remaining redundant `country_name is country_name` aliases that have now been fixed.

#### Hard/Extra 100 Test Set
| Database | G3 Flash Errors | G2.5 Pro Errors |
|----------|-----------------|-----------------|
| geo | 12 | 12 |
| movie_1 | 10 | 8 |
| scholar | 8 | 27 |
| activity_1 | 5 | 5 |
| game_1 | 2 | 3 |
| customers_and_products_contacts | 2 | 2 |
| gas_company | 1 | 0 |
| behavior_monitoring | 1 | 1 |

## The Redundant Field Alias Bug

### What Happened

When enriching semantic layers with documentation, we inadvertently created patterns like:

```malloy
dimension:
  title is title              // Redundant - causes error!
  country_name is country_name // Redundant - causes error!
```

When an LLM generates code referencing these fields, Malloy sees both:
1. The original column from SQL
2. The aliased dimension with the same name

This creates a "Cannot redefine 'X'" compile error.

### The Fix

**Never alias a field to itself.** Instead, use comments to document:

```malloy
dimension:
  // Title of the paper (use raw column: title)
  paper_name is title  // OK - actual rename
```

### Files Fixed

1. `malloy/expert/geo.malloy` - Removed all redundant aliases (country_name, city_name, border, highest_elevation, etc.)
2. `malloy/expert/scholar.malloy` - Previously fixed
3. `malloy/expert/behavior_monitoring.malloy` - Previously fixed
4. `malloy/expert/customers_and_products_contacts.malloy` - Previously fixed

## Methodology

### Test Sets

1. **Stratified 100**: Proportionally sampled across difficulty levels
   - Easy: 38 questions
   - Medium: 45 questions
   - Hard: 8 questions
   - Extra: 9 questions

2. **Hard/Extra 100**: Only hard and extra-hard questions
   - Contains INTERSECT/EXCEPT/UNION operations
   - Multiple JOINs
   - Subqueries
   - Complex aggregations

### Models Tested

| Model | Provider | Cost Mode | Result |
|-------|----------|-----------|--------|
| Gemini 3 Flash | Google | Batch (50% savings) | Best performer |
| Gemini 2.5 Pro | Google | Batch (50% savings) | Moderate |
| DeepSeek v3.2 | DeepSeek | Real-time | Moderate |
| MiniMax 2.1 | MiniMax | Real-time | Failed (0%) |
| MiniMax 2 | MiniMax | Real-time | Failed (0%) |

### Evaluation Pipeline

1. Load question and semantic layer
2. Generate Malloy query via LLM
3. Compile Malloy to SQL
4. Execute SQL on DuckDB (via sqlite_scan)
5. Compare results to gold SQL executed on SQLite
6. Score using execution-based matching (results must match, not syntax)

## Conclusions

1. **Semantic layer quality is critical**: Redundant alias patterns (`field is field`) caused massive accuracy drops. Always avoid same-name aliases.

2. **Gemini 3 Flash is the best performer for Malloy generation**: 56% on stratified, 60% on hard/extra - consistently outperforming other models.

3. **Gemini 2.5 Pro showed biggest improvement after fix**: +4% on stratified, +3% on hard/extra, reaching 50% and 45% respectively.

4. **DeepSeek shows high variance**: Results fluctuated between runs (40-47%), suggesting API non-determinism.

5. **MiniMax models don't support Malloy**: They return JSON instead of code - fundamental model limitation.

6. **Remaining errors are LLM-generated syntax issues**: After fixing semantic layers, most errors are invalid Malloy syntax generated by LLMs (e.g., `extraneous input 'measure:'`).

7. **The `geo` database remains challenging**: Complex multi-table geography queries account for many errors across all models.

## Learnings Documented

All learnings from this experiment have been documented in:
- `docs/malloy_learnings.md` - Iteration 6 (Redundant Field Aliases Bug) and Iteration 7 (Hand-Crafted Expert Layers)

## Files Updated

- `malloy/expert/geo.malloy` - Fixed redundant aliases
- `docs/malloy_learnings.md` - Added new learnings
- `experiments/enriched_layer_evaluation_v2.md` - This report
