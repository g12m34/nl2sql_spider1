# Extended Test Set Evaluation Report

*Generated: 2026-01-11*

## Executive Summary

This report evaluates Gemini 3 Flash on two new test sets of 100 questions each, extending beyond our original 46-question benchmark to assess model performance at scale.

### Key Results

| Test Set | Compile Rate | Execution Accuracy |
|----------|--------------|-------------------|
| Hard/Extra (100) | 82.0% | 65.0% |
| Stratified (100) | 87.0% | 75.0% |
| Original (44 evaluated) | 95.7% | 88.6% |

**Observations:**
- Performance degrades on harder questions (65% vs 88.6% on original set)
- Stratified sample shows 75% accuracy, closer to expected real-world performance
- Compile rate drops from 95.7% to 82-87% on larger test sets
- Most failures are in `scholar` database (complex academic paper schema)

## Test Set Composition

### Hard/Extra Set (100 questions)
Questions filtered to only include `hard` and `extra` difficulty levels based on SQL complexity:
- Contains INTERSECT/EXCEPT/UNION operations
- Multiple JOINs
- Subqueries
- Complex aggregations with HAVING

**Distribution by database:**
| Database | Questions | Errors | Error Rate |
|----------|-----------|--------|------------|
| scholar | 58 | 16 | 27.6% |
| movie_1 | 15 | 9 | 60.0% |
| activity_1 | 10 | 5 | 50.0% |
| game_1 | 8 | 2 | 25.0% |
| geo | 5 | 1 | 20.0% |
| ship_1 | 2 | 0 | 0.0% |
| gas_company | 2 | 0 | 0.0% |

### Stratified Set (100 questions)
Proportionally sampled across all difficulty levels:
- Easy: 38 questions
- Medium: 45 questions
- Hard: 8 questions
- Extra: 9 questions

**Distribution by database:**
| Database | Questions | Errors | Error Rate |
|----------|-----------|--------|------------|
| scholar | 45 | 6 | 13.3% |
| geo | 22 | 4 | 18.2% |
| activity_1 | 10 | 3 | 30.0% |
| manufactory_1 | 7 | 4 | 57.1% |
| ship_1 | 5 | 3 | 60.0% |
| game_1 | 4 | 1 | 25.0% |
| behavior_monitoring | 3 | 2 | 66.7% |
| movie_1 | 2 | 1 | 50.0% |
| gas_company | 1 | 1 | 100.0% |
| customers_and_products_contacts | 1 | 0 | 0.0% |

## Error Analysis

### Compile Errors (31 total across both sets)

#### 1. Extraneous Input '.' (10 errors)
**Pattern:** Model uses dot notation in select/group_by where it's not allowed.

**Example:**
```malloy
run: author -> {
  where: author_name = 'oren etzioni'
  select: writes.paper.title, writes.paper.year  // ERROR
}
```

**Fix:** Use `group_by` for joined fields or nest the query properly.

#### 2. Undefined Source (10 errors)
**Pattern:** Model references sources not defined in the semantic layer.

**Examples:**
- `journal` not defined (should use `venue`)
- `order_items` not defined (should use `customer_orders`)
- `keyphrase` not defined directly (should use `paper_keyphrase.keyphrase`)

**Fix:** Improve semantic layer documentation with valid source names.

#### 3. Illegal Statement (5 errors)
**Pattern:** Model uses invalid operations in select queries.

**Example:**
```malloy
run: author -> {
  group_by: author_name
  aggregate: paper_count is writes.count()
} -> {
  select: author_name
  order_by: paper_count desc  // ERROR: paper_count not in output
}
```

**Fix:** Ensure fields referenced in order_by are in the output.

#### 4. Join Path Required (4 errors)
**Pattern:** Model forgets to specify join path for aggregations.

**Example:**
```malloy
aggregate: total_citations is sum(writes.paper.num_cited_by)  // ERROR
```

**Correct:**
```malloy
aggregate: total_citations is writes.paper.num_cited_by.sum()
```

### Logic Errors (29 total across both sets)

#### Same Row Count, Different Content (21 errors)
Most logic errors produce the same number of rows but with different values. This indicates:
- Wrong column selection (e.g., returning name instead of ID)
- Wrong aggregation (e.g., SUM vs COUNT)
- Case sensitivity issues in string matching

#### Different Row Count (8 errors)
| Expected | Got | Likely Cause |
|----------|-----|--------------|
| 0 | 1 | Missing filter, returning default |
| 2 | 1 | Missing UNION/INTERSECT handling |
| 16 | 14 | Incomplete join traversal |
| 18 | 0 | Complete failure to find results |

## Improvement Recommendations

### High Priority (Fix 10+ errors)

1. **Improve Source Name Documentation**
   - Add explicit list of valid source names at top of each semantic layer
   - Add comments for common aliases (e.g., `// venue contains journal information`)
   - Estimated lift: +5% accuracy

2. **Add More Join Path Examples**
   - Document the `.sum()` vs `sum()` pattern more clearly
   - Add examples of nested join aggregations
   - Estimated lift: +2% accuracy

### Medium Priority (Fix 5-10 errors)

3. **Fix Extraneous Dot Errors**
   - Add rule: "Don't use dot notation in select: for joined fields"
   - Provide correct patterns using group_by or nest
   - Estimated lift: +5% accuracy

4. **Handle Complex Queries Better**
   - Add chain-of-thought prompting for hard/extra questions
   - Break complex queries into steps
   - Estimated lift: +3% accuracy

### Lower Priority (Fix <5 errors)

5. **Order_by Field Validation**
   - Add rule about order_by fields needing to be in output
   - Estimated lift: +2% accuracy

## Accuracy by Difficulty

| Difficulty | Questions | Correct | Accuracy |
|------------|-----------|---------|----------|
| Easy | 38 | 34 | 89.5% |
| Medium | 45 | 36 | 80.0% |
| Hard | 8 | 3 | 37.5% |
| Extra | 9 | 2 | 22.2% |

*Based on stratified set. Hard/extra set performance is lower due to selection bias.*

## Comparison with Original Test Set

| Metric | Original (46) | Hard/Extra (100) | Stratified (100) |
|--------|---------------|------------------|------------------|
| Compile Rate | 95.7% | 82.0% | 87.0% |
| Accuracy | 88.6% | 65.0% | 75.0% |
| Compile Errors | 2 | 18 | 13 |
| Logic Errors | 5 | 17 | 12 |

The original test set showed higher accuracy because:
1. It was hand-curated to use enriched semantic layers
2. Questions were selected to test specific patterns
3. Several problematic gold SQL questions were excluded

The extended test sets provide a more realistic assessment of model capabilities.

## Conclusion

Gemini 3 Flash achieves:
- **75% accuracy** on a representative stratified sample
- **65% accuracy** on hard/extra difficulty questions
- **89.5% accuracy** on easy questions

The main failure modes are:
1. Undefined sources (schema linking errors)
2. Incorrect dot notation usage
3. Missing join path specifications
4. Complex query handling

With targeted prompt improvements addressing these patterns, we estimate potential accuracy gains of **+10-15%**, bringing stratified accuracy to **85-90%**.

## Files Generated

- `/workspace/project/evaluation/test_hard_extra_100.json` - Hard/Extra test set
- `/workspace/project/evaluation/test_stratified_100.json` - Stratified test set
- `/workspace/project/evaluation/batch_jobs/eval_results_batches_shisjp9nka04nbr11epse4u5rnjzn3x3mf2q.json` - Hard/Extra evaluation
- `/workspace/project/evaluation/batch_jobs/eval_results_batches_4dmypl3w6zipf3akxi31f84cxks7z84hn4pb.json` - Stratified evaluation
