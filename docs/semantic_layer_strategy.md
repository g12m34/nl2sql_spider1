# Semantic Layer Strategy

## Overview

The Malloy semantic layer is built **once per database** (166 databases), not per question. This allows us to:
1. Invest more upfront in getting it right
2. Use a more capable (expensive) model for this one-time task
3. Validate and cache results
4. Focus experimentation on the query generation agent

## What the Semantic Layer Should Contain

For each Spider database, we need a `.malloy` file with:

```malloy
// Example: concert_singer.malloy

source: singer is duckdb.table('singer') extend {
  // Primary key
  primary_key: Singer_ID

  // Dimensions (groupable fields)
  dimension:
    name is Name
    country is Country
    song_name is Song_Name
    release_year is Song_release_year
    is_male is Is_male

  // Measures (aggregations)
  measure:
    singer_count is count()
    avg_age is avg(Age)
    min_age is min(Age)
    max_age is max(Age)
}

source: stadium is duckdb.table('stadium') extend {
  primary_key: Stadium_ID

  dimension:
    name is Name
    location is Location

  measure:
    stadium_count is count()
    total_capacity is sum(Capacity)
    avg_capacity is avg(Capacity)
    max_capacity is max(Capacity)
}

source: concert is duckdb.table('concert') extend {
  primary_key: concert_ID

  dimension:
    concert_name is concert_Name
    theme is Theme
    year is Year

  // Join to stadium
  join_one: stadium on Stadium_ID = stadium.Stadium_ID

  measure:
    concert_count is count()
}

source: singer_in_concert is duckdb.table('singer_in_concert') extend {
  // Junction table for many-to-many
  join_one: singer on singer_ID = singer.Singer_ID
  join_one: concert on concert_ID = concert.concert_ID
}
```

## Generation Strategy

### Phase 1: Create Exemplar Models (Manual)

Hand-craft Malloy models for 5-10 diverse databases:

| Database | Complexity | Why Include |
|----------|------------|-------------|
| concert_singer | Simple | Basic joins, measures |
| pets_1 | Simple | Single table |
| car_1 | Medium | Multiple tables, FKs |
| flight_2 | Medium | Date handling |
| world_1 | Complex | Many tables, aggregations |
| college_2 | Complex | Multiple join paths |
| hr_1 | Complex | Self-referential joins |

These serve as few-shot examples and validation targets.

### Phase 2: Generate Remaining Models

**Prompt structure:**
```
You are an expert in Malloy, a semantic modeling language.

Given a SQL schema, generate a complete Malloy source file that includes:
1. Source definitions for each table
2. Primary keys where identifiable
3. Dimensions for all columns (with readable names)
4. Measures for numeric columns (count, sum, avg, min, max as appropriate)
5. Join relationships based on foreign keys
6. Comments explaining non-obvious relationships

## Examples
[Include 3-5 exemplar models]

## SQL Schema to Convert
[Insert schema from tables.json]

## Output
Generate only the .malloy file content, no explanations.
```

**Model choice:** Claude Sonnet 4.5 or Opus 4.5
- This is a one-time cost (~$1-2 total)
- Quality matters more than cost here
- Better to get it right than iterate

### Phase 3: Validate with Malloy Compiler

```bash
# For each generated .malloy file
malloy compile path/to/schema.malloy

# If errors, feed back to LLM for correction
```

Validation loop:
1. Attempt compilation
2. If error, send error message + original file to LLM
3. Get corrected version
4. Repeat until valid (max 3 attempts)
5. Flag for human review if still failing

### Phase 4: Smoke Test with Sample Queries

For each database, run 2-3 simple queries to verify:
- Sources load correctly
- Joins work as expected
- Measures compute properly

```malloy
// Smoke test queries
run: singer -> { aggregate: singer_count }
run: concert -> { group_by: year; aggregate: concert_count }
run: singer_in_concert -> {
  group_by: singer.country
  aggregate: concert.concert_count
}
```

## Cost Estimate

| Phase | Model | Est. Cost |
|-------|-------|-----------|
| Generate 166 schemas | Sonnet 4.5 | $1.50 |
| Validation fixes (~30% need retry) | Sonnet 4.5 | $0.50 |
| Smoke test queries | Haiku 4.5 | $0.20 |
| **Total** | | **~$2.20** |

This is negligible compared to query generation experiments.

## File Structure

```
malloy/
├── sources/
│   ├── concert_singer.malloy
│   ├── pets_1.malloy
│   ├── car_1.malloy
│   └── ... (166 files)
├── exemplars/
│   ├── simple_example.malloy
│   ├── medium_example.malloy
│   └── complex_example.malloy
└── validation/
    ├── smoke_tests.malloy
    └── validation_results.json
```

## Advantages of This Approach

1. **One-time cost**: ~$2 vs. $5-50 for query experiments
2. **Cacheable**: Generate once, use forever
3. **Verifiable**: Compiler catches syntax errors
4. **Improvable**: Can refine semantic layer based on query failures
5. **Separates concerns**: Query agent only needs to write Malloy queries, not understand raw schemas

## Query Agent Focus

With the semantic layer pre-built, the query agent's job simplifies to:

**Input:**
- User question: "What is the average age of French singers?"
- Available sources: `singer`, `stadium`, `concert`, `singer_in_concert`
- Source definitions (dimensions, measures, joins)

**Output:**
```malloy
run: singer -> {
  where: country = 'France'
  aggregate: avg_age
}
```

This is much simpler than having the agent also figure out:
- Table relationships
- Column types
- Appropriate aggregations
- Join conditions

## Next Steps

1. [ ] Install Malloy CLI for validation
2. [ ] Create 5-10 exemplar Malloy models manually
3. [ ] Write generation script with validation loop
4. [ ] Generate all 166 database models
5. [ ] Run smoke tests
6. [ ] Begin query agent experiments

---

*This strategy allows us to focus experimentation budget on the query generation agent, where the real cost/performance tradeoffs matter.*
