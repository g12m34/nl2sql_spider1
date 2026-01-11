# NL2Malloy Cross-Model Error Analysis

*Generated: 2026-01-11 18:11 UTC*

## Executive Summary

This analysis compares the performance of 5 frontier LLMs on the NL2Malloy task:
converting natural language questions to Malloy queries using expert semantic layers.

### Overall Results

| Model | Compile Rate | Execution Accuracy | Accuracy Rank |
|-------|--------------|-------------------|---------------|
| Gemini 3 Pro | 91.3% (42/46) | 80.4% (37/46) | #1 |
| Claude Sonnet 4.5 | 82.6% (38/46) | 71.7% (33/46) | #2 |
| DeepSeek v3.2 | 73.9% (34/46) | 65.2% (30/46) | #3 |
| Gemini 2.5 Pro | 78.3% (36/46) | 65.2% (30/46) | #4 |
| Claude Opus 4.5 | 73.9% (34/46) | 63.0% (29/46) | #5 |
| Gemini 2.5 Flash | 71.7% (33/46) | 60.9% (28/46) | #6 |

### Key Findings

1. **Gemini 3 Pro** leads with 80.4% execution accuracy
2. **6 questions** failed across ALL models (systematic issues)
3. **28 unique questions** had at least one model fail

## Error Breakdown by Model

### DeepSeek v3.2

**Accuracy: 30/46 (65.2%)**

| Error Type | Count | Percentage |
|------------|-------|------------|
| compile | 12 | 26.1% |
| logic | 4 | 8.7% |

### Gemini 2.5 Flash

**Accuracy: 28/46 (60.9%)**

| Error Type | Count | Percentage |
|------------|-------|------------|
| compile | 13 | 28.3% |
| logic | 5 | 10.9% |

### Gemini 2.5 Pro

**Accuracy: 30/46 (65.2%)**

| Error Type | Count | Percentage |
|------------|-------|------------|
| compile | 10 | 21.7% |
| logic | 6 | 13.0% |

### Gemini 3 Pro

**Accuracy: 37/46 (80.4%)**

| Error Type | Count | Percentage |
|------------|-------|------------|
| logic | 5 | 10.9% |
| compile | 4 | 8.7% |

### Claude Sonnet 4.5

**Accuracy: 33/46 (71.7%)**

| Error Type | Count | Percentage |
|------------|-------|------------|
| compile | 8 | 17.4% |
| logic | 5 | 10.9% |

### Claude Opus 4.5

**Accuracy: 29/46 (63.0%)**

| Error Type | Count | Percentage |
|------------|-------|------------|
| compile | 12 | 26.1% |
| logic | 5 | 10.9% |

## Common Failure Analysis

### Questions Failed by ALL Models

These questions represent systematic challenges that no model could solve:

| Q# | Database | Question | Failed Models |
|----|----------|----------|---------------|
| 47 | activity_1 | What is the first and last name of the faculty members who p... | All (6) |
| 58 | geo | what rivers flow through the state with the largest populati... | All (6) |
| 91 | movie_1 | What are the ids of all moviest hat have not been reviewed b... | All (6) |
| 110 | movie_1 | What is the name of the movie that has been reviewed the mos... | All (6) |
| 150 | movie_1 | For each director, what are the titles and ratings for all t... | All (6) |
| 162 | activity_1 | What are the first names of the professors who do not play C... | All (6) |

### Questions with Mixed Results

Questions where some models succeeded and others failed (indicates model-specific strengths):

| Q# | Database | Question | Failed Models | Succeeded Models |
|----|----------|----------|---------------|------------------|
| 1 | scholar | who published the most at chi | DeepSeek v, Gemini 2.5, Claude Opu | Gemini 2.5, Gemini 3 P, Claude Son |
| 2 | movie_1 | What are the titles and directors of the... | DeepSeek v, Gemini 2.5, Gemini 2.5, Claude Son, Claude Opu | Gemini 3 P |
| 4 | ship_1 | What are the ranks of captains that are ... | Gemini 2.5, Gemini 2.5 | DeepSeek v, Gemini 3 P, Claude Son, Claude Opu |
| 5 | gas_company | Show all headquarters without a company ... | Gemini 2.5 | DeepSeek v, Gemini 2.5, Gemini 3 P, Claude Son, Claude Opu |
| 9 | behavior_monitoring | What are the line 1 of addresses shared ... | Claude Opu | DeepSeek v, Gemini 2.5, Gemini 2.5, Gemini 3 P, Claude Son |
| 28 | scholar | main topics of work by Brian DeRenzi | DeepSeek v, Gemini 2.5, Gemini 2.5, Claude Opu | Gemini 3 P, Claude Son |
| 32 | geo | what is the lowest point of all states t... | DeepSeek v | Gemini 2.5, Gemini 2.5, Gemini 3 P, Claude Son, Claude Opu |
| 35 | geo | what is the largest capital | Gemini 2.5 | DeepSeek v, Gemini 2.5, Gemini 3 P, Claude Son, Claude Opu |
| 40 | scholar | What is the most cited paper by ohad sha... | DeepSeek v, Gemini 2.5, Gemini 2.5, Claude Son, Claude Opu | Gemini 3 P |
| 59 | geo | where is the highest mountain of the uni... | Claude Son | DeepSeek v, Gemini 2.5, Gemini 2.5, Gemini 3 P, Claude Opu |
| 63 | movie_1 | What are the movie titles with the highe... | DeepSeek v, Gemini 2.5, Gemini 3 P | Gemini 2.5, Claude Son, Claude Opu |
| 64 | geo | what is the lowest point of the state wi... | DeepSeek v, Claude Son, Claude Opu | Gemini 2.5, Gemini 2.5, Gemini 3 P |
| 81 | geo | what states border the state with the sm... | DeepSeek v, Gemini 2.5, Claude Opu | Gemini 2.5, Gemini 3 P, Claude Son |
| 106 | game_1 | Show student ids who are on scholarship ... | Claude Son, Claude Opu | DeepSeek v, Gemini 2.5, Gemini 2.5, Gemini 3 P |
| 111 | geo | what is the capital of the state with th... | Gemini 2.5 | DeepSeek v, Gemini 2.5, Gemini 3 P, Claude Son, Claude Opu |

## Error Pattern Analysis

### Schema Linking (6 occurrences)

*Wrong field or source names used*

| Model | Count |
|-------|-------|
| DeepSeek v3.2 | 4 |
| Gemini 2.5 Flash | 1 |
| Gemini 2.5 Pro | 1 |

### Aggregation (17 occurrences)

*Incorrect aggregate function usage*

| Model | Count |
|-------|-------|
| Gemini 2.5 Pro | 6 |
| Claude Sonnet 4.5 | 3 |
| Claude Opus 4.5 | 3 |
| DeepSeek v3.2 | 2 |
| Gemini 2.5 Flash | 2 |
| Gemini 3 Pro | 1 |

### Other (66 occurrences)

*Logic errors or other issues*

| Model | Count |
|-------|-------|
| Gemini 2.5 Flash | 15 |
| Claude Opus 4.5 | 14 |
| DeepSeek v3.2 | 10 |
| Claude Sonnet 4.5 | 10 |
| Gemini 2.5 Pro | 9 |
| Gemini 3 Pro | 8 |

## Hypotheses for Improvement

Based on the error analysis, here are targeted hypotheses for improving accuracy.
Lift estimates are based on the number of questions that could be fixed by each improvement.

### H1: Enhanced Schema Linking Guidance

**Observation:** Schema linking errors are common, with models using incorrect field names.

**Hypothesis:** Adding explicit field name listings at the start of the prompt will reduce schema linking errors.

**Test:** Create a prompt variant that lists all available sources and their fields upfront.

**Potential Lift:** +3 questions (~6.5% absolute) → 87.0% accuracy

### H2: Join Path Examples

**Observation:** Nested join paths (e.g., `author.writes.paper.venue`) frequently cause errors.

**Hypothesis:** Including explicit examples of valid join paths in the semantic layer comments will help models navigate relationships.

**Test:** Add `// Valid paths: author.writes.paper.venue.venue_name` comments to semantic layers.

**Potential Lift:** +0 questions (~0.0% absolute) → 80.4% accuracy

### H3: Query Templates by Question Type

**Observation:** Certain question patterns (e.g., "find entities in BOTH X and Y", NOT IN queries) consistently fail across all models.

**Hypothesis:** Providing query templates for common patterns will improve accuracy on pattern-matching questions.

**Test:** Add more INTERSECT pattern examples, NOT EXISTS patterns, and other common query patterns to the prompt.

**Potential Lift:** +4 questions (~8.7% absolute) → 89.1% accuracy

*Note: 6 questions fail ALL models - these represent the highest-value targets.*

### H4: Chain-of-Thought for Complex Queries

**Observation:** Logic errors occur even when queries compile, suggesting reasoning failures.

**Hypothesis:** Requiring models to explicitly reason about the query structure before generating code will reduce logic errors.

**Test:** Add a chain-of-thought prompt that requires models to: 1) Identify the source, 2) List required fields, 3) Determine if aggregation is needed, 4) Write the query.

**Potential Lift:** +3 questions (~6.5% absolute) → 87.0% accuracy

### H5: Few-Shot Examples per Database

**Observation:** Some databases (e.g., `movie_1`, `scholar`) have higher error rates than others.

**Hypothesis:** Including 1-2 working query examples for each database in the prompt will improve accuracy.

**Test:** Add database-specific few-shot examples to the semantic layer files.

**Potential Lift:** +2 questions (~4.3% absolute) → 84.8% accuracy

### Combined Lift Estimate

If all hypotheses prove valid (with some overlap), potential combined accuracy:

**Current Best:** 37/46 (80.4%)

**Optimistic Target:** 46/46 (100.0%)

**Conservative Target:** 41/46 (89.1%)

## Model-Specific Observations

### Gemini 3 Pro

- **Compile Rate:** 91.3%
- **Logic Error Rate (of compiled):** 11.9%
- **Strength:** Strong understanding of Malloy syntax
- **Strength:** Good semantic understanding of queries

### Claude Sonnet 4.5

- **Compile Rate:** 82.6%
- **Logic Error Rate (of compiled):** 13.2%
- **Strength:** Strong understanding of Malloy syntax
- **Strength:** Good semantic understanding of queries

### DeepSeek v3.2

- **Compile Rate:** 73.9%
- **Logic Error Rate (of compiled):** 11.8%
- **Strength:** Good semantic understanding of queries
- **Weakness:** Struggles with Malloy syntax specifics

### Gemini 2.5 Pro

- **Compile Rate:** 78.3%
- **Logic Error Rate (of compiled):** 16.7%
- **Weakness:** Logic errors even on compilable queries

### Claude Opus 4.5

- **Compile Rate:** 73.9%
- **Logic Error Rate (of compiled):** 14.7%
- **Strength:** Good semantic understanding of queries
- **Weakness:** Struggles with Malloy syntax specifics

### Gemini 2.5 Flash

- **Compile Rate:** 71.7%
- **Logic Error Rate (of compiled):** 15.2%
- **Weakness:** Struggles with Malloy syntax specifics

## Conclusion

The analysis reveals that while frontier models can generate Malloy queries with reasonable accuracy,
systematic improvements are possible through:

1. **Better schema documentation** - Explicit field listings and join path examples
2. **Pattern templates** - Common query patterns like INTERSECT should be documented
3. **Chain-of-thought prompting** - Structured reasoning reduces logic errors
4. **Database-specific examples** - Few-shot learning improves accuracy

The fact that different models fail on different questions suggests that ensemble approaches
or model-specific prompt tuning could further improve results.

## Appendix: Raw Data

### All Failed Questions by Model

<details>
<summary>Gemini 3 Pro - 9 failures</summary>

| Q# | DB | Error Type | Error |
|----|----| -----------|-------|
| 47 | activity_1 | compile | error: Can't determine view type (`group_by` / `ag... |
| 58 | geo | compile | error: Unknown field state_population in output sp... |
| 63 | movie_1 | compile | error: Join path is required for this calculation;... |
| 91 | movie_1 | logic | N/A... |
| 110 | movie_1 | logic | N/A... |
| 124 | behavior_monitoring | logic | N/A... |
| 150 | movie_1 | logic | N/A... |
| 162 | activity_1 | logic | N/A... |
| 199 | geo | compile | error: Unknown field length in output space at lin... |

</details>

<details>
<summary>Claude Sonnet 4.5 - 13 failures</summary>

| Q# | DB | Error Type | Error |
|----|----| -----------|-------|
| 2 | movie_1 | compile | error: Cannot redefine 'rating' at line 6... |
| 40 | scholar | compile | error: extraneous input '.' expecting {AGGREGATE, ... |
| 47 | activity_1 | logic | N/A... |
| 58 | geo | compile | error: mismatched input '->' expecting {AND, DAY, ... |
| 59 | geo | compile | error: Unknown field mountain_altitude in output s... |
| 64 | geo | compile | error: Joins in queries are deprecated, move into ... |
| 91 | movie_1 | compile | error: Cannot use an aggregate field in a dimensio... |
| 106 | game_1 | compile | error: no viable alternative at input '``' at line... |
| 110 | movie_1 | logic | N/A... |
| 114 | movie_1 | logic | N/A... |
| 117 | scholar | compile | error: extraneous input '.' expecting {AGGREGATE, ... |
| 150 | movie_1 | logic | N/A... |
| 162 | activity_1 | logic | N/A... |

</details>

<details>
<summary>DeepSeek v3.2 - 16 failures</summary>

| Q# | DB | Error Type | Error |
|----|----| -----------|-------|
| 1 | scholar | compile | Malloy compile error: error: Unknown field chi_pap... |
| 2 | movie_1 | compile | Malloy compile error: error: Join path is required... |
| 28 | scholar | compile | Malloy compile error: error: 'keyphrase' is not de... |
| 32 | geo | compile | Malloy compile error: error: Joins in queries are ... |
| 40 | scholar | compile | Malloy compile error: error: 'cite_cited_paper' is... |
| 47 | activity_1 | logic | N/A... |
| 58 | geo | compile | Malloy compile error: error: extraneous input 'run... |
| 63 | movie_1 | compile | Malloy compile error: error: Join path is required... |
| 64 | geo | compile | Malloy compile error: error: Joins in queries are ... |
| 81 | geo | compile | Malloy compile error: error: Joins in queries are ... |
| 91 | movie_1 | logic | N/A... |
| 110 | movie_1 | logic | N/A... |
| 114 | movie_1 | compile | Malloy compile error: error: extraneous input '/' ... |
| 117 | scholar | compile | Malloy compile error: error: 'cite_cited_paper' is... |
| 150 | movie_1 | compile | Malloy compile error: error: 'movie' is not define... |
| 162 | activity_1 | logic | N/A... |

</details>

<details>
<summary>Gemini 2.5 Pro - 16 failures</summary>

| Q# | DB | Error Type | Error |
|----|----| -----------|-------|
| 1 | scholar | compile | error: Unknown field paper_count in output space a... |
| 2 | movie_1 | compile | error: Cannot use an aggregate field in a select o... |
| 4 | ship_1 | logic | N/A... |
| 5 | gas_company | compile | error: 'company' is not defined at line 3... |
| 28 | scholar | compile | error: Unknown field paper_count in output space a... |
| 35 | geo | compile | error: Unknown field population in output space at... |
| 40 | scholar | compile | error: extraneous input '.' expecting {AGGREGATE, ... |
| 47 | activity_1 | logic | N/A... |
| 58 | geo | compile | error: Unknown field population in output space at... |
| 63 | movie_1 | compile | error: Join path is required for this calculation;... |
| 91 | movie_1 | logic | N/A... |
| 110 | movie_1 | compile | error: Unknown field review_count in output space ... |
| 114 | movie_1 | logic | N/A... |
| 117 | scholar | compile | error: extraneous input '.' expecting {AGGREGATE, ... |
| 150 | movie_1 | logic | N/A... |
| 162 | activity_1 | logic | N/A... |

</details>

<details>
<summary>Claude Opus 4.5 - 17 failures</summary>

| Q# | DB | Error Type | Error |
|----|----| -----------|-------|
| 1 | scholar | compile | error: no viable alternative at input 'i' at line ... |
| 2 | movie_1 | compile | error: mismatched input 'extend' expecting {AND, D... |
| 9 | behavior_monitoring | compile | error: Aggregate expressions are not allowed in `w... |
| 28 | scholar | compile | error: Joins in queries are deprecated, move into ... |
| 40 | scholar | compile | error: no viable alternative at input 'i' at line ... |
| 47 | activity_1 | logic | N/A... |
| 58 | geo | compile | error: extraneous input 'run:' expecting {ALL, AVG... |
| 64 | geo | compile | error: Joins in queries are deprecated, move into ... |
| 81 | geo | compile | error: mismatched input '->' expecting {AND, DAY, ... |
| 91 | movie_1 | logic | N/A... |
| 106 | game_1 | compile | error: Joins in queries are deprecated, move into ... |
| 110 | movie_1 | compile | error: Cannot use an aggregate field in a select o... |
| 114 | movie_1 | logic | N/A... |
| 117 | scholar | compile | error: no viable alternative at input 'i' at line ... |
| 124 | behavior_monitoring | compile | error: Not legal in project query at line 3... |
| 150 | movie_1 | logic | N/A... |
| 162 | activity_1 | logic | N/A... |

</details>

<details>
<summary>Gemini 2.5 Flash - 18 failures</summary>

| Q# | DB | Error Type | Error |
|----|----| -----------|-------|
| 2 | movie_1 | compile | error: Join path is required for this calculation;... |
| 4 | ship_1 | logic | N/A... |
| 28 | scholar | compile | error: Not legal in grouping query at line 8... |
| 40 | scholar | compile | error: 'author' is not defined at line 2... |
| 47 | activity_1 | logic | N/A... |
| 58 | geo | compile | error: Unknown field population in output space at... |
| 81 | geo | compile | error: Unknown field state_area in output space at... |
| 91 | movie_1 | logic | N/A... |
| 110 | movie_1 | compile | error: Unknown field num_reviews in output space a... |
| 111 | geo | compile | error: Unknown field state_population in output sp... |
| 114 | movie_1 | logic | N/A... |
| 117 | scholar | compile | error: extraneous input '.' expecting {AGGREGATE, ... |
| 136 | geo | compile | error: Unknown field max_river_length in output sp... |
| 150 | movie_1 | compile | error: extraneous input '.' expecting {AGGREGATE, ... |
| 162 | activity_1 | logic | N/A... |
| 180 | geo | compile | error: Unknown field population in output space at... |
| 185 | geo | compile | error: Unknown field population in output space at... |
| 199 | geo | compile | error: Unknown field river_length in output space ... |

</details>
