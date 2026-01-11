# Malloy Semantic Layer Patterns

## Learned from Malloy Documentation

### Core Syntax Patterns

#### 1. Source Definition with SQLite
```malloy
source: table_name is duckdb.table('path/to/database.sqlite', 'TableName') extend {
  // extensions here
}
```

#### 2. Primary Key Declaration
```malloy
source: users is duckdb.table('db.sqlite', 'users') extend {
  primary_key: user_id
}
```

#### 3. Dimension Definitions
```malloy
source: products is duckdb.table('db.sqlite', 'products') extend {
  dimension:
    product_name is Name           // rename column
    is_active is status = 'active' // calculated dimension
}
```

#### 4. Measure Definitions
```malloy
source: orders is duckdb.table('db.sqlite', 'orders') extend {
  measure:
    row_count is count()
    total_amount is sum(amount)
    avg_amount is avg(amount)
    min_amount is min(amount)
    max_amount is max(amount)
}
```

#### 5. Join Patterns

**join_one with foreign key (requires primary_key on joined source):**
```malloy
source: orders is duckdb.table('db.sqlite', 'orders') extend {
  join_one: customers with customer_id
}
```

**join_one with explicit condition:**
```malloy
source: orders is duckdb.table('db.sqlite', 'orders') extend {
  join_one: customers on customer_id = customers.id
}
```

**join_one with alias:**
```malloy
source: flights is duckdb.table('db.sqlite', 'flights') extend {
  join_one: origin_airport is airports on origin = airports.code
  join_one: dest_airport is airports on destination = airports.code
}
```

**join_many for one-to-many:**
```malloy
source: customers is duckdb.table('db.sqlite', 'customers') extend {
  join_many: orders on id = orders.customer_id
}
```

### Key Rules

1. **Join Direction**:
   - `join_one` = joined table has ONE row per source row (many-to-one)
   - `join_many` = joined table has MANY rows per source row (one-to-many)

2. **Primary Keys Required**: For `with` syntax joins, the joined source must have `primary_key` declared

3. **Default Join Type**: All Malloy joins are LEFT OUTER joins by default

4. **Field Access**: After joining, access fields via `joined_source.field_name`

### Complete Source Template
```malloy
// Source: table_name
// Purpose: Description of the table
source: table_name is duckdb.table('path/to/db.sqlite', 'OriginalTableName') extend {
  primary_key: id_column

  // Joins (based on foreign keys)
  join_one: related_table with foreign_key_column
  // OR with explicit condition:
  // join_one: related_table on foreign_key = related_table.primary_key

  // Dimensions - all columns with readable names
  dimension:
    column_name is OriginalColumnName
    another_col is AnotherColumn

  // Measures - aggregations for numeric columns
  measure:
    row_count is count()
    total_numeric is sum(numeric_column)
    avg_numeric is avg(numeric_column)
    min_numeric is min(numeric_column)
    max_numeric is max(numeric_column)
}
```

---

## Spider Database Conventions

For Spider databases, we'll use:

1. **Database Path**: `/workspace/spider_db/spider/database/{db_id}/{db_id}.sqlite`

2. **Source Names**: lowercase with underscores (match table name)

3. **Dimension Names**: lowercase with underscores

4. **Measure Names**: `{agg}_{column}` pattern (e.g., `avg_age`, `sum_capacity`)

5. **Comments**: Brief description of table purpose

---

## Example: concert_singer Database

Schema:
- stadium (Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
- singer (Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- concert (concert_ID, concert_Name, Theme, Stadium_ID, Year)
- singer_in_concert (concert_ID, Singer_ID)

```malloy
// Malloy semantic layer for: concert_singer
// Database: /workspace/spider_db/spider/database/concert_singer/concert_singer.sqlite

source: stadium is duckdb.table('../data/concert_singer.sqlite', 'stadium') extend {
  primary_key: Stadium_ID

  dimension:
    stadium_id is Stadium_ID
    location is Location
    name is Name
    capacity is Capacity
    highest is Highest
    lowest is Lowest
    average is Average

  measure:
    row_count is count()
    total_capacity is sum(Capacity)
    avg_capacity is avg(Capacity)
    max_capacity is max(Capacity)
    min_capacity is min(Capacity)
}

source: singer is duckdb.table('../data/concert_singer.sqlite', 'singer') extend {
  primary_key: Singer_ID

  dimension:
    singer_id is Singer_ID
    name is Name
    country is Country
    song_name is Song_Name
    song_release_year is Song_release_year
    age is Age
    is_male is Is_male

  measure:
    row_count is count()
    avg_age is avg(Age)
    max_age is max(Age)
    min_age is min(Age)
}

source: concert is duckdb.table('../data/concert_singer.sqlite', 'concert') extend {
  primary_key: concert_ID

  join_one: stadium with Stadium_ID

  dimension:
    concert_id is concert_ID
    concert_name is concert_Name
    theme is Theme
    stadium_id is Stadium_ID
    year is Year

  measure:
    row_count is count()
}

source: singer_in_concert is duckdb.table('../data/concert_singer.sqlite', 'singer_in_concert') extend {
  join_one: concert with concert_ID
  join_one: singer with Singer_ID

  dimension:
    concert_id is concert_ID
    singer_id is Singer_ID

  measure:
    row_count is count()
}
```
