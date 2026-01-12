# Full Prompt Comparison

This document shows the complete text of both prompts for the same question.

**Question:** What is the name of the activity that has the most faculty members involved in?
**Database:** activity_1
**Question ID:** 6785

---

# BASELINE PROMPT (V3 - Achieved 60% with Gemini Flash)

```
# Malloy Query Generation

## Malloy Syntax Reference

Malloy is a semantic modeling and query language. Queries use `run:` followed by a source and pipeline `->`.

### Query Patterns

```malloy
// Select fields
run: source -> { select: field1, field2 }

// Aggregate with grouping
run: source -> { group_by: dim1, dim2; aggregate: count_measure, sum_measure }

// Filter rows (only non-aggregate conditions allowed in where:)
run: source -> { where: field = 'value'; select: * }

// Order and limit
run: source -> { select: *; order_by: field desc; limit: 10 }

// Navigate joins (defined in source with join_one/join_many)
run: orders -> { group_by: customer.name; aggregate: total_revenue }

// Count related records via join_many
run: parent -> { group_by: parent_id; aggregate: child_count is children.count() }
```

### INTERSECT Pattern (records in BOTH related tables)

```malloy
// Find entities that have records in BOTH table_a AND table_b
run: parent_source -> {
  group_by: key_field
  aggregate: a_count is joined_table_a.count(), b_count is joined_table_b.count()
} -> {
  where: a_count > 0 and b_count > 0
  select: key_field
}
```

### CRITICAL Syntax Rules

DO:
- Use .count() on joined sources for counting related records
- Separate aggregates with COMMAS: `aggregate: a is x.count(), b is y.count()`
- Separate clauses with SEMICOLONS: `group_by: x; aggregate: y`
- Use single quotes for strings: `'value'`
- Use `having:` for filtering on aggregated values: `{ group_by: x; aggregate: cnt is y.count(); having: cnt > 0 }`
- Or use pipeline with view type: `{ aggregate: x } -> { select: *; where: x > 0 }`

FILTERED AGGREGATES - VERY IMPORTANT:
- CORRECT: `count() { where: field = 'value' }` - filter AFTER the function
- CORRECT: `sum(amount) { where: type = 'sale' }`
- WRONG: `joined { where: x = 'y' }.count()` - this DOES NOT WORK
- When filtering joined data, use FULL PATH: `joined.count() { where: joined.field = 'value' }`
- Example: `customer_orders.count() { where: customer_orders.status = 'Completed' }` (NOT just `status`)

SCALAR VS AGGREGATE - CRITICAL:
- Dimensions (scalar fields) go in: `group_by:` or `select:`
- Measures (aggregate fields) go in: `aggregate:`
- To find max/min of a dimension, use aggregate functions: `aggregate: max_altitude is max(altitude)`
- WRONG: `aggregate: altitude` - this tries to aggregate a scalar and will ERROR
- CORRECT: `aggregate: max_altitude is max(altitude)` or `group_by: altitude; order_by: altitude desc; limit: 1`

VALID AGGREGATE FUNCTIONS:
- count(), sum(field), avg(field), min(field), max(field)
- NO list(), string_agg(), or other SQL functions directly

COUNTING JOINED RECORDS - CRITICAL:
- To count related records and get 0 when none exist, use: `count(joined.field)`
- WRONG: `joined.count()` - returns 1 even when no matches (counts the row itself)
- CORRECT: `count(joined.primary_key)` - returns 0 when no matches
- Example: `count(detention.teacher_id)` NOT `detention.count()`

ENTITY LOOKUP PATTERN - "What/Which is the X with max/min Y":
- When asked "what is the tallest mountain" - return the MOUNTAIN NAME, not just the height
- WRONG: `aggregate: max(height)` - returns only the height value
- CORRECT: `select: mountain_name, mountain_altitude; order_by: mountain_altitude desc; limit: 1`
- IMPORTANT: order_by fields MUST be in output (select/group_by)
- Example: "what is the biggest state" = `run: state -> { select: state_name, area; order_by: area desc; limit: 1 }`
- HANDLING TIES: When there may be multiple records with the same max/min value, use having: to return ALL tied records:
  `{ group_by: name; aggregate: cnt is items.count() } -> { select: *; having: cnt = max(cnt) }`

DO NOT:
- Use SQL keywords: IN, EXISTS, UNION, INTERSECT, EXCEPT, SUBQUERY
- Put aggregates in where: clauses (use `having:` or pipeline instead)
- Use filter() function - not valid Malloy syntax
- Use inline joins in queries - joins must be in source definitions (join_one/join_many)
- Create new aggregates in second pipeline stage - only filter/select
- Create pipeline stages without a view type - WRONG: `-> { where: x > 0 }` CORRECT: `-> { select: *; where: x > 0 }`
- Put { where: } BEFORE .count() - always put it AFTER
- Use `aggregate: dimension_field` - dimensions are scalar, use max/min/avg or group_by
- Use `run:` inside another query (NO SUBQUERIES) - use pipelines instead
- Use `count(distinct field)` - DEPRECATED, use `count(field)` instead

## Instructions

Generate a Malloy query. Use source names and field names exactly as defined in the semantic layer.
Return ONLY the query - no explanation, no markdown code blocks.

## Semantic Layer

```malloy
// =============================================================================
// ACTIVITY_1 DATABASE - University Activities System
// =============================================================================
// This database tracks students, faculty, and their participation in activities:
// - Student: university students with demographic info
// - Faculty: university faculty members
// - Activity: extracurricular activities offered
// - Participates_in: which students do which activities
// - Faculty_Participates_in: which faculty supervise/participate in activities
//
// KEY RELATIONSHIPS:
// - Student participates in Activity (via Participates_in junction)
// - Faculty participates in Activity (via Faculty_Participates_in junction)
// - Faculty advises Student (via Student.advisor = Faculty.fac_id)
//
// COMMON QUERY PATTERNS:
// - "activities for [student]": student -> participates_in.activity
// - "students in [activity]": participates_in where activity.name = X
// - "faculty who do [activity]": faculty -> faculty_participates_in.activity
// - "students advised by [faculty]": faculty -> student (via advisor)
// - "activities with most participants": group by activity, count participates_in
// =============================================================================

// ACTIVITY TABLE
// List of activities students and faculty can participate in
source: activity_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Activity')
""") extend {
  dimension:
    // Unique activity identifier
    act_id is actid

    // Name of the activity
    // Values: 'Mountain Climbing', 'Canoeing', 'Kayaking', 'Spelunking',
    //         'Soccer', 'Baseball', 'Football', 'Volleyball', 'Chess', etc.
    name is activity_name

  primary_key: act_id

  measure:
    activity_count is count()
}

// STUDENT TABLE
// University students who can participate in activities
source: student_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Student')
""") extend {
  dimension:
    // Unique student identifier
    stu_id is StuID

    // Student's last name
    // Examples: 'Smith', 'Kim', 'Jones', 'Kumar', 'Gompers'
    last_name is LName

    // Student's first name
    // Examples: 'Linda', 'Tracy', 'Shiela', 'Dinesh', 'Paul'
    first_name is Fname

    // Student's age
    age is Age

    // Sex: 'M' or 'F'
    sex is Sex

    // Academic major code
    major is Major

    // Faculty advisor ID
    advisor is Advisor

    // City code
    student_city is city_code

  primary_key: stu_id

  measure:
    student_count is count()
}

// FACULTY TABLE
// University faculty members who can advise students and participate in activities
source: faculty_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Faculty')
""") extend {
  dimension:
    // Unique faculty identifier
    fac_id is FacID

    // Faculty last name
    // Examples: 'Giuliano', 'Goodrich', 'Masson', 'Runolfsson', 'Naiman'
    last_name is Lname

    // Faculty first name
    // Examples: 'Mark', 'Michael', 'Gerald', 'Thordur', 'Daniel'
    first_name is Fname

    // Academic rank
    // Values: 'Professor', 'AsstProf', 'Instructor', 'AssocProf'
    rank is Rank

    // Sex: 'M' or 'F'
    sex is Sex

    // Phone number
    phone is Phone

    // Room number
    room is Room

    // Building name
    building is Building

  primary_key: fac_id

  measure:
    faculty_count is count()
}

// PARTICIPATES_IN TABLE (Junction)
// Links students to their activities
source: participates_in_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Participates_in')
""") extend {
  dimension:
    stu_id is stuid
    act_id is actid

  measure:
    participation_count is count()
}

// FACULTY_PARTICIPATES_IN TABLE (Junction)
// Links faculty to activities they supervise/participate in
source: faculty_participates_in_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Faculty_Participates_in')
""") extend {
  dimension:
    fac_id is FacID
    act_id is actid

  measure:
    faculty_participation_count is count()
}

// =============================================================================
// FULL SOURCES WITH RELATIONSHIPS
// =============================================================================

// Activity with participants
source: activity is activity_base extend {
  join_many: participates_in is participates_in_base on act_id = participates_in.act_id
  join_many: faculty_participates_in is faculty_participates_in_base on act_id = faculty_participates_in.act_id
}

// Participates_in with activity info (for nested joins)
source: participates_in_with_activity is participates_in_base extend {
  join_one: activity is activity_base on act_id = activity.act_id
}

// Faculty_participates_in with activity info (for nested joins)
source: faculty_participates_in_with_activity is faculty_participates_in_base extend {
  join_one: activity is activity_base on act_id = activity.act_id
}

// Student with their activities (includes nested activity details)
source: student is student_base extend {
  join_many: participates_in is participates_in_with_activity on stu_id = participates_in.stu_id
}

// Faculty with their activities AND students they advise
source: faculty is faculty_base extend {
  join_many: faculty_participates_in is faculty_participates_in_with_activity on fac_id = faculty_participates_in.fac_id
  join_many: student is student_base on fac_id = student.advisor  // students this faculty advises
}

// Participation with full details
source: participates_in is participates_in_base extend {
  join_one: student is student_base on stu_id = student.stu_id
  join_one: activity is activity_base on act_id = activity.act_id
}

// Faculty participation with full details
source: faculty_participates_in is faculty_participates_in_base extend {
  join_one: faculty is faculty_base on fac_id = faculty.fac_id
  join_one: activity is activity_base on act_id = activity.act_id
}

```

## Question

What is the name of the activity that has the most faculty members involved in?

## Query
```

---

# REASONING TRACE PROMPT (This Experiment - Achieved 46% with Gemini Flash)

```
# Malloy Query Generation

## Malloy Syntax Reference

Malloy is a semantic modeling and query language. Queries use `run:` followed by a source and pipeline `->`.

### Query Patterns

```malloy
// Select fields
run: source -> { select: field1, field2 }

// Aggregate with grouping
run: source -> { group_by: dim1, dim2; aggregate: count_measure, sum_measure }

// Filter rows (only non-aggregate conditions allowed in where:)
run: source -> { where: field = 'value'; select: * }

// Order and limit
run: source -> { select: *; order_by: field desc; limit: 10 }

// Navigate joins (defined in source with join_one/join_many)
run: orders -> { group_by: customer.name; aggregate: total_revenue }

// Count related records via join_many
run: parent -> { group_by: parent_id; aggregate: child_count is children.count() }
```

### INTERSECT Pattern (records in BOTH related tables)

```malloy
// Find entities that have records in BOTH table_a AND table_b
run: parent_source -> {
  group_by: key_field
  aggregate: a_count is joined_table_a.count(), b_count is joined_table_b.count()
} -> {
  where: a_count > 0 and b_count > 0
  select: key_field
}
```

### CRITICAL Syntax Rules

DO:
- Use .count() on joined sources for counting related records
- Separate aggregates with COMMAS: `aggregate: a is x.count(), b is y.count()`
- Separate clauses with SEMICOLONS: `group_by: x; aggregate: y`
- Use single quotes for strings: `'value'`
- Use `having:` for filtering on aggregated values: `{ group_by: x; aggregate: cnt is y.count(); having: cnt > 0 }`
- Or use pipeline with view type: `{ aggregate: x } -> { select: *; where: x > 0 }`

FILTERED AGGREGATES - VERY IMPORTANT:
- CORRECT: `count() { where: field = 'value' }` - filter AFTER the function
- CORRECT: `sum(amount) { where: type = 'sale' }`
- WRONG: `joined { where: x = 'y' }.count()` - this DOES NOT WORK
- When filtering joined data, use FULL PATH: `joined.count() { where: joined.field = 'value' }`
- Example: `customer_orders.count() { where: customer_orders.status = 'Completed' }` (NOT just `status`)

SCALAR VS AGGREGATE - CRITICAL:
- Dimensions (scalar fields) go in: `group_by:` or `select:`
- Measures (aggregate fields) go in: `aggregate:`
- To find max/min of a dimension, use aggregate functions: `aggregate: max_altitude is max(altitude)`
- WRONG: `aggregate: altitude` - this tries to aggregate a scalar and will ERROR
- CORRECT: `aggregate: max_altitude is max(altitude)` or `group_by: altitude; order_by: altitude desc; limit: 1`

VALID AGGREGATE FUNCTIONS:
- count(), sum(field), avg(field), min(field), max(field)
- NO list(), string_agg(), or other SQL functions directly

COUNTING JOINED RECORDS - CRITICAL:
- To count related records and get 0 when none exist, use: `count(joined.field)`
- WRONG: `joined.count()` - returns 1 even when no matches (counts the row itself)
- CORRECT: `count(joined.primary_key)` - returns 0 when no matches
- Example: `count(detention.teacher_id)` NOT `detention.count()`

ENTITY LOOKUP PATTERN - "What/Which is the X with max/min Y":
- When asked "what is the tallest mountain" - return the MOUNTAIN NAME, not just the height
- WRONG: `aggregate: max(height)` - returns only the height value
- CORRECT: `select: mountain_name, mountain_altitude; order_by: mountain_altitude desc; limit: 1`
- IMPORTANT: order_by fields MUST be in output (select/group_by)
- Example: "what is the biggest state" = `run: state -> { select: state_name, area; order_by: area desc; limit: 1 }`
- HANDLING TIES: When there may be multiple records with the same max/min value, use having: to return ALL tied records:
  `{ group_by: name; aggregate: cnt is items.count() } -> { select: *; having: cnt = max(cnt) }`

DO NOT:
- Use SQL keywords: IN, EXISTS, UNION, INTERSECT, EXCEPT, SUBQUERY
- Put aggregates in where: clauses (use `having:` or pipeline instead)
- Use filter() function - not valid Malloy syntax
- Use inline joins in queries - joins must be in source definitions (join_one/join_many)
- Create new aggregates in second pipeline stage - only filter/select
- Create pipeline stages without a view type - WRONG: `-> { where: x > 0 }` CORRECT: `-> { select: *; where: x > 0 }`
- Put { where: } BEFORE .count() - always put it AFTER
- Use `aggregate: dimension_field` - dimensions are scalar, use max/min/avg or group_by
- Use `run:` inside another query (NO SUBQUERIES) - use pipelines instead
- Use `count(distinct field)` - DEPRECATED, use `count(field)` instead

## Available Sources: activity, participates_in_with_activity, faculty_participates_in_with_activity, student, faculty, participates_in, faculty_participates_in

## Semantic Layer

```malloy
// =============================================================================
// ACTIVITY_1 DATABASE - University Activities System
// =============================================================================
// This database tracks students, faculty, and their participation in activities:
// - Student: university students with demographic info
// - Faculty: university faculty members
// - Activity: extracurricular activities offered
// - Participates_in: which students do which activities
// - Faculty_Participates_in: which faculty supervise/participate in activities
//
// KEY RELATIONSHIPS:
// - Student participates in Activity (via Participates_in junction)
// - Faculty participates in Activity (via Faculty_Participates_in junction)
// - Faculty advises Student (via Student.advisor = Faculty.fac_id)
//
// COMMON QUERY PATTERNS:
// - "activities for [student]": student -> participates_in.activity
// - "students in [activity]": participates_in where activity.name = X
// - "faculty who do [activity]": faculty -> faculty_participates_in.activity
// - "students advised by [faculty]": faculty -> student (via advisor)
// - "activities with most participants": group by activity, count participates_in
// =============================================================================

// ACTIVITY TABLE
// List of activities students and faculty can participate in
source: activity_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Activity')
""") extend {
  dimension:
    // Unique activity identifier
    act_id is actid

    // Name of the activity
    // Values: 'Mountain Climbing', 'Canoeing', 'Kayaking', 'Spelunking',
    //         'Soccer', 'Baseball', 'Football', 'Volleyball', 'Chess', etc.
    name is activity_name

  primary_key: act_id

  measure:
    activity_count is count()
}

// STUDENT TABLE
// University students who can participate in activities
source: student_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Student')
""") extend {
  dimension:
    // Unique student identifier
    stu_id is StuID

    // Student's last name
    // Examples: 'Smith', 'Kim', 'Jones', 'Kumar', 'Gompers'
    last_name is LName

    // Student's first name
    // Examples: 'Linda', 'Tracy', 'Shiela', 'Dinesh', 'Paul'
    first_name is Fname

    // Student's age
    age is Age

    // Sex: 'M' or 'F'
    sex is Sex

    // Academic major code
    major is Major

    // Faculty advisor ID
    advisor is Advisor

    // City code
    student_city is city_code

  primary_key: stu_id

  measure:
    student_count is count()
}

// FACULTY TABLE
// University faculty members who can advise students and participate in activities
source: faculty_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Faculty')
""") extend {
  dimension:
    // Unique faculty identifier
    fac_id is FacID

    // Faculty last name
    // Examples: 'Giuliano', 'Goodrich', 'Masson', 'Runolfsson', 'Naiman'
    last_name is Lname

    // Faculty first name
    // Examples: 'Mark', 'Michael', 'Gerald', 'Thordur', 'Daniel'
    first_name is Fname

    // Academic rank
    // Values: 'Professor', 'AsstProf', 'Instructor', 'AssocProf'
    rank is Rank

    // Sex: 'M' or 'F'
    sex is Sex

    // Phone number
    phone is Phone

    // Room number
    room is Room

    // Building name
    building is Building

  primary_key: fac_id

  measure:
    faculty_count is count()
}

// PARTICIPATES_IN TABLE (Junction)
// Links students to their activities
source: participates_in_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Participates_in')
""") extend {
  dimension:
    stu_id is stuid
    act_id is actid

  measure:
    participation_count is count()
}

// FACULTY_PARTICIPATES_IN TABLE (Junction)
// Links faculty to activities they supervise/participate in
source: faculty_participates_in_base is duckdb.sql("""
  SELECT * FROM sqlite_scan('/workspace/spider_db/spider/database/activity_1/activity_1.sqlite', 'Faculty_Participates_in')
""") extend {
  dimension:
    fac_id is FacID
    act_id is actid

  measure:
    faculty_participation_count is count()
}

// =============================================================================
// FULL SOURCES WITH RELATIONSHIPS
// =============================================================================

// Activity with participants
source: activity is activity_base extend {
  join_many: participates_in is participates_in_base on act_id = participates_in.act_id
  join_many: faculty_participates_in is faculty_participates_in_base on act_id = faculty_participates_in.act_id
}

// Participates_in with activity info (for nested joins)
source: participates_in_with_activity is participates_in_base extend {
  join_one: activity is activity_base on act_id = activity.act_id
}

// Faculty_participates_in with activity info (for nested joins)
source: faculty_participates_in_with_activity is faculty_participates_in_base extend {
  join_one: activity is activity_base on act_id = activity.act_id
}

// Student with their activities (includes nested activity details)
source: student is student_base extend {
  join_many: participates_in is participates_in_with_activity on stu_id = participates_in.stu_id
}

// Faculty with their activities AND students they advise
source: faculty is faculty_base extend {
  join_many: faculty_participates_in is faculty_participates_in_with_activity on fac_id = faculty_participates_in.fac_id
  join_many: student is student_base on fac_id = student.advisor  // students this faculty advises
}

// Participation with full details
source: participates_in is participates_in_base extend {
  join_one: student is student_base on stu_id = student.stu_id
  join_one: activity is activity_base on act_id = activity.act_id
}

// Faculty participation with full details
source: faculty_participates_in is faculty_participates_in_base extend {
  join_one: faculty is faculty_base on fac_id = faculty.fac_id
  join_one: activity is activity_base on act_id = activity.act_id
}

```

## Question

What is the name of the activity that has the most faculty members involved in?

## Solution Strategy

Goal: Find activity with highest faculty participation count
Tables needed: activity, faculty_participates_in
Join path: activity -> faculty_participates_in
Filters: None
Aggregation: group by activity.name, measure: count faculty, order: descending, limit: 1
Malloy approach: Group by activity, count participants, order desc, limit 1

## Instructions

Using the solution strategy above, generate the Malloy query. Use source names and field names exactly as defined in the semantic layer.
Output ONLY the Malloy query. No explanation. No markdown. Just the query starting with `run:`

Query:
```

---

## Key Observations

- Baseline prompt length: 11045 characters, 300 lines
- Reasoning prompt length: 11631 characters, 311 lines
- Difference: +586 characters, +11 lines
