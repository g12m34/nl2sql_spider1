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

## Current Best Configuration
- **Layers:** Expert (`/malloy/expert/`)
- **Prompt:** Enhanced or CoT (both ~40% on 10 questions)
- **Accuracy:** ~20-25% on larger sets

## Top Error Categories (to fix)
1. **Schema Linking** (47%): Wrong source/field names
2. **Syntax Errors** (40%): Missing brackets, wrong filter syntax
3. **Logic Errors** (13%): Compiles but wrong results

---
