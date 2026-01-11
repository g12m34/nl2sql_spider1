#!/usr/bin/env python3
"""
Generate FULL Malloy semantic layers for all Spider databases.

This script creates complete semantic layers with:
- ALL columns as dimensions
- Appropriate measures for numeric columns
- Primary key declarations
- Join definitions based on foreign keys
- Proper handling of reserved words
"""

import json
from pathlib import Path
from collections import defaultdict

# Malloy/SQL reserved words that need backticks
RESERVED_WORDS = {
    'year', 'date', 'time', 'timestamp', 'name', 'type', 'value', 'key',
    'order', 'group', 'by', 'limit', 'offset', 'count', 'sum', 'avg', 'min', 'max',
    'select', 'from', 'where', 'join', 'on', 'and', 'or', 'not', 'in', 'is', 'null',
    'true', 'false', 'all', 'any', 'as', 'asc', 'desc', 'having', 'union', 'except',
    'intersect', 'case', 'when', 'then', 'else', 'end', 'between', 'like', 'index',
    'primary', 'foreign', 'references', 'default', 'check', 'unique', 'constraint',
    'create', 'table', 'drop', 'alter', 'add', 'column', 'delete', 'insert', 'update',
    'set', 'values', 'into', 'distinct', 'top', 'percent', 'with', 'over', 'partition',
    'row', 'rows', 'range', 'unbounded', 'preceding', 'following', 'current', 'first',
    'last', 'nulls', 'rank', 'dense_rank', 'row_number', 'lead', 'lag', 'ntile',
    'language', 'code', 'level', 'action', 'position', 'match', 'data', 'result',
    # Additional reserved words found during testing
    'number', 'hours', 'minutes', 'cast', 'round', 'state', 'block', 'person',
    'people', 'student', 'club', 'events', 'staff', 'actor', 'day', 'month', 'week',
    'second', 'minute', 'hour', 'quarter'
}


def clean_identifier(name):
    """Clean a name to be a valid identifier, removing special chars."""
    import re
    # Remove parentheses and their contents, or replace with underscore
    result = re.sub(r'\([^)]*\)', '', name)
    # Replace spaces and special chars with underscores
    result = result.replace(' ', '_').replace('-', '_').replace('.', '_')
    result = result.replace('/', '_').replace('\\', '_').replace("'", '')
    # Remove any remaining non-alphanumeric chars except underscore
    result = re.sub(r'[^a-zA-Z0-9_]', '', result)
    # Clean up multiple underscores
    result = re.sub('_+', '_', result).strip('_')
    return result


def needs_quoting(name):
    """Check if a name needs to be quoted."""
    # If it has special characters, always quote
    if any(c in name for c in '()[] -/%'):
        return True
    # If it starts with a number or special char
    if name and (name[0].isdigit() or not name[0].isalpha() and name[0] != '_'):
        return True
    # If it's a reserved word
    if name.lower() in RESERVED_WORDS:
        return True
    return False


def quote_if_reserved(name):
    """Quote column name if it's a reserved word or has special chars."""
    if needs_quoting(name):
        return f'`{name}`'
    return name


def to_snake_case(name):
    """Convert column name to snake_case dimension name."""
    import re
    # First clean the name of special chars
    result = clean_identifier(name)
    # Convert camelCase to snake_case
    result = re.sub('([A-Z])', r'_\1', result).lower()
    # Clean up multiple underscores
    result = re.sub('_+', '_', result).strip('_')
    # If the result is a reserved word, add suffix
    if result.lower() in RESERVED_WORDS:
        result = result + '_val'
    # If result is empty or starts with number, prefix with underscore
    if not result or result[0].isdigit():
        result = 'col_' + result
    return result


def get_source_name(table_name):
    """Get a safe source name for a table, avoiding reserved words."""
    source_name = to_snake_case(table_name)
    if source_name.lower() in RESERVED_WORDS:
        source_name = source_name + '_src'
    return source_name


def load_spider_schemas(tables_path):
    """Load all database schemas from tables.json."""
    with open(tables_path, 'r') as f:
        tables_data = json.load(f)
    return {db['db_id']: db for db in tables_data}


def get_db_path(db_id):
    """Get the path to the SQLite database file."""
    return f'/workspace/spider_db/spider/database/{db_id}/{db_id}.sqlite'


def analyze_schema(schema):
    """Analyze schema to extract tables, columns, types, PKs, and FKs."""
    table_names_orig = schema.get('table_names_original', schema.get('table_names', []))
    column_info = schema.get('column_names_original', schema.get('column_names', []))
    column_types = schema.get('column_types', [])
    primary_keys = schema.get('primary_keys', [])
    foreign_keys = schema.get('foreign_keys', [])

    # Build table info
    tables = {}
    for i, table_name in enumerate(table_names_orig):
        # Skip sqlite internal tables
        if table_name.lower() in ('sqlite_sequence', 'sqlite_stat1'):
            continue
        tables[i] = {
            'name': table_name,
            'columns': [],
            'primary_key': None,
            'foreign_keys': []
        }

    # Map columns to tables
    for col_idx, (table_idx, col_name) in enumerate(column_info):
        if table_idx < 0:  # Skip * column
            continue
        if table_idx not in tables:  # Skip columns from ignored tables
            continue
        col_type = column_types[col_idx] if col_idx < len(column_types) else 'text'
        tables[table_idx]['columns'].append({
            'name': col_name,
            'type': col_type,
            'index': col_idx
        })

    # Map primary keys
    for pk_col_idx in primary_keys:
        for table_idx, table_info in tables.items():
            for col in table_info['columns']:
                if col['index'] == pk_col_idx:
                    table_info['primary_key'] = col['name']
                    break

    # Map foreign keys
    for fk_col_idx, pk_col_idx in foreign_keys:
        # Find which table the FK column belongs to
        fk_table_idx = None
        fk_col_name = None
        for t_idx, t_info in tables.items():
            for col in t_info['columns']:
                if col['index'] == fk_col_idx:
                    fk_table_idx = t_idx
                    fk_col_name = col['name']
                    break
            if fk_table_idx is not None:
                break

        # Find which table the PK column belongs to
        pk_table_idx = None
        pk_col_name = None
        for t_idx, t_info in tables.items():
            for col in t_info['columns']:
                if col['index'] == pk_col_idx:
                    pk_table_idx = t_idx
                    pk_col_name = col['name']
                    break
            if pk_table_idx is not None:
                break

        if fk_table_idx is not None and pk_table_idx is not None:
            tables[fk_table_idx]['foreign_keys'].append({
                'column': fk_col_name,
                'ref_table_idx': pk_table_idx,
                'ref_column': pk_col_name
            })

    return tables


def topological_sort(tables):
    """Sort tables so that referenced tables come before referencing tables."""
    # Build dependency graph
    table_indices = list(tables.keys())
    deps = {idx: set() for idx in table_indices}

    for idx, info in tables.items():
        for fk in info['foreign_keys']:
            ref_idx = fk['ref_table_idx']
            # Skip self-references (table referencing itself)
            if ref_idx != idx and ref_idx in tables:
                deps[idx].add(ref_idx)

    # Kahn's algorithm for topological sort
    in_degree = {idx: len(deps[idx]) for idx in table_indices}

    # Start with tables that have no dependencies
    queue = [idx for idx, deg in in_degree.items() if deg == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        # Update dependencies
        for idx in table_indices:
            if node in deps[idx]:
                deps[idx].remove(node)
                in_degree[idx] -= 1
                if in_degree[idx] == 0 and idx not in result and idx not in queue:
                    queue.append(idx)

    # Add any remaining (cyclic deps) at the end
    for idx in table_indices:
        if idx not in result:
            result.append(idx)

    return result


def generate_malloy_source(db_id, tables):
    """Generate complete Malloy source code with all lowercase snake_case."""
    db_path = get_db_path(db_id)
    lines = []

    lines.append(f"// Malloy semantic layer for: {db_id}")
    lines.append(f"// Full layer with ALL columns, primary keys, and joins")
    lines.append(f"// Database: {db_path}")
    lines.append("")

    # Sort tables for proper dependency order
    sorted_indices = topological_sort(tables)

    # Build table_idx -> source_name mapping
    source_names = {idx: get_source_name(tables[idx]['name']) for idx in tables}

    # Build column name -> snake_case mapping for each table
    # We'll define ALL columns as dimensions with snake_case names
    table_col_maps = {}
    for idx, info in tables.items():
        col_map = {}
        for col in info['columns']:
            col_map[col['name']] = to_snake_case(col['name'])
        table_col_maps[idx] = col_map

    for table_idx in sorted_indices:
        table_info = tables[table_idx]
        table_name = table_info['name']
        source_name = source_names[table_idx]
        col_map = table_col_maps[table_idx]

        lines.append(f"// {table_name}")
        lines.append(f'source: {source_name} is duckdb.sql("""')
        lines.append(f"  SELECT * FROM sqlite_scan('{db_path}', '{table_name}')")
        lines.append('""") extend {')

        # Dimensions - define columns that need renaming to snake_case
        # Track which columns have dimensions defined
        has_dimension = set()
        dim_definitions = []
        for col in table_info['columns']:
            dim_name = col_map[col['name']]
            orig_name = col['name']
            # Skip if dimension name equals original (would be a redefinition)
            if dim_name.lower() == orig_name.lower() and not needs_quoting(orig_name):
                continue
            quoted_orig = quote_if_reserved(orig_name)
            dim_definitions.append(f"    {dim_name} is {quoted_orig}")
            has_dimension.add(col['name'])

        if dim_definitions:
            lines.append("  dimension:")
            lines.extend(dim_definitions)
            lines.append("")

        # Primary key - use dimension name if defined, else original column name
        if table_info['primary_key']:
            pk_orig = table_info['primary_key']
            if pk_orig in has_dimension:
                pk_ref = col_map.get(pk_orig, to_snake_case(pk_orig))
            else:
                pk_ref = quote_if_reserved(pk_orig)
            lines.append(f"  primary_key: {pk_ref}")
            lines.append("")

        # Joins - use dimension names if defined, else original column names
        if table_info['foreign_keys']:
            # Count how many times each target table is joined (excluding self-joins)
            join_counts = defaultdict(int)
            for fk in table_info['foreign_keys']:
                if fk['ref_table_idx'] in tables and fk['ref_table_idx'] != table_idx:
                    join_counts[fk['ref_table_idx']] += 1

            # Get all column names in this table (to detect conflicts)
            col_names = set(col_map.values())

            # Build has_dimension set for referenced tables
            ref_has_dimension = {}
            for ref_idx in tables:
                ref_has_dim = set()
                for c in tables[ref_idx]['columns']:
                    c_snake = to_snake_case(c['name'])
                    if c_snake.lower() != c['name'].lower() or needs_quoting(c['name']):
                        ref_has_dim.add(c['name'])
                ref_has_dimension[ref_idx] = ref_has_dim

            # Track used join names within this source
            used_join_names = set()
            for fk in table_info['foreign_keys']:
                # Skip self-joins (table referencing itself)
                if fk['ref_table_idx'] == table_idx:
                    continue
                ref_table = tables.get(fk['ref_table_idx'])
                if ref_table:
                    ref_source_name = source_names[fk['ref_table_idx']]
                    ref_col_map = table_col_maps[fk['ref_table_idx']]

                    # Use dimension name if defined, else quoted original
                    fk_col_snake = col_map.get(fk['column'], to_snake_case(fk['column']))
                    if fk['column'] in has_dimension:
                        fk_col_ref = fk_col_snake
                    else:
                        fk_col_ref = quote_if_reserved(fk['column'])

                    ref_col_snake = ref_col_map.get(fk['ref_column'], to_snake_case(fk['ref_column']))
                    if fk['ref_column'] in ref_has_dimension.get(fk['ref_table_idx'], set()):
                        ref_col_ref = ref_col_snake
                    else:
                        ref_col_ref = quote_if_reserved(fk['ref_column'])

                    # Need alias if: multiple joins to same table, or source name already used,
                    # or source name conflicts with a column name
                    needs_alias = (
                        join_counts[fk['ref_table_idx']] > 1 or
                        ref_source_name in used_join_names or
                        ref_source_name in col_names
                    )

                    if needs_alias:
                        # Use FK column name to create alias
                        alias_base = fk_col_snake.replace('_id', '').replace('_val', '')
                        if not alias_base or alias_base == ref_source_name:
                            alias_base = 'ref'
                        alias = f"{alias_base}_{ref_source_name}"
                        # Ensure unique
                        counter = 2
                        orig_alias = alias
                        while alias in used_join_names or alias in col_names:
                            alias = f"{orig_alias}_{counter}"
                            counter += 1
                        lines.append(f"  join_one: {alias} is {ref_source_name} on {fk_col_ref} = {alias}.{ref_col_ref}")
                        used_join_names.add(alias)
                    else:
                        lines.append(f"  join_one: {ref_source_name} on {fk_col_ref} = {ref_source_name}.{ref_col_ref}")
                        used_join_names.add(ref_source_name)
            lines.append("")

        # Measures - use dimension name if defined, else original column name
        numeric_cols = [c for c in table_info['columns'] if c['type'] == 'number']
        lines.append("  measure:")
        lines.append("    row_count is count()")
        for col in numeric_cols:
            dim_name = col_map[col['name']]
            # Use dimension name if we created one, else use quoted original
            if col['name'] in has_dimension:
                ref_name = dim_name
            else:
                ref_name = quote_if_reserved(col['name'])
            lines.append(f"    total_{dim_name} is sum({ref_name})")
            lines.append(f"    avg_{dim_name} is avg({ref_name})")
            lines.append(f"    max_{dim_name} is max({ref_name})")
            lines.append(f"    min_{dim_name} is min({ref_name})")

        lines.append("}")
        lines.append("")

    return '\n'.join(lines)


def main():
    tables_path = Path('/workspace/spider_db/spider/tables.json')
    output_dir = Path('/workspace/project/malloy/full')
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Spider schemas...")
    schemas = load_spider_schemas(tables_path)
    print(f"Found {len(schemas)} database schemas")

    stats = {'success': 0, 'failed': 0, 'errors': []}

    for db_id, schema in sorted(schemas.items()):
        try:
            tables = analyze_schema(schema)
            if not tables:
                print(f"  SKIP {db_id}: no tables found")
                continue

            malloy_code = generate_malloy_source(db_id, tables)

            output_path = output_dir / f"{db_id}.malloy"
            with open(output_path, 'w') as f:
                f.write(malloy_code)

            table_count = len(tables)
            col_count = sum(len(t['columns']) for t in tables.values())
            print(f"  OK {db_id}: {table_count} tables, {col_count} columns")
            stats['success'] += 1

        except Exception as e:
            print(f"  FAIL {db_id}: {str(e)}")
            stats['failed'] += 1
            stats['errors'].append({'db_id': db_id, 'error': str(e)})

    print(f"\n{'='*60}")
    print("GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Success: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Output directory: {output_dir}")

    if stats['errors']:
        print("\nErrors:")
        for err in stats['errors']:
            print(f"  {err['db_id']}: {err['error']}")


if __name__ == '__main__':
    main()
