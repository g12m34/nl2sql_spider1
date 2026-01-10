# Semantic Layer Strategy

## Overview

The Malloy semantic layer is built **once per database** (166 databases), not per question. We'll use **Claude Code** (subscription) to generate these layers at no additional API cost.

## Two Semantic Layers Per Database

We will create **two versions** of each semantic layer to enable proper evaluation:

### 1. Minimal Layer (`*_minimal.malloy`)
- Contains **only** columns/measures used in ground truth SQL
- Derived deterministically from correct query analysis
- Use case: Baseline testing, debugging, "oracle" reference

### 2. Full Layer (`*_full.malloy`)
- Contains **all** columns from the database schema
- Represents realistic production scenario
- Use case: **Primary evaluation target**

### Why Both Are Needed

```
┌─────────────────────────────────────────────────────────────────┐
│                    EVALUATION INSIGHT                           │
├─────────────────────────────────────────────────────────────────┤
│ If we only give models the "correct" columns, we hide a major  │
│ source of errors: POOR COLUMN SELECTION.                       │
│                                                                 │
│ Models need to:                                                 │
│   1. Understand the question                                    │
│   2. Choose the RIGHT columns from many options  ← HARD!        │
│   3. Write correct Malloy syntax                                │
│   4. Handle joins/aggregations properly                         │
│                                                                 │
│ Testing only with minimal layer = artificially inflated scores  │
└─────────────────────────────────────────────────────────────────┘
```

### Error Attribution

With both layers, we can measure:

| Error Type | How to Detect |
|------------|---------------|
| Wrong column selection | Query fails on full layer, succeeds on minimal |
| Syntax errors | Query fails on both layers |
| Logic errors | Query runs but wrong results |
| Missing join | Query fails with join error |

## File Structure

```
malloy/
├── minimal/                    # Ground-truth derived (script-generated)
│   ├── concert_singer.malloy
│   ├── world_1.malloy
│   └── ... (166 files)
│
├── full/                       # Complete schema (Claude Code generated)
│   ├── concert_singer.malloy
│   ├── world_1.malloy
│   └── ... (166 files)
│
└── analysis/                   # Supporting data
    ├── concert_singer.json     # Which columns are in ground truth
    ├── _summary.json
    └── column_coverage.json    # Stats on minimal vs full
```

## Generation Plan

### Phase 1: Generate Minimal Layers (Automated)

**Method:** Python script analyzing ground truth SQL
**Cost:** $0
**Script:** `scripts/generate_semantic_layers.py`

```bash
python scripts/generate_semantic_layers.py --output malloy/minimal/
```

The script extracts from correct SQL:
- Tables actually referenced
- Columns used in SELECT, WHERE, GROUP BY, ORDER BY
- Aggregation functions applied (COUNT, SUM, AVG, MIN, MAX)
- Join patterns detected

**Output:** 166 `.malloy` files with only necessary elements

### Phase 2: Generate Full Layers (Claude Code)

**Method:** Use Claude Code (subscription) to generate complete semantic layers
**Cost:** $0 (covered by subscription)

#### Approach

For each database, Claude Code will:

1. **Read the schema** from `tables.json`:
   - All table names
   - All column names and types
   - Primary keys
   - Foreign key relationships

2. **Read the minimal layer** as reference:
   - Understand the naming conventions used
   - See which measures were deemed useful
   - Learn the join patterns

3. **Generate full layer** including:
   - ALL columns as dimensions (with readable names)
   - Appropriate measures for ALL numeric columns
   - Complete join definitions based on foreign keys
   - Comments explaining table purposes

#### Prompt Strategy for Claude Code

For each database, we'll provide:

```
Context:
- Database schema (from tables.json)
- Minimal layer (from Phase 1) as style reference
- 2-3 exemplar full layers (hand-crafted for reference)

Task:
Generate a complete Malloy semantic layer that includes:
1. Source definitions for ALL tables in the schema
2. Dimensions for ALL columns (use readable snake_case names)
3. Measures for numeric columns:
   - count() for all tables
   - sum/avg/min/max for numeric columns
4. Join definitions based on foreign keys
5. Primary key declarations where identifiable

Output only the .malloy file content.
```

#### Batch Processing with Claude Code

We'll process databases in batches:

```
Batch 1: Simple schemas (< 5 tables)     ~80 databases
Batch 2: Medium schemas (5-10 tables)    ~60 databases
Batch 3: Complex schemas (10+ tables)    ~26 databases
```

For each batch:
1. Provide exemplar from that complexity tier
2. Generate all databases in tier
3. Validate with Malloy compiler
4. Fix any errors before moving to next batch

### Phase 3: Validation

#### 3a. Malloy Compiler Check

```bash
# Validate all generated files
for f in malloy/full/*.malloy; do
  malloy compile "$f" 2>&1 || echo "FAILED: $f" >> validation_errors.txt
done
```

#### 3b. Schema Coverage Check

Verify full layer actually covers all schema elements:

```python
# Pseudo-code for validation
for db in databases:
    schema_columns = get_columns_from_tables_json(db)
    malloy_dimensions = parse_malloy_file(f"malloy/full/{db}.malloy")

    missing = schema_columns - malloy_dimensions
    if missing:
        report_missing(db, missing)
```

#### 3c. Smoke Test Queries

Run simple queries against each source:

```malloy
// For each source in the layer
run: source_name -> { aggregate: row_count }
run: source_name -> { group_by: first_dimension; aggregate: row_count }
```

### Phase 4: Create Analysis Artifacts

Generate supporting data for experiments:

```json
// column_coverage.json
{
  "concert_singer": {
    "minimal_columns": 18,
    "full_columns": 24,
    "coverage_ratio": 0.75,
    "unused_columns": ["highest", "lowest", "is_male", ...]
  },
  ...
}
```

This helps us analyze:
- How much "noise" (unused columns) exists per database
- Whether column selection difficulty correlates with model errors

## Exemplar Databases

We'll hand-craft 3 full semantic layers as reference exemplars:

| Database | Complexity | Tables | Why Selected |
|----------|------------|--------|--------------|
| `concert_singer` | Simple | 4 | Basic joins, clear relationships |
| `college_2` | Medium | 10 | Multiple join paths, varied types |
| `hospital_1` | Complex | 15 | Many tables, complex relationships |

These serve as:
1. Few-shot examples for Claude Code
2. Validation targets (we know they're correct)
3. Documentation of our Malloy conventions

## Conventions for Generated Layers

### Naming
- Source names: `lowercase_with_underscores` (match table name)
- Dimension names: `lowercase_with_underscores`
- Measure names: `{agg}_{column}` (e.g., `avg_age`, `sum_capacity`)

### Structure
```malloy
source: table_name is duckdb.table('OriginalTableName') extend {
  // Primary key (if identifiable)
  primary_key: id_column

  // Joins (based on foreign keys)
  join_one: other_table on fk_column = other_table.pk_column

  // Dimensions (ALL columns)
  dimension:
    readable_name is OriginalColumnName
    another_column is AnotherColumn

  // Measures (for numeric columns + row count)
  measure:
    row_count is count()
    total_amount is sum(amount)
    avg_amount is avg(amount)
}
```

### Comments
```malloy
// Purpose: [brief description of table]
// Relationships: [key joins to note]
```

## Success Criteria

Before moving to query agent experiments:

- [ ] 166 minimal layers generated and validated
- [ ] 166 full layers generated and validated
- [ ] All layers compile without errors
- [ ] Smoke tests pass for all sources
- [ ] Column coverage analysis complete
- [ ] 3 exemplar databases hand-verified

## Cost Summary

| Phase | Method | Cost |
|-------|--------|------|
| Minimal layers | Python script | $0 |
| Full layers | Claude Code subscription | $0 |
| Validation | Malloy CLI | $0 |
| **Total** | | **$0** |

## Next Steps

1. [ ] Create 3 hand-crafted exemplar full layers
2. [ ] Run minimal layer generation script
3. [ ] Use Claude Code to generate full layers (batch by complexity)
4. [ ] Validate all layers with Malloy compiler
5. [ ] Run smoke tests
6. [ ] Generate column coverage analysis
7. [ ] Begin query agent experiments with FULL layers as primary target

---

*With both minimal and full layers, we can properly evaluate model performance including their ability to select the right columns - a critical real-world skill.*
