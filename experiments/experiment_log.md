# Experiment Log

## Experiment 0: Baseline
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Questions:** 46 (from 10 enriched databases)
**Malloy Layers:** `/malloy/full/` (original)

### Results
- Accuracy: 8.7% (4/46)
- Errors: 40 compile errors

### Passing Questions
1. game_1: "What are the ids of all students who played video games and sports?"
2. behavior_monitoring: "What are the line 1 of addresses shared by some students and teachers?"
3. movie_1: "What is the average number of stars that each reviewer gave?"
4. geo: "what is the capital of the state with the most inhabitants?"

---

## Experiment 1: Heuristic Enrichment
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Questions:** 46
**Malloy Layers:** `/malloy/full_enriched/` (auto-generated descriptions)

### Changes
- Added field metadata comments (sample values, types)
- Added heuristic-based descriptions (PK, FK, categorical, etc.)

### Results
- Accuracy: 17.4% (8/46)
- Errors: 34 compile errors
- **Improvement: +100% (2x)**

### New Passing Questions
5. ship_1: "What are the ranks of captains that are both in Cutter and Armed schooner classes?"
6. geo: "what is the tallest mountain in the united states?"
7. movie_1: "What are the movie titles with the highest average rating?"
8. geo: "what is the largest city in wyoming?"
9. game_1: "Show student ids who are on scholarship and have most hours per week"

---

## Experiment 2: Expert Semantic Layers
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Questions:** 20
**Malloy Layers:** `/malloy/expert/` (manually crafted)

### Changes
- Detailed semantic descriptions for each field
- Relationship explanations
- Sample values in comments
- Fixed reserved word issues (`year`, `name` need backticks)

### Results (Standard Prompt)
- Accuracy: 25% (5/20)
- Improvement from heuristic: minimal

### Key Finding
Expert descriptions alone don't significantly help. The main issues are:
1. LLM still uses wrong source/field names
2. Syntax errors (wrong filter patterns)

---

## Experiment 3: Enhanced Prompt Mode
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Questions:** 10, 20
**Prompt Mode:** Enhanced (explicit source listing)

### Changes
- Added "Available Sources: X, Y, Z" prominently in prompt
- Clearer "DO / DO NOT" syntax rules
- Explicit instruction to output ONLY the query

### Results
- 10 questions: 40% (4/10)
- 20 questions: 20% (4/20)

### Key Finding
Explicit source listing helps on small tests but doesn't scale. LLM still struggles with:
- Schema linking (using wrong source names)
- Filter syntax (using SQL patterns)

---

## Experiment 4: Chain-of-Thought Mode
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Questions:** 10
**Prompt Mode:** CoT (internal reasoning before query)

### Changes
- Prompt asks model to think through: source selection, fields, pipeline needs
- Instruction to NOT write reasoning, just use it internally

### Results
- Accuracy: 40% (4/10)
- Same as enhanced mode

### Key Finding
Internal CoT doesn't help more than explicit source listing. The model's errors are mostly:
1. Wrong source/field names (schema linking)
2. Invalid Malloy syntax patterns

---

## Experiment 5: Fixed Filtered Aggregate Syntax
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Prompt Mode:** Enhanced with improved syntax guide

### Changes
Added CRITICAL clarification to prompt:
- CORRECT: `count() { where: field = 'value' }` - filter AFTER function
- WRONG: `joined { where: x = 'y' }.count()` - filter BEFORE function

### Results
- 10 questions: **60% (6/10)** - up from 40%
- 20 questions: **35% (7/20)** - up from 20%
- 46 questions: **19.6% (9/46)** - up from 8.7% baseline

### Key Finding
Fixing the filtered aggregate syntax pattern was the biggest single improvement.
Went from 8.7% -> 19.6% = **125% relative improvement**

---

## Current Best Configuration
- **Layers:** Expert (`/malloy/expert/`)
- **Prompt:** Enhanced mode with fixed syntax guide
- **Accuracy:** 19.6% on 46 questions (up from 8.7% baseline)

## Summary of All Experiments

| Experiment | 10 Q | 20 Q | 46 Q | Notes |
|------------|------|------|------|-------|
| Baseline (original) | 20% | - | 8.7% | Starting point |
| Heuristic enrichment | 30% | - | 17.4% | +100% |
| Expert + standard | - | 25% | - | Manual descriptions |
| Expert + enhanced | 40% | 20% | - | Added source listing |
| Expert + CoT | 40% | - | - | Chain-of-thought |
| **Expert + fixed syntax** | **60%** | **35%** | **19.6%** | **Best so far** |

## Remaining Error Categories
1. **Schema Linking** (~60%): LLM uses wrong source/field names
   - 'venue', 'activity', 'paper', 'keyphrase', 'length' not defined
2. **Malloy-Specific Errors** (~30%):
   - "Cannot use scalar field in aggregate"
   - "Joins in queries deprecated"
3. **Logic Errors** (~10%): Compiles but wrong results

---

## Research: Constrained Decoding
**Date:** 2025-01-11

### Overview
Constrained decoding (grammar-guided generation) forces LLM outputs to conform to a specified grammar, potentially eliminating syntax errors entirely.

### Relevant Tools & Papers
1. **Outlines** - Open-source library for structured generation with O(1) valid token lookup
2. **Guidance** - Microsoft's constrained generation framework
3. **XGrammar** - Grammar-constrained decoding engine
4. **CRANE** (2024) - Reasoning-aware constrained decoding
5. **IterGen** (2024) - Iterative structured output generation

### Feasibility for NL2Malloy
- **Challenge**: We're using DeepSeek's API, not local models
- **Option 1**: Implement grammar constraints server-side (complex, requires model access)
- **Option 2**: Post-process outputs with grammar validation and retry
- **Option 3**: Use DeepSeek's JSON mode or similar structured output features

### Recommendation
Constrained decoding would be highly effective but requires either:
- Local model deployment (expensive, slow)
- API-level grammar support (not available on DeepSeek)

For now, focus on prompt engineering. Consider constrained decoding for production with different model hosting.

---

## Experiment 6: Entity Lookup Pattern & Layer Fixes
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Prompt Mode:** Enhanced with entity lookup guidance

### Changes
1. Fixed nested join paths in activity_1.malloy (student -> participates_in -> activity)
2. Added explicit dimension declarations in geo.malloy (river_length, state_density, etc.)
3. Added "Entity Lookup Pattern" guidance:
   - "what is the tallest mountain" should return the NAME, not max(height)
   - Use `order_by: field desc; limit: 1` pattern for finding entities by max/min

### Results
- 46 questions: **21.7% (10/46)** - up from 19.6%
- Errors dropped from 31 to 27 (more queries compile), then back to 32

### Key Finding
Entity lookup guidance helped with some questions. Main remaining issues:
- Schema linking still dominant (~50% of errors)
- Some queries compile but return wrong structure (aggregate vs entity)

---

## Experiment 7: Order_by Output Space Requirement
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Prompt Mode:** Enhanced with order_by guidance

### Changes
Discovered CRITICAL Malloy rule: fields used in `order_by:` MUST be in the output space (select/group_by).

Updated prompt guidance:
- WRONG: `select: name; order_by: height desc` - height not in output
- CORRECT: `select: name, height; order_by: height desc`

### Results
- 46 questions: **50.0% (23/46)** - up from 21.7%
- Errors: 19 (down from 32)
- **Relative improvement: +475% from baseline (8.7%)**

### Key Finding
This single rule fix caused a massive improvement. The LLM was generating many queries that had the right logic but failed on this technical Malloy requirement.

---

## Experiment 8: No Subqueries + Count Deprecation
**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Prompt Mode:** Enhanced

### Changes
Added "DO NOT" guidance:
- `run:` inside another query (NO SUBQUERIES) - use pipelines instead
- `count(distinct field)` - DEPRECATED, use `count(field)` instead

### Results
- 46 questions: **54.3% (25/46)** - up from 50.0%
- Errors: 18 (down from 19)
- **Relative improvement: +524% from baseline (8.7%)**

### Remaining Error Categories
- 8x: Schema linking (field not defined)
- 2x: Scholar database join paths
- 2x: Nested run: subquery attempts (still happening)
- 2x: Order_by not in output
- 4x: Other syntax/internal errors

### Final Analysis
The biggest wins came from:
1. **Order_by output requirement** - single biggest fix (+28% accuracy)
2. **Filtered aggregate syntax** - `count() { where: }` not `{ where: }.count()`
3. **Entity lookup pattern** - return name not max(value)

Remaining issues are primarily schema linking (wrong field/source names) which require database-specific knowledge or better semantic layer design.

---

## Summary of All Experiments

| Experiment | Accuracy | Improvement |
|------------|----------|-------------|
| Baseline (original) | 8.7% | - |
| Heuristic enrichment | 17.4% | +100% |
| Expert layers | 19.6% | +125% |
| Entity lookup + fixes | 21.7% | +150% |
| Order_by output rule | 50.0% | +475% |
| No subqueries + deprecation | **54.3%** | **+524%** |

### Key Learnings

1. **Malloy-specific syntax rules are critical** - Many errors came from SQL-like patterns that don't work in Malloy
2. **Order_by requires output fields** - This single rule caused ~25% accuracy gain
3. **Filtered aggregates syntax** - `func() { where: }` not `{ where: }.func()`
4. **Schema linking remains the biggest challenge** - LLM still hallucinates field names
5. **Expert semantic layers help but aren't sufficient** - Need good prompts too

---
