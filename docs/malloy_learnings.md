# Malloy Semantic Layer Learnings

This document captures key learnings and gotchas discovered while building and testing Malloy semantic layers for NL2SQL evaluation.

## Iteration 1: Initial Generation

**Date:** 2025-01-11

### What We Built
- Generated 166 Malloy semantic layers from Spider database schemas
- Each layer included: sources, dimensions, measures, primary keys, and foreign key joins

### Issues Discovered

#### 1. One-Way Joins Are Insufficient

**Problem:** We only generated `join_one` relationships from child tables to parent tables (following foreign keys). This prevents queries that need to traverse relationships in reverse.

**Example:**
```
# What we generated:
plays_games → student_val (join_one)
sports_info → student_val (join_one)

# What we need for "students in both tables":
student_val → plays_games (join_many)
student_val → sports_info (join_many)
```

**Impact:** Questions requiring INTERSECT-like logic ("find X that appears in both A and B") cannot be expressed because you can't check if a parent has children in multiple related tables.

**Solution:** Add bidirectional joins - `join_many` on parent tables pointing to child tables.

---

#### 2. LLMs Don't Know Malloy Syntax

**Problem:** LLMs (Claude, GPT, DeepSeek) generated invalid Malloy syntax, using SQL patterns like:
- `IN (subquery)` - not valid in Malloy
- `HAVING` clause - not valid in Malloy
- Inline `join_one:` inside query blocks - joins must be in source definitions

**Example of Invalid Generated Code:**
```malloy
// LLM tried this (INVALID):
run: student_val -> {
  where: stu_i_d in (plays_games.stu_i_d)
  select: stu_i_d
}
```

**Solution:** Enhanced prompt with:
- Explicit Malloy syntax guide
- Clear statement that SQL keywords don't work
- Examples of valid Malloy patterns

---

#### 3. Prompt Structure for Cache Optimization

**Learning:** Structure prompts to maximize token caching:

```
1. Static content (syntax guide) - cached across ALL calls
2. Instructions - cached across ALL calls
3. Semantic layer - cached per database
4. Question - at the end, changes every call
```

This reduces costs when running many questions against the same database.

---

## Iteration 2: Bidirectional Joins

**Date:** 2025-01-11

### Changes Made
- Added `join_many` relationships from parent tables to child tables
- Parent tables now have visibility into their related child records

### New Semantic Layer Pattern

```malloy
// Parent table with reverse joins
source: student_val is duckdb.sql("...") extend {
  primary_key: stu_i_d

  // Forward reference to children
  join_many: plays_games on stu_i_d = plays_games.stu_i_d
  join_many: sports_info on stu_i_d = sports_info.stu_i_d

  measure:
    row_count is count()
    games_played_count is plays_games.count()
    sports_count is sports_info.count()
}

// Child table with parent join (unchanged)
source: plays_games is duckdb.sql("...") extend {
  join_one: student_val on stu_i_d = student_val.stu_i_d
}
```

### Enables These Query Patterns

```malloy
// Students who play both video games AND sports (INTERSECT equivalent)
run: student_val -> {
  where: plays_games.row_count > 0 and sports_info.row_count > 0
  group_by: stu_i_d
}

// Students who play video games OR sports (UNION equivalent)
run: student_val -> {
  where: plays_games.row_count > 0 or sports_info.row_count > 0
  group_by: stu_i_d
}
```

---

## Iteration 3: Forward Reference Fix

**Date:** 2025-01-11

### Problem Discovered

Adding bidirectional joins created **forward reference errors**:
- Parent sources tried to reference child sources that weren't defined yet
- Malloy requires sources to be defined before they can be referenced
- Topological sort for join_one (parents first) conflicts with join_many (children first)

**Error:**
```
error: Reference to undefined object 'plays_games' at line 15
```

### Solution: Two-Pass Source Generation

Generate sources in two passes:
1. **Base sources** - All tables with dimensions, PKs, measures (NO joins)
2. **Full sources** - Extend base sources with joins (can reference any base source)

```malloy
// PASS 1: Base sources (no joins)
source: student_val_base is duckdb.sql("...") extend {
  dimension: stu_i_d is StuID
  primary_key: stu_i_d
  measure: row_count is count()
}

source: plays_games_base is duckdb.sql("...") extend { ... }

// PASS 2: Full sources with joins (extend base sources)
source: student_val is student_val_base extend {
  join_many: plays_games is plays_games_base on stu_i_d = plays_games.stu_i_d
}

source: plays_games is plays_games_base extend {
  join_one: student_val is student_val_base on stu_i_d = student_val.stu_i_d
}
```

**Key insight:** Full sources join to `_base` sources, avoiding circular references.

---

## Iteration 4: Aggregate Filter Syntax

**Date:** 2025-01-11

### Problem Discovered

LLMs generated correct patterns but with wrong syntax:

```malloy
// INVALID - aggregates cannot be in where: clause
run: student_val -> { where: plays_games.row_count > 0 }

// INVALID - semicolon between aggregates
run: source -> { aggregate: a is x.count(); b is y.count() }
```

**Errors:**
- "Aggregate expressions are not allowed in `where:`"
- "no viable alternative at input"

### Solution: Updated Prompt with Correct Patterns

1. **Use pipelines for aggregate filters:** First aggregate, then filter
2. **Use commas between aggregates**, not semicolons
3. **Use `.count()` on joins**, not `.row_count`

**Correct INTERSECT pattern:**
```malloy
run: student_val -> {
  group_by: stu_i_d
  aggregate: games_count is plays_games.count(), sports_count is sports_info.count()
} -> {
  where: games_count > 0 and sports_count > 0
  select: stu_i_d
}
```

---

## Key Gotchas Summary

| Issue | Symptom | Solution |
|-------|---------|----------|
| One-way joins | Can't query "in both A and B" | Add `join_many` on parent tables |
| Forward references | "undefined object" errors | Two-pass generation with base sources |
| SQL syntax in Malloy | Compile errors on `IN`, `EXISTS`, etc. | Use join traversal + filters |
| Inline joins | `join_one:` in query fails | Define joins in source, not query |
| Aggregates in where | "not allowed in where:" error | Use pipeline: aggregate then filter |
| Multiple aggregates | Syntax errors | Comma-separate, don't semicolon-separate |
| Prompt caching | High API costs | Static content first, question last |

---

## Malloy Limitations for Spider Questions

Some Spider question patterns may be difficult or impossible in Malloy:

1. **True set operations** - UNION ALL with duplicates
2. **Correlated subqueries** - complex nested logic
3. **Self-joins** - may need source aliases (not well supported)
4. **EXCEPT** - "in A but not in B" requires careful join + null checks

For evaluation, we should track which question types fail due to Malloy limitations vs. LLM errors.

---

## Iteration 5: Metadata Enrichment (AT&T Paper Approach)

**Date:** 2025-01-11

### Paper Reference

Based on "Automatic Metadata Extraction for Text-to-SQL" (AT&T), which achieved #1 on BIRD benchmark.

### Key Insights from Paper

1. **Database Profiling** outperformed human-supplied metadata:
   - No metadata: 49.8% accuracy
   - Human metadata: 59.6% accuracy
   - Profiling metadata: 61.2% accuracy
   - Fused (both): 63.2% accuracy

2. **Profiling Statistics Collected**:
   - NULL counts and percentages
   - Distinct value counts
   - Min/max values
   - Top-k sample values (most common)
   - Value patterns (fixed length, numeric-only, etc.)

3. **LLM Profile Summarization**:
   - Short descriptions: For schema linking
   - Long descriptions: For SQL generation (includes samples)

### Implementation

Created `/workspace/project/scripts/generate_enriched_layers.py`:

1. **Database Profiling**: Extract statistics for each field
2. **Heuristic Descriptions**: Auto-detect field semantics:
   - Primary keys (unique, non-null ID columns)
   - Foreign keys (non-unique ID columns)
   - Names (columns with "name" in the name)
   - Categorical fields (few distinct values)
   - Dates/times, numeric measures, etc.
3. **Enriched Comments**: Add field descriptions and sample values as comments

### Enriched Layer Format

```malloy
// ============================================================
// FIELD METADATA (Auto-generated from database profiling)
// ============================================================
//
// Table: Student
//   StuID: Primary key identifier for Student
//     Sample values: '1001', '1002', '1003'
//   Age: Categorical field: '18', '20', '19', '17', '26'
//     Sample values: '18', '20', '19'
//   Sex: Categorical field: 'M', 'F'
//     Sample values: 'M', 'F'
...

source: student_val_base is duckdb.sql("...") extend {
  dimension:
    // Primary key identifier for Student
    stu_i_d is StuID
    // Name field with 31 distinct values
    l_name is LName
    ...
}
```

### Results

Tested on 46 questions from 10 databases:

| Metric | Original | Enriched | Improvement |
|--------|----------|----------|-------------|
| Accuracy | 8.7% (4/46) | 17.4% (8/46) | **+100%** |
| Errors | 40 | 34 | **-6 errors** |

**Key Finding**: Even heuristic-based descriptions (no LLM needed) doubled the accuracy. The sample values in comments help the LLM understand field semantics and generate more accurate queries.

### Future Improvements

1. Use LLM to generate richer semantic descriptions
2. Add more sample values in the prompt (5-10 per field)
3. Include value patterns (email formats, phone numbers, etc.)
4. Add cross-table relationship descriptions

---

## Iteration 6: Redundant Field Aliases Bug

**Date:** 2025-01-11

### Problem Discovered

After enriching semantic layers with domain context and field descriptions, accuracy **dramatically dropped** from ~75% to ~16-27%. The error logs showed:

```
error: Cannot redefine 'title' at line 138
error: Cannot redefine 'country_name' at line 53
error: Cannot redefine 'address_type_code' at line X
```

### Root Cause

When enriching semantic layers, we inadvertently created **redundant same-name aliases**:

```malloy
// BAD - causes "Cannot redefine" error when LLM generates code
dimension:
  title is title              // Redundant alias!
  state_name is state_name    // Redundant alias!
  address_id is address_id    // Redundant alias!
```

When an LLM generates Malloy code that references these fields, the compiler sees both:
1. The original column `title` from the SQL
2. The aliased dimension `title is title`

This creates a name collision when the generated code tries to use `title`.

### Solution

**Never alias a field to itself.** Only create aliases when renaming:

```malloy
// GOOD - use raw column names without aliasing
dimension:
  // Title of the paper (semantic description)
  // Use raw column: title
  paper_id      // Just the column name, no alias needed
  author_name   // Just the column name

// GOOD - alias only when actually renaming
dimension:
  id is StuID                    // Renaming StuID -> id (OK)
  full_name is LName             // Renaming LName -> full_name (OK)
```

### Fix Applied

Removed all redundant same-name aliases from:
- `scholar.malloy`: Removed `title is title`
- `geo.malloy`: Removed `state_name is state_name`, `country_name is country_name`
- `behavior_monitoring.malloy`: Removed `address_id is address_id`, `address_type_code is address_type_code`
- `customers_and_products_contacts.malloy`: Removed `address_id is address_id`

### Impact

After fix, DeepSeek accuracy on enriched layers:
- Stratified 100: **41.0%** (was ~12% before fix)
- Hard/Extra 100: **47.0%** (was ~10% before fix)

### Key Lesson

**When writing semantic layer generation prompts/instructions:**

> **NEVER create aliases like `field is field`.** If you want to document a field, add a comment describing it, but keep the field reference as-is. Only use aliases when actually renaming a column to a different name.

This is critical for future automation of semantic layer creation.

---

## Iteration 7: Hand-Crafted Expert Layers

**Date:** 2025-01-11

### Approach

Instead of automated generation, we manually enriched 10 key databases used in extended test sets with:

1. **Domain context headers** - Explain what the database represents
2. **Relationship documentation** - Explain how tables connect and why
3. **Example values** - Show actual data to help LLMs understand field semantics
4. **Common query patterns** - Document typical questions and how to express them
5. **Intermediate sources** - Create helper sources for complex join paths

### Structure Pattern

```malloy
// ============================================================
// DATABASE: {db_name}
// Domain: {domain description}
// ============================================================
//
// DATA MODEL OVERVIEW:
// This database models {domain}. The core entities are:
// - {entity1}: {description}
// - {entity2}: {description}
//
// KEY RELATIONSHIPS:
// - {table1} -> {table2}: {relationship description}
//
// EXAMPLE VALUES:
// - {field}: {sample1}, {sample2}, {sample3}
//
// COMMON QUERY PATTERNS:
// 1. {pattern_name}: {how to express in Malloy}
// ============================================================

// Base sources first (no joins)
source: table1_base is duckdb.sql("...") extend {
  primary_key: id
  dimension:
    // {field description}
    field1
}

// Extended sources with joins
source: table1 is table1_base extend {
  join_one: table2 is table2_base on fk = table2.pk
}
```

### Databases Enriched

| Database | Focus Areas |
|----------|-------------|
| scholar | Academic papers, authors, citations, venues |
| geo | US geography, states, cities, rivers, borders |
| movie_1 | Movies, reviewers, ratings |
| game_1 | Students, video games, sports |
| activity_1 | Faculty, students, activities |
| manufactory_1 | Manufacturers, products, prices |
| ship_1 | Ships, captains, ranks |
| gas_company | Gas/oil companies, stations |
| behavior_monitoring | Teachers, students, behavior assessments |
| customers_and_products_contacts | CRM with customers, products, addresses |

### Results

With properly enriched layers (no redundant aliases), evaluation showed improved handling of complex queries, especially those requiring:
- Multi-hop joins
- Domain-specific understanding
- Correct field semantics

