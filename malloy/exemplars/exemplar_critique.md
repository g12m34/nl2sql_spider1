# Exemplar Critique and Learnings

## Exemplar 1: concert_singer

### What Worked
1. **sqlite_scan syntax** - `duckdb.sql("SELECT * FROM sqlite_scan('path', 'table')")` works correctly
2. **Primary keys** - Declaring `primary_key: field` enables join_one with `with` syntax
3. **Join definitions** - `join_one: table on fk = table.pk` works correctly
4. **Measures** - count(), sum(), avg(), min(), max() all work
5. **Dimensions** - Direct column references work

### Issues Found
1. **Reserved word: Year** - Had to use backticks: `` `Year` `` and rename to `concert_year`
2. **Query syntax** - In test queries, use `group_by:` not `select:` to output fields
3. **Order by** - Fields must be in output space (group_by or aggregate) to order by them

### Key Learnings for Full Generation

1. **Reserved Words to Watch:**
   - Year, Name, Date, Time, Index, Order, Group, By, Key, Value, Type, Count, Sum, Avg, Min, Max
   - Solution: Check column names against reserved words and quote them with backticks

2. **SQLite Connection Pattern:**
   ```malloy
   source: table_name is duckdb.sql("""
     SELECT * FROM sqlite_scan('/path/to/db.sqlite', 'TableName')
   """) extend { ... }
   ```

3. **Join Order Matters:**
   - Define sources with primary_key BEFORE sources that join to them
   - Or use explicit `on` syntax if order is unavoidable

4. **Dimension Naming:**
   - Use snake_case for dimension names
   - Map from original column names
   - Prefix reserved words or use backticks

5. **Measure Pattern:**
   ```malloy
   measure:
     row_count is count()
     total_{col} is sum({col})
     avg_{col} is avg({col})
     max_{col} is max({col})
     min_{col} is min({col})
   ```

### Test Results: concert_singer
| Query | Question | Status |
|-------|----------|--------|
| q1 | Singer count | PASS |
| q3 | Singers by age desc | PASS |
| q5 | French singer stats | PASS |
| q7 | Youngest singer song | PASS |
| q9 | Countries with singers > 20 | PASS |

**10/10 questions answered correctly**

---

## Reserved Words Reference

Common SQL/Malloy reserved words to escape:
- `year`, `date`, `time`, `timestamp`
- `name`, `type`, `value`, `key`
- `order`, `group`, `by`, `limit`, `offset`
- `count`, `sum`, `avg`, `min`, `max`
- `select`, `from`, `where`, `join`, `on`
- `and`, `or`, `not`, `in`, `is`, `null`
- `true`, `false`, `all`, `any`

Solution: Use backticks around reserved words: `` `Year` ``
