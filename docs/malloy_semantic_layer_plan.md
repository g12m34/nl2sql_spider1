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

## Phase 1: Environment Setup

### 1.1 Download Spider Databases
- [ ] Locate Spider database download URL (from Yale LILY site or related sources)
- [ ] Download all 166 SQLite database files
- [ ] Verify database integrity (all tables present, data accessible)
- [ ] Document database location

### 1.2 Install/Verify Malloy CLI
- [ ] Check if Malloy CLI is available
- [ ] Install if needed
- [ ] Verify installation

### 1.3 Create Directory Structure
```
/workspace/project/malloy/
├── minimal/           # Script-generated from ground-truth SQL
├── full/              # Complete schema layers (main deliverable)
├── analysis/          # JSON analysis files
└── exemplars/         # Reference exemplars from Malloy docs
```

---

## Phase 2: Learn Malloy Patterns

### 2.1 Study Malloy Documentation
- [ ] Fetch Malloy semantic layer documentation
- [ ] Identify best exemplar patterns for:
  - Source definitions
  - Dimension declarations
  - Measure declarations
  - Join syntax (join_one, join_many)
  - Primary key declarations
- [ ] Save relevant exemplars to `malloy/exemplars/`

### 2.2 Document Malloy Conventions
Key syntax patterns to follow:
```malloy
source: table_name is duckdb.table('path/to/db.sqlite', 'TableName') extend {
  primary_key: id_column

  join_one: other_table on foreign_key = other_table.primary_key

  dimension:
    column_name is OriginalColumnName

  measure:
    row_count is count()
    total_amount is sum(amount)
}
```

---

## Phase 3: Generate Minimal Layers

### 3.1 Fix Script Path
- [ ] Update `scripts/generate_semantic_layers.py` to use correct Spider path
- [ ] Update output path to `/workspace/project/malloy/minimal/`

### 3.2 Run Minimal Layer Generation
- [ ] Execute the script
- [ ] Verify 166 `.malloy` files created in `malloy/minimal/`
- [ ] Review analysis JSON files in `malloy/analysis/`

### 3.3 Review Minimal Layer Output
- [ ] Check a sample of generated files for correctness
- [ ] Note naming conventions used
- [ ] Note join patterns detected

---

## Phase 4: Create Full Layer Exemplars

### 4.1 Select Exemplar Databases
| Database | Complexity | Tables | Selection Reason |
|----------|------------|--------|------------------|
| `concert_singer` | Simple | 4 | Basic joins, clear relationships |
| `world_1` | Medium | 4 | Well-known schema, good FK examples |
| `college_2` | Medium | ~10 | Multiple join paths |

### 4.2 Create Exemplar Full Layers
For each exemplar database:
- [ ] Read schema from `tables.json`
- [ ] Read minimal layer as reference
- [ ] Create full layer with:
  - ALL columns as dimensions
  - Appropriate measures for numeric columns
  - Complete join definitions from FK metadata
  - Primary key declarations
  - Descriptive comments

### 4.3 Test Exemplars
For each exemplar:
- [ ] Compile with Malloy CLI (syntax validation)
- [ ] Run against 10 questions from Spider dev/train set
- [ ] Track errors in error log
- [ ] Fix errors and re-test
- [ ] Repeat until all 10 questions pass

### 4.4 Critique and Refine
- [ ] Review exemplar quality
- [ ] Document lessons learned
- [ ] Update patterns/conventions based on findings
- [ ] Create final exemplar template

---

## Phase 5: Generate All Full Layers

### 5.1 Batch by Complexity
| Batch | Criteria | Est. Count |
|-------|----------|------------|
| 1 | Simple (< 5 tables) | ~80 |
| 2 | Medium (5-10 tables) | ~60 |
| 3 | Complex (10+ tables) | ~26 |

### 5.2 Generation Process
For each database:
1. Read schema from `tables.json`
2. Read minimal layer for reference
3. Generate full layer following exemplar patterns
4. Include:
   - All tables as sources
   - All columns as dimensions (readable snake_case names)
   - Measures: count() for all, sum/avg/min/max for numeric
   - Joins based on foreign key relationships
   - Primary keys where defined

### 5.3 Validation Loop
For each generated layer:
- [ ] Compile with Malloy CLI
- [ ] If errors: fix and re-compile
- [ ] Run smoke test queries
- [ ] Test against 10 Spider questions for that database
- [ ] Track all errors in error log
- [ ] Fix and repeat until passing

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
