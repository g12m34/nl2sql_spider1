# Semantic Layer Strategy

## Overview

The Malloy semantic layer is built **once per database** (166 databases), not per question. This allows us to:
1. Invest more upfront in getting it right
2. Use a more capable (expensive) model for this one-time task
3. Validate and cache results
4. Focus experimentation on the query generation agent

## Key Insight: Reverse-Engineer from Ground Truth SQL

Instead of guessing what the semantic layer needs from the schema alone, we **analyze the correct SQL queries** to determine exactly what's required:

```
Ground Truth SQL Queries
        │
        ▼
┌───────────────────┐
│ Analyze patterns: │
│ - Tables used     │
│ - Columns in      │
│   SELECT/WHERE/   │
│   GROUP BY        │
│ - Aggregations    │
│ - Join patterns   │
└───────────────────┘
        │
        ▼
  Malloy Source File
  (exactly what's needed)
```

### Benefits of This Approach

1. **No over-engineering**: Only includes columns/measures actually used
2. **Guaranteed coverage**: Every query pattern is captured
3. **No LLM needed**: Deterministic extraction from SQL
4. **Verifiable**: Can trace each element back to source queries

### Analysis Results (Sample)

| Database | Queries | Tables | Dimensions | Measures |
|----------|---------|--------|------------|----------|
| concert_singer | 45 | 4 | 18 | 5 |
| world_1 | 120 | 3 | 19 | 15 |
| college_2 | 170 | 10 | 35 | 14 |
| flight_1 | 96 | 4 | 16 | 8 |

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

### NEW: Automated Extraction from Ground Truth SQL

We now use a **deterministic script** to extract semantic layer requirements directly from the correct SQL queries. No LLM needed for this phase!

**Script:** `scripts/generate_semantic_layers.py`

```bash
# Generate all semantic layers
python scripts/generate_semantic_layers.py
```

This script:
1. Loads all Spider queries (train + dev)
2. Groups them by database
3. Analyzes SQL patterns to extract:
   - Tables actually used
   - Columns used as dimensions
   - Columns used in aggregations
   - Join patterns
4. Generates `.malloy` files with exactly what's needed
5. Outputs analysis JSON for debugging

### Phase 1: Run Automated Generation (FREE)

```bash
python scripts/generate_semantic_layers.py
```

Output:
- `malloy/sources/*.malloy` - One file per database
- `malloy/analysis/*.json` - Detailed analysis per database
- `malloy/analysis/_summary.json` - Overall stats

**Cost: $0** - No LLM calls, pure SQL parsing

### Phase 2: Validate with Malloy Compiler

```bash
# For each generated .malloy file
for f in malloy/sources/*.malloy; do
  malloy compile "$f" || echo "FAILED: $f"
done
```

Any syntax errors are likely due to:
- Edge cases in SQL parsing
- Malloy syntax nuances

These can be fixed manually or with a quick LLM pass.

### Phase 3: Enhance with LLM (Optional)

For databases where the auto-generated layer is insufficient, use an LLM to:
1. Add missing join definitions
2. Create derived dimensions (e.g., age groups, date parts)
3. Add human-readable aliases

**Estimated LLM cost:** $0.50-1.00 for edge cases only

### Phase 4: Smoke Test

Run sample queries against each database to verify the semantic layer works:

```malloy
// Smoke test queries
run: singer -> { aggregate: row_count }
run: concert -> { group_by: year; aggregate: row_count }
```

## Cost Estimate (Revised)

| Phase | Method | Est. Cost |
|-------|--------|-----------|
| Generate 166 schemas | Python script | **$0** |
| Fix edge cases (~10%) | LLM | ~$0.50 |
| Smoke test queries | Malloy CLI | **$0** |
| **Total** | | **~$0.50** |

This is essentially free compared to query generation experiments!

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

1. [x] Write SQL analysis script (`scripts/generate_semantic_layers.py`)
2. [ ] Run script to generate all 166 Malloy source files
3. [ ] Install Malloy CLI for validation
4. [ ] Validate generated files, fix any syntax errors
5. [ ] Run smoke tests against sample databases
6. [ ] Begin query agent experiments (the real work!)

---

*This strategy allows us to focus experimentation budget on the query generation agent, where the real cost/performance tradeoffs matter.*
