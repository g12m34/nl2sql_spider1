# Error Analysis - Experiment 2 (Expert Layers)

**Date:** 2025-01-11
**Model:** deepseek-v3.2
**Questions:** 20
**Accuracy:** 25% (5/20)

## Error Categories

### 1. Schema Linking Errors (7/15 errors = 47%)
LLM generates queries referencing sources/fields that don't exist in the semantic layer.

| Error | Question | Issue |
|-------|----------|-------|
| 'author' is not defined | scholar | LLM used `author` but layer has `author_base` |
| 'activity' is not defined | activity_1 | LLM used `activity` but needs proper source |
| 'paper' is not defined | scholar (x3) | LLM can't find paper source |
| 'length' is not defined | geo | LLM used `length` but field name differs |
| Unknown field 'density' | geo | Field exists but not in output space |
| Unknown field 'population' | geo | Field exists but pipeline issue |
| Unknown field 'max_area' | geo | Aggregate not available |

**Hypothesis:** The LLM isn't correctly reading the source names from the semantic layer. Need to:
- Make source names more prominent
- Add explicit "Available sources: X, Y, Z" section
- Use consistent naming (avoid `_base` suffix confusion)

### 2. Syntax Errors (6/15 errors = 40%)
LLM generates invalid Malloy syntax.

| Error | Question | Issue |
|-------|----------|-------|
| missing '(' at 'movie_director' | movie_1 (x2) | Parse error in layer itself? |
| extraneous input '=' | gas_company, manufactory | Assignment syntax wrong |
| missing DAY, HOUR... | customers | Wrong aggregate filter syntax |
| Joins in queries deprecated | geo | Used inline join instead of source join |

**Hypothesis:**
- The prompt's Malloy syntax guide is incomplete
- Need examples of what NOT to do
- Constrained decoding could help enforce structure

### 3. Logic/Semantic Errors (2/15 = 13%)
Query compiles but produces wrong results.

- activity_1 Q18: returned wrong data

**Hypothesis:** LLM understands syntax but misunderstands the question or schema relationships.

## Top 3 Actionable Fixes

1. **Fix Schema Linking** (biggest impact)
   - Add "USE THESE SOURCES:" section with explicit source names
   - Remove `_base` suffix confusion - use only full source names
   - List available dimensions/measures per source

2. **Improve Syntax Guide**
   - Add "DO NOT" examples
   - Show correct aggregate filter syntax with `{ where: }` not `filter(where:)`
   - Clarify pipeline vs single-stage queries

3. **Add Chain-of-Thought**
   - Have LLM first identify which source to use
   - Then list which fields are needed
   - Finally write the query

## Next Steps
1. Update prompt with explicit source listing
2. Test syntax guide improvements
3. Implement chain-of-thought approach
