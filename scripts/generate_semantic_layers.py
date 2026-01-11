#!/usr/bin/env python3
"""
Generate Malloy semantic layers from Spider ground-truth SQL queries.

This script analyzes the correct SQL queries for each database to determine:
- Which tables are actually used
- Which columns are used as dimensions (SELECT, WHERE, GROUP BY, ORDER BY)
- Which columns are used in aggregations (COUNT, SUM, AVG, MIN, MAX)
- Join patterns between tables

The output is Malloy source files that capture exactly what's needed to answer
the Spider questions, without over-engineering unused features.
"""

import json
import re
import os
from collections import defaultdict
from pathlib import Path


def load_spider_data(base_path):
    """Load Spider dataset files."""
    # Try multiple possible paths
    possible_paths = [
        base_path,
        base_path / 'spider',
        base_path / 'evaluation_examples' / 'examples',
        base_path / 'spider' / 'evaluation_examples' / 'examples',
    ]

    examples_path = None
    for p in possible_paths:
        if (p / 'dev.json').exists():
            examples_path = p
            break

    if examples_path is None:
        raise FileNotFoundError(f"Could not find Spider data files in {base_path}")

    with open(examples_path / 'dev.json', 'r') as f:
        dev_data = json.load(f)
    with open(examples_path / 'train_spider.json', 'r') as f:
        train_data = json.load(f)
    with open(examples_path / 'tables.json', 'r') as f:
        tables_data = json.load(f)

    return dev_data + train_data, {db['db_id']: db for db in tables_data}


def analyze_sql_queries(queries, schema):
    """Analyze SQL queries to extract semantic layer requirements."""

    table_names = [t.lower() for t in schema.get('table_names_original', schema.get('table_names', []))]
    column_info = schema.get('column_names_original', schema.get('column_names', []))
    column_types = schema.get('column_types', [])

    # Build column lookup: table_idx -> [(col_name, col_type), ...]
    table_columns = defaultdict(list)
    for i, (table_idx, col_name) in enumerate(column_info):
        if table_idx >= 0:
            col_type = column_types[i] if i < len(column_types) else 'text'
            table_columns[table_idx].append((col_name.lower(), col_type))

    analysis = {
        'tables_used': set(),
        'dimensions': defaultdict(set),
        'measures': defaultdict(lambda: defaultdict(set)),
        'joins_detected': set(),
        'query_count': len(queries),
    }

    for sql in queries:
        sql_lower = sql.lower()

        # Find tables and columns used
        for i, table in enumerate(table_names):
            if re.search(rf'\b{re.escape(table)}\b', sql_lower):
                analysis['tables_used'].add(table)

                for col_name, col_type in table_columns[i]:
                    if re.search(rf'\b{re.escape(col_name)}\b', sql_lower):
                        analysis['dimensions'][table].add(col_name)

                        # Check for aggregates
                        for agg in ['count', 'sum', 'avg', 'min', 'max']:
                            if re.search(rf'{agg}\s*\([^)]*\b{re.escape(col_name)}\b', sql_lower):
                                analysis['measures'][table][agg].add(col_name)

        # Detect join patterns
        join_pattern = r'(\w+)\s*\.\s*(\w+)\s*=\s*(\w+)\s*\.\s*(\w+)'
        for match in re.finditer(join_pattern, sql_lower):
            t1, c1, t2, c2 = match.groups()
            if t1 in table_names and t2 in table_names:
                # Normalize join order
                if t1 > t2:
                    t1, c1, t2, c2 = t2, c2, t1, c1
                analysis['joins_detected'].add((t1, c1, t2, c2))

    return analysis


def generate_malloy_source(db_id, analysis, schema):
    """Generate Malloy source code from analysis."""

    table_names_orig = schema.get('table_names_original', schema.get('table_names', []))
    column_info = schema.get('column_names_original', schema.get('column_names', []))
    column_types = schema.get('column_types', [])

    # Map table names (lowercase -> original case)
    table_case_map = {t.lower(): t for t in table_names_orig}

    # Map columns per table with original case and type
    table_columns = defaultdict(dict)
    for i, (table_idx, col_name) in enumerate(column_info):
        if table_idx >= 0:
            table_lower = table_names_orig[table_idx].lower()
            col_type = column_types[i] if i < len(column_types) else 'text'
            table_columns[table_lower][col_name.lower()] = {
                'original': col_name,
                'type': col_type
            }

    lines = []
    lines.append(f"// Malloy semantic layer for: {db_id}")
    lines.append(f"// Auto-generated from {analysis['query_count']} ground-truth SQL queries")
    lines.append(f"// Tables used: {len(analysis['tables_used'])}")
    lines.append(f"//")
    lines.append(f"// This file contains only the dimensions and measures that are")
    lines.append(f"// actually needed to answer the Spider benchmark questions.")
    lines.append("")

    # Generate source for each table
    for table in sorted(analysis['tables_used']):
        orig_table = table_case_map.get(table, table)
        lines.append(f"source: {table} is duckdb.table('{orig_table}') extend {{")

        # Dimensions
        dims = analysis['dimensions'].get(table, set())
        if dims:
            lines.append("  dimension:")
            for col in sorted(dims):
                col_info = table_columns[table].get(col, {'original': col, 'type': 'text'})
                orig_col = col_info['original']
                # Use lowercase name as the dimension name, original as the reference
                lines.append(f"    {col} is {orig_col}")

        # Measures
        measures = analysis['measures'].get(table, {})
        if measures or dims:  # Always add row_count if table is used
            lines.append("  measure:")
            lines.append(f"    row_count is count()")

            for agg_type in ['sum', 'avg', 'min', 'max', 'count']:
                cols = measures.get(agg_type, set())
                for col in sorted(cols):
                    if agg_type == 'count' and col == '*':
                        continue  # Already have row_count
                    measure_name = f"{agg_type}_{col}"
                    lines.append(f"    {measure_name} is {agg_type}({col})")

        lines.append("}")
        lines.append("")

    # Add join relationships as comments for reference
    if analysis['joins_detected']:
        lines.append("// Join patterns detected in queries:")
        for t1, c1, t2, c2 in sorted(analysis['joins_detected']):
            lines.append(f"// JOIN: {t1}.{c1} = {t2}.{c2}")
        lines.append("")

        # TODO: Could generate actual Malloy join syntax here
        # This requires determining which table is the "one" vs "many" side

    return '\n'.join(lines)


def generate_analysis_report(db_id, analysis):
    """Generate a JSON analysis report for a database."""
    return {
        'db_id': db_id,
        'query_count': analysis['query_count'],
        'tables_used': sorted(analysis['tables_used']),
        'dimensions': {t: sorted(cols) for t, cols in analysis['dimensions'].items()},
        'measures': {
            t: {agg: sorted(cols) for agg, cols in aggs.items()}
            for t, aggs in analysis['measures'].items()
        },
        'joins': [
            {'left_table': t1, 'left_col': c1, 'right_table': t2, 'right_col': c2}
            for t1, c1, t2, c2 in sorted(analysis['joins_detected'])
        ]
    }


def main():
    # Paths - using the downloaded Spider dataset
    base_path = Path('/workspace/spider')  # Contains evaluation_examples/examples/
    output_dir = Path('/workspace/project/malloy/minimal')
    analysis_dir = Path('/workspace/project/malloy/analysis')

    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    print("Loading Spider dataset...")
    all_data, db_schemas = load_spider_data(base_path)

    # Group queries by database
    db_queries = defaultdict(list)
    for item in all_data:
        db_queries[item['db_id']].append(item['query'])

    print(f"Found {len(db_queries)} databases with queries")
    print(f"Found {len(db_schemas)} database schemas")

    # Generate semantic layers
    all_analyses = {}
    stats = {'success': 0, 'skipped': 0, 'total_queries': 0}

    for db_id in sorted(db_queries.keys()):
        if db_id not in db_schemas:
            print(f"  SKIP {db_id}: no schema found")
            stats['skipped'] += 1
            continue

        queries = db_queries[db_id]
        schema = db_schemas[db_id]

        # Analyze queries
        analysis = analyze_sql_queries(queries, schema)
        all_analyses[db_id] = analysis

        # Generate Malloy source
        malloy_code = generate_malloy_source(db_id, analysis, schema)

        # Write Malloy file
        malloy_path = output_dir / f"{db_id}.malloy"
        with open(malloy_path, 'w') as f:
            f.write(malloy_code)

        # Write analysis JSON
        analysis_report = generate_analysis_report(db_id, analysis)
        analysis_path = analysis_dir / f"{db_id}.json"
        with open(analysis_path, 'w') as f:
            json.dump(analysis_report, f, indent=2)

        stats['success'] += 1
        stats['total_queries'] += len(queries)

        print(f"  OK {db_id}: {len(queries)} queries, {len(analysis['tables_used'])} tables, "
              f"{sum(len(d) for d in analysis['dimensions'].values())} dims, "
              f"{sum(len(m) for a in analysis['measures'].values() for m in a.values())} measures")

    # Summary
    print(f"\n{'='*60}")
    print("GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Databases processed: {stats['success']}")
    print(f"Databases skipped: {stats['skipped']}")
    print(f"Total queries analyzed: {stats['total_queries']}")
    print(f"Output directory: {output_dir}")
    print(f"Analysis directory: {analysis_dir}")

    # Write summary
    summary = {
        'databases_processed': stats['success'],
        'databases_skipped': stats['skipped'],
        'total_queries': stats['total_queries'],
        'databases': list(all_analyses.keys())
    }
    with open(analysis_dir / '_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)


if __name__ == '__main__':
    main()
