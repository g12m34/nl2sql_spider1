# Reasoning Traces Experiment Report

*Generated: 2026-01-12*

## Executive Summary

This experiment tested whether providing pre-computed reasoning traces to LLMs improves their Malloy code generation accuracy. **The results were surprising: reasoning traces generally DECREASED performance.**

## Experiment Design

### Hypothesis
Providing detailed reasoning traces (tables needed, join paths, filters, aggregation strategies) in the prompt would help LLMs generate more accurate Malloy queries.

### Methodology
1. Created 100 reasoning traces for the hard/extra test set
2. Each trace includes:
   - Goal: What the question asks
   - Tables needed: Which tables to query
   - Join path: How to connect tables
   - Filters: What conditions to apply
   - Aggregation: Group by, measures, ordering, limits
   - Malloy approach: Strategy for writing the query
3. Added traces to prompts via new "reasoning" prompt mode
4. Evaluated on same 100 hard/extra questions

### Prompt Comparison: Baseline vs Reasoning Traces

Both prompts include the same:
1. Malloy Syntax Reference (200+ lines of syntax rules and patterns)
2. Full Semantic Layer (400+ lines of Malloy source definitions)

**The key difference is in the question/instruction section.**

#### BASELINE PROMPT (V3 - No Reasoning Trace)
Used in V3 evaluation that achieved 60% accuracy with Gemini Flash:

```
## Instructions

Generate a Malloy query. Use source names and field names exactly as defined in the semantic layer.
Return ONLY the query - no explanation, no markdown code blocks.

## Semantic Layer

[... 400+ lines of Malloy source definitions ...]

## Question

who is the most cited author at CVPR ?

## Query
```

**Total prompt tokens: ~4,500**

#### REASONING TRACE PROMPT (This Experiment)
Used in this experiment that achieved 46% accuracy with Gemini Flash:

```
## Available Sources: venue, author, journal, keyphrase, dataset, paper, cite, writes, paper_dataset, paper_keyphrase

## Semantic Layer

[... 400+ lines of Malloy source definitions ...]

## Question

who is the most cited author at CVPR ?

## Solution Strategy

Goal: Find the author whose CVPR papers have received the most citations
Tables needed: venue, paper, writes, author, cite
Join path: venue (CVPR) -> paper -> writes -> author, and paper -> cite (as cited_paper)
Filters: venue.venue_name = 'CVPR'
Aggregation: group by author.author_id, measure: count of citations (count citing papers via cite table where this paper is cited_paper_id), order: descending by citation count, limit: 1
Malloy approach: Start from paper, filter venue = CVPR, join to cite where paper is the cited paper, group by author via writes, count citations

## Instructions

Using the solution strategy above, generate the Malloy query. Use source names and field names exactly as defined in the semantic layer.
Output ONLY the Malloy query. No explanation. No markdown. Just the query starting with `run:`

## Query
```

**Total prompt tokens: ~4,700 (+200 for reasoning trace)**

#### Key Differences

| Aspect | Baseline | Reasoning Trace |
|--------|----------|-----------------|
| Instruction placement | Before semantic layer | After semantic layer |
| Question placement | At end | Before solution strategy |
| Solution guidance | None | Detailed 6-line strategy |
| Available sources | Not listed | Explicitly listed |
| Token count | ~4,500 | ~4,700 |

#### Why Reasoning Traces May Have Hurt

1. **Placed between question and code generation**: The model has to "skip over" the reasoning trace to get to generating code
2. **Generic table names vs Malloy sources**: Reasoning trace says "cite table" but Malloy has `cite`, `cite_base`, `cite_citing_paper`, `cite_cited_paper`
3. **Conflicting join paths**: Trace describes one approach, but semantic layer may enable simpler alternatives
4. **Instruction dilution**: "Using the solution strategy above" may have distracted from "Use source names exactly as defined"

## Results

### With Reasoning Traces (This Experiment)

| Model | Accuracy | Compile Rate |
|-------|----------|--------------|
| **Gemini 2.5 Pro** | **47.0%** | 55.0% |
| Gemini 2.5 Flash | 46.0% | 55.0% |
| GPT-5.2 | 43.0% | 52.0% |
| DeepSeek v3.2 | 42.0% | ~55% |
| GPT-5 mini | 14.1% | 45.5% |
| GPT-5.2 pro | Failed | - |

### Baseline (V3 - Without Reasoning Traces)

| Model | Accuracy |
|-------|----------|
| **Gemini 2.5 Flash** | **60.0%** |
| Gemini 2.5 Pro | 45.0% |
| DeepSeek v3.2 | 43.0% |

### Comparison: Reasoning vs Baseline

| Model | Baseline | With Reasoning | Change |
|-------|----------|----------------|--------|
| Gemini 2.5 Flash | 60.0% | 46.0% | **-14.0%** |
| Gemini 2.5 Pro | 45.0% | 47.0% | +2.0% |
| DeepSeek v3.2 | 43.0% | 42.0% | -1.0% |

## Analysis

### Key Finding: Reasoning Traces HURT Performance

For Gemini Flash, the best-performing model, reasoning traces **reduced accuracy by 14 percentage points** (60% → 46%). This is a significant degradation.

### Why Reasoning Traces May Have Failed

1. **Information Overload**: The additional context may have confused models rather than helped them
2. **Schema Mismatch**: Reasoning traces described tables/columns in generic terms that didn't always match exact Malloy source/field names
3. **Competing Instructions**: Models may have followed the reasoning trace even when it conflicted with the semantic layer definitions
4. **Prompt Length**: Longer prompts may have diluted the importance of the Malloy syntax reference

### GPT-5 mini Poor Performance

GPT-5 mini achieved only 14.1% accuracy with 26 execution errors. This suggests the model:
- Generates syntactically valid Malloy (45.5% compile rate)
- But produces logically incorrect queries
- May be over-relying on the reasoning trace rather than the semantic layer

### GPT-5.2 pro Failure

The GPT-5.2-pro model is not compatible with the chat completions endpoint and failed all requests.

## Error Analysis

### Error Breakdown by Type

| Model | Compile Errors | Logic Errors | Execution Errors |
|-------|----------------|--------------|------------------|
| Gemini Flash | 45 | 9 | 0 |
| Gemini Pro | 45 | 8 | 0 |
| GPT-5.2 | 48 | 9 | 0 |
| GPT-5 mini | 54 | 5 | 26 |
| DeepSeek | ~58 | - | - |

## Conclusions

1. **Reasoning traces do NOT improve performance**: For our best model (Gemini Flash), accuracy dropped 14 percentage points

2. **The "more context is better" assumption is wrong for this task**: LLMs perform better with just the semantic layer and question, without additional reasoning guidance

3. **Semantic layer quality is more important**: Previous experiments showed that fixing redundant aliases (+3-4% improvement) was more effective than adding reasoning traces

4. **GPT-5 mini is not suitable for this task**: 14.1% accuracy is far below other models

## Recommendations

1. **Do NOT use reasoning traces in production prompts**

2. **Focus on semantic layer quality**: Ensure dimensions, measures, and joins are clearly documented

3. **Keep prompts focused**: The Malloy syntax reference + semantic layer + question is sufficient

4. **Continue using Gemini Flash**: Best cost/performance ratio at 60% accuracy (without reasoning traces)

## Files

- Reasoning traces: `evaluation/reasoning_traces_hard_extra.json`
- GPT batch client: `scripts/openai_batch.py`
- Updated run_evaluation.py with reasoning mode
- Evaluation results in `evaluation/batch_jobs/`

## Future Work

1. Test selective reasoning traces (only for complex INTERSECT/EXCEPT queries)
2. Test different trace formats (more concise vs more detailed)
3. Test few-shot examples instead of reasoning traces
