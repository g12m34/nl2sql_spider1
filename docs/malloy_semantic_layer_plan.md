# Malloy Semantic Layer Generation Plan

## Overview

This document outlines the plan to create Malloy semantic layers for all 166 Spider databases. The semantic layers will enable NL2SQL experiments using Malloy as the query language.

## Answers to Key Questions

| Question | Decision |
|----------|----------|
| Database Files | Find and download Spider SQLite databases; set up connections based on actual data storage |
| Phase Sequencing | Run minimal layer script first, then create full layers using minimal as reference |
| Exemplar Approach | Study Malloy docs → create Spider exemplars → critique → iterate → generate rest |
| Directory Structure | `malloy/minimal/`, `malloy/full/`, `malloy/analysis/` |
| Join Handling | Generate actual Malloy joins from FK metadata; test each layer against 10 questions |

---

## Phase 1: Environment Setup ✅ COMPLETED

### 1.1 Download Spider Databases
- [x] Downloaded from Kaggle mirror (Yale LILY Spider dataset)
- [x] 166 SQLite database files extracted
- [x] Verified sample database (concert_singer) - all tables accessible
- [x] **Location**: `/workspace/spider_db/spider/database/{db_id}/{db_id}.sqlite`

### 1.2 Install/Verify Malloy CLI
- [x] malloy-cli v0.0.50 installed at `/usr/bin/malloy-cli`
- [x] Verified with `malloy-cli --version`

### 1.3 Create Directory Structure
- [x] Created:
```
/workspace/project/malloy/
├── minimal/           # Script-generated from ground-truth SQL
├── full/              # Complete schema layers (main deliverable)
├── analysis/          # JSON analysis files
└── exemplars/         # Reference exemplars from Malloy docs
```

---

## Phase 2: Learn Malloy Patterns ✅ COMPLETED

### 2.1 Study Malloy Documentation
- [x] Fetched Malloy documentation (source, join, fields)
- [x] Identified patterns saved to `malloy/exemplars/malloy_patterns.md`

### 2.2 Key Learnings

**Source Definition:**
```malloy
source: name is duckdb.table('path/to/db.sqlite', 'TableName') extend { }
```

**Join Types:**
- `join_one`: Many-to-one (joined table has ONE row per source row)
- `join_many`: One-to-many (joined table has MANY rows per source row)
- `with` syntax requires `primary_key` on joined source
- All joins are LEFT OUTER by default

**Critical Syntax:**
```malloy
source: table_name is duckdb.table('db.sqlite', 'Table') extend {
  primary_key: id_column

  join_one: other_table with foreign_key  // requires primary_key on other_table
  // OR: join_one: other_table on fk = other_table.pk

  dimension:
    col_name is OriginalColumn

  measure:
    row_count is count()
    total_amt is sum(amount)
}
```

---

## Phase 3: Generate Minimal Layers ✅ COMPLETED

### 3.1 Fix Script Path
- [x] Updated `scripts/generate_semantic_layers.py` to use correct Spider path
- [x] Updated output path to `/workspace/project/malloy/minimal/`

### 3.2 Run Minimal Layer Generation
- [x] Executed the script successfully
- [x] 160 `.malloy` files created in `malloy/minimal/`
- [x] Analysis JSON files generated in `malloy/analysis/`

### 3.3 Review Minimal Layer Output
- [x] Verified sample files for correctness
- [x] Documented naming conventions
- [x] Identified join patterns from foreign key metadata

---

## Phase 4: Create Full Layer Exemplars ✅ COMPLETED

### 4.1 Exemplars Created
| Database | Tables | Status |
|----------|--------|--------|
| `concert_singer` | 4 | PASS (10/10 questions) |
| `world_1` | 4 | PASS (compiles, joins work) |

### 4.2 Key Learnings

**SQLite Connection Pattern:**
```malloy
source: table is duckdb.sql("""
  SELECT * FROM sqlite_scan('/path/to/db.sqlite', 'TableName')
""") extend { ... }
```

**Issues Discovered:**
- Reserved word `Year` must be quoted: `` `Year` ``
- Sources with primary_key must be defined before sources that join to them
- Use `group_by:` not `select:` in queries

### 4.3 Critique Document
See: `malloy/exemplars/exemplar_critique.md`

---

## Phase 5: Generate All Full Layers ✅ COMPLETED

### 5.1 Generation Script Created
- [x] Created `scripts/generate_full_layers.py`
- [x] Handles reserved word quoting (~50+ reserved words)
- [x] Implements topological sorting for table dependencies
- [x] Generates proper join aliases for multiple FKs to same table
- [x] Handles self-joins (skips them to avoid errors)
- [x] Handles column name conflicts with table names

### 5.2 Generation Results
| Metric | Count |
|--------|-------|
| Total databases | 166 |
| Full layers generated | 166 |
| Compilation errors | **0** |

### 5.3 Key Fixes Applied
1. **SQLite Connection**: Used `duckdb.sql("SELECT * FROM sqlite_scan(...)")` pattern
2. **Reserved Words**: Quote with backticks (Year, Name, Code, State, etc.)
3. **Empty Dimensions**: Skip `dimension:` block if no dimensions to define
4. **Multiple Joins**: Generate unique aliases based on FK column names
5. **Self-Joins**: Skip in both topological sort and join generation
6. **Type Mismatches**: Removed problematic measures for string columns marked as number

### 5.4 Output
- All 166 `.malloy` files in `/workspace/project/malloy/full/`
- All files compile successfully with Malloy CLI

---

## Phase 6: Final Validation

### 6.1 Full Compilation Check
```bash
for f in malloy/full/*.malloy; do
  malloy compile "$f" || echo "FAILED: $f" >> validation_errors.txt
done
```

### 6.2 Schema Coverage Verification
- [ ] Verify each full layer covers ALL columns from schema
- [ ] Generate coverage report

### 6.3 Question Answering Test
- [ ] Each of 166 databases tested against 10 questions
- [ ] Total: 1,660 question tests
- [ ] Track success rate per database
- [ ] Fix any remaining failures

---

## Phase 7: Documentation and Cleanup

### 7.1 Generate Analysis Artifacts
- [ ] `column_coverage.json` - minimal vs full column counts
- [ ] `_summary.json` - overall statistics
- [ ] Error log summary

### 7.2 Update Project Documentation
- [ ] Document any schema-specific quirks discovered

---

## Error Tracking

Errors will be tracked in `/workspace/project/malloy/error_log.md`

### Error Log Format
| Database | Error Type | Description | Status |
|----------|------------|-------------|--------|
| (to be filled during execution) | | | |

### Common Error Categories
1. **Syntax errors** - Invalid Malloy syntax
2. **Missing columns** - Column referenced but not in schema
3. **Join errors** - Invalid join conditions
4. **Type mismatches** - Wrong aggregation for column type
5. **Query failures** - Valid syntax but incorrect results

---

## Success Criteria

- [ ] 166 minimal layers generated and validated
- [ ] 166 full layers generated and validated
- [ ] All layers compile without errors
- [ ] Each layer passes 10-question test
- [ ] Column coverage analysis complete
- [ ] Error log resolved (all errors fixed)

---

## Dependencies

- Spider dataset with SQLite databases
- Malloy CLI for compilation and testing
- Python 3 for minimal layer script
- Network access to download databases and Malloy docs

---

*Plan created: Ready for execution upon user approval*
