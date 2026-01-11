#!/usr/bin/env python3
"""
Generate enriched Malloy semantic layers with profiling-based metadata.

Based on insights from "Automatic Metadata Extraction for Text-to-SQL" (AT&T):
- Profile each field to get sample values, distinct counts, NULL stats
- Use LLM to generate meaningful field descriptions
- Add metadata as comments in Malloy semantic layers
"""

import json
import sqlite3
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import Counter
import anthropic

# Configuration
SPIDER_DB_PATH = "/workspace/spider_db/spider/database"
OUTPUT_DIR = "/workspace/project/malloy/full_enriched"
FULL_LAYERS_DIR = "/workspace/project/malloy/full"

# LLM configuration
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"


def profile_field(cursor, table_name: str, column_name: str, column_type: str) -> Dict[str, Any]:
    """Profile a single field to extract statistics."""
    profile = {
        "column_name": column_name,
        "column_type": column_type,
        "total_rows": 0,
        "null_count": 0,
        "distinct_count": 0,
        "min_value": None,
        "max_value": None,
        "sample_values": [],
        "value_patterns": []
    }

    try:
        # Get total rows
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        profile["total_rows"] = cursor.fetchone()[0]

        if profile["total_rows"] == 0:
            return profile

        # Get NULL count
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{column_name}" IS NULL')
        profile["null_count"] = cursor.fetchone()[0]

        # Get distinct count
        cursor.execute(f'SELECT COUNT(DISTINCT "{column_name}") FROM "{table_name}"')
        profile["distinct_count"] = cursor.fetchone()[0]

        # Get min/max for non-null values
        cursor.execute(f'SELECT MIN("{column_name}"), MAX("{column_name}") FROM "{table_name}" WHERE "{column_name}" IS NOT NULL')
        min_max = cursor.fetchone()
        profile["min_value"] = str(min_max[0]) if min_max[0] is not None else None
        profile["max_value"] = str(min_max[1]) if min_max[1] is not None else None

        # Get top-k sample values (most common)
        cursor.execute(f'''
            SELECT "{column_name}", COUNT(*) as cnt
            FROM "{table_name}"
            WHERE "{column_name}" IS NOT NULL
            GROUP BY "{column_name}"
            ORDER BY cnt DESC
            LIMIT 10
        ''')
        samples = cursor.fetchall()
        profile["sample_values"] = [str(s[0]) for s in samples if s[0] is not None]

        # Analyze value patterns (for string fields)
        if profile["sample_values"]:
            lengths = set()
            all_numeric = True
            for val in profile["sample_values"][:5]:
                lengths.add(len(str(val)))
                if not str(val).replace('.', '').replace('-', '').isdigit():
                    all_numeric = False

            if len(lengths) == 1:
                profile["value_patterns"].append(f"Fixed length: {list(lengths)[0]} characters")
            if all_numeric and profile["sample_values"]:
                profile["value_patterns"].append("All numeric values")

    except Exception as e:
        print(f"  Warning: Could not profile {table_name}.{column_name}: {e}")

    return profile


def profile_table(cursor, table_name: str) -> Dict[str, Any]:
    """Profile all columns in a table."""
    # Get column info
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    columns = cursor.fetchall()

    table_profile = {
        "table_name": table_name,
        "columns": {}
    }

    for col in columns:
        col_name = col[1]
        col_type = col[2]
        profile = profile_field(cursor, table_name, col_name, col_type)
        table_profile["columns"][col_name] = profile

    return table_profile


def profile_database(db_path: str) -> Dict[str, Any]:
    """Profile all tables in a database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]

    db_profile = {
        "database_path": db_path,
        "tables": {}
    }

    for table in tables:
        if table.startswith('sqlite_'):
            continue
        db_profile["tables"][table] = profile_table(cursor, table)

    conn.close()
    return db_profile


def generate_field_description_heuristic(table_name: str,
                                         column_name: str,
                                         profile: Dict[str, Any],
                                         other_columns: List[str]) -> str:
    """Generate a meaningful field description using heuristics (no LLM needed)."""

    col_lower = column_name.lower()
    col_type = profile['column_type'].upper()
    distinct = profile['distinct_count']
    total = profile['total_rows']
    null_pct = 100 * profile['null_count'] / max(1, total)
    samples = profile.get('sample_values', [])[:5]

    desc_parts = []

    # Detect primary key / ID columns
    if col_lower.endswith('id') or col_lower.endswith('_id') or col_lower == 'id':
        if distinct == total and null_pct == 0:
            desc_parts.append(f"Primary key identifier for {table_name}")
        else:
            desc_parts.append(f"Foreign key reference")

    # Detect name columns
    elif 'name' in col_lower:
        if distinct == total:
            desc_parts.append(f"Unique name identifier")
        else:
            desc_parts.append(f"Name field with {distinct} distinct values")

    # Detect categorical/enum columns
    elif distinct <= 10 and total > 10:
        if samples:
            sample_str = ', '.join(repr(s) for s in samples[:5])
            desc_parts.append(f"Categorical field: {sample_str}")
        else:
            desc_parts.append(f"Categorical field with {distinct} categories")

    # Detect date/time columns
    elif 'date' in col_lower or 'time' in col_lower or 'year' in col_lower:
        if profile['min_value'] and profile['max_value']:
            desc_parts.append(f"Date/time field ranging from {profile['min_value']} to {profile['max_value']}")
        else:
            desc_parts.append(f"Date/time field")

    # Detect numeric measure columns
    elif 'INTEGER' in col_type or 'REAL' in col_type or 'NUMERIC' in col_type:
        if 'count' in col_lower or 'num' in col_lower or 'total' in col_lower:
            desc_parts.append(f"Numeric count/total")
        elif 'price' in col_lower or 'cost' in col_lower or 'amount' in col_lower:
            desc_parts.append(f"Monetary value")
        elif profile['min_value'] and profile['max_value']:
            desc_parts.append(f"Numeric field ranging from {profile['min_value']} to {profile['max_value']}")
        else:
            desc_parts.append(f"Numeric field")

    # Default description with sample values
    else:
        if samples:
            sample_str = ', '.join(repr(s)[:30] for s in samples[:3])
            desc_parts.append(f"Values include: {sample_str}")
        else:
            desc_parts.append(f"{col_type} field")

    # Add null info if significant
    if null_pct > 10:
        desc_parts.append(f"({null_pct:.0f}% NULL)")

    return ". ".join(desc_parts)


def generate_field_description(client: Optional[anthropic.Anthropic],
                               table_name: str,
                               column_name: str,
                               profile: Dict[str, Any],
                               other_columns: List[str],
                               use_llm: bool = False) -> str:
    """Generate a meaningful field description, optionally using LLM."""

    # Use heuristic by default
    if not use_llm or client is None:
        return generate_field_description_heuristic(table_name, column_name, profile, other_columns)

    # Build profile summary for LLM
    profile_text = f"""
Table: {table_name}
Column: {column_name}
Type: {profile['column_type']}
Total rows: {profile['total_rows']}
NULL count: {profile['null_count']} ({100*profile['null_count']/max(1,profile['total_rows']):.1f}%)
Distinct values: {profile['distinct_count']}
"""

    if profile['min_value'] is not None:
        profile_text += f"Min value: {profile['min_value']}\n"
        profile_text += f"Max value: {profile['max_value']}\n"

    if profile['sample_values']:
        samples = profile['sample_values'][:5]
        profile_text += f"Sample values: {', '.join(repr(s) for s in samples)}\n"

    if profile['value_patterns']:
        profile_text += f"Patterns: {', '.join(profile['value_patterns'])}\n"

    profile_text += f"Other columns in table: {', '.join(other_columns[:10])}\n"

    prompt = f"""Based on this database field profile, generate a SHORT description (1-2 sentences max) of what this field likely represents. Focus on:
1. The semantic meaning of the field
2. The format of values (if relevant)
3. How it might be used in queries

{profile_text}

Return ONLY the description, no preamble. Be concise."""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  Warning: LLM call failed for {table_name}.{column_name}: {e}")
        return generate_field_description_heuristic(table_name, column_name, profile, other_columns)


def generate_enriched_malloy(db_id: str, db_profile: Dict[str, Any],
                             field_descriptions: Dict[str, Dict[str, str]],
                             original_malloy: str) -> str:
    """Generate enriched Malloy semantic layer with field descriptions."""

    # Parse the original malloy to find dimension definitions
    lines = original_malloy.split('\n')
    enriched_lines = []

    current_table = None
    in_dimension_block = False

    for i, line in enumerate(lines):
        # Detect which table we're in
        source_match = re.match(r'source:\s+(\w+)_base\s+is', line)
        if source_match:
            # Extract table name from source name (e.g., student_val_base -> Student)
            source_name = source_match.group(1)
            # Find matching table in profile
            for table_name in db_profile["tables"]:
                normalized = table_name.lower().replace('_', '').replace('-', '')
                source_normalized = source_name.lower().replace('_', '').replace('val', '')
                if normalized == source_normalized or table_name.lower() == source_name.lower():
                    current_table = table_name
                    break

        # Detect dimension block
        if 'dimension:' in line:
            in_dimension_block = True
        elif in_dimension_block and line.strip() and not line.strip().startswith('//'):
            # Check if this line defines a dimension
            dim_match = re.match(r'\s+(\w+)\s+is\s+(\w+)', line)
            if dim_match:
                dim_name = dim_match.group(1)
                original_col = dim_match.group(2)

                # Try to find description for this field
                desc = None
                if current_table and current_table in field_descriptions:
                    if original_col in field_descriptions[current_table]:
                        desc = field_descriptions[current_table][original_col]
                    elif dim_name in field_descriptions[current_table]:
                        desc = field_descriptions[current_table][dim_name]

                if desc:
                    # Add description as comment before the dimension
                    enriched_lines.append(f"    // {desc}")

        # Detect end of dimension block
        if in_dimension_block and (line.strip().startswith('primary_key:') or
                                    line.strip().startswith('measure:') or
                                    line.strip().startswith('join_')):
            in_dimension_block = False

        enriched_lines.append(line)

    return '\n'.join(enriched_lines)


def add_sample_values_comment(db_profile: Dict[str, Any],
                               field_descriptions: Dict[str, Dict[str, str]]) -> str:
    """Generate a header comment with sample values for each field."""
    comment_lines = [
        "// ============================================================",
        "// FIELD METADATA (Auto-generated from database profiling)",
        "// ============================================================",
        "//"
    ]

    for table_name, table_info in db_profile["tables"].items():
        comment_lines.append(f"// Table: {table_name}")
        for col_name, col_profile in table_info["columns"].items():
            desc = field_descriptions.get(table_name, {}).get(col_name, "")
            samples = col_profile.get("sample_values", [])[:3]

            if desc:
                comment_lines.append(f"//   {col_name}: {desc}")
            if samples:
                sample_str = ', '.join(repr(s)[:30] for s in samples)
                comment_lines.append(f"//     Sample values: {sample_str}")
        comment_lines.append("//")

    return '\n'.join(comment_lines)


def process_database(db_id: str, client: Optional[anthropic.Anthropic] = None, use_llm: bool = False) -> bool:
    """Process a single database to create enriched semantic layer."""

    # Find database path
    db_dir = os.path.join(SPIDER_DB_PATH, db_id)
    db_path = os.path.join(db_dir, f"{db_id}.sqlite")

    if not os.path.exists(db_path):
        print(f"  Database not found: {db_path}")
        return False

    # Check if original malloy exists
    original_malloy_path = os.path.join(FULL_LAYERS_DIR, f"{db_id}.malloy")
    if not os.path.exists(original_malloy_path):
        print(f"  Original Malloy not found: {original_malloy_path}")
        return False

    print(f"  Profiling database...")
    db_profile = profile_database(db_path)

    print(f"  Generating field descriptions...")
    field_descriptions = {}

    for table_name, table_info in db_profile["tables"].items():
        field_descriptions[table_name] = {}
        other_columns = list(table_info["columns"].keys())

        for col_name, col_profile in table_info["columns"].items():
            other_cols = [c for c in other_columns if c != col_name]
            desc = generate_field_description(client, table_name, col_name, col_profile, other_cols, use_llm=use_llm)
            field_descriptions[table_name][col_name] = desc
            print(f"    {table_name}.{col_name}: {desc[:60]}...")

    # Read original malloy
    with open(original_malloy_path, 'r') as f:
        original_malloy = f.read()

    # Generate header with sample values
    header_comment = add_sample_values_comment(db_profile, field_descriptions)

    # Generate enriched malloy
    enriched_malloy = generate_enriched_malloy(db_id, db_profile, field_descriptions, original_malloy)

    # Combine header and enriched content
    # Replace the first comment block with our enriched header
    final_malloy = header_comment + "\n\n" + enriched_malloy

    # Write output
    output_path = os.path.join(OUTPUT_DIR, f"{db_id}.malloy")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(final_malloy)

    print(f"  Written: {output_path}")
    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate enriched Malloy semantic layers")
    parser.add_argument("--db-ids", nargs="+", help="Specific database IDs to process")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of databases")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM for descriptions (requires API key)")
    args = parser.parse_args()

    # Initialize Anthropic client only if using LLM
    client = None
    if args.use_llm:
        client = anthropic.Anthropic()
        print("Using LLM for field descriptions")
    else:
        print("Using heuristic-based field descriptions")

    # Get list of databases to process
    if args.db_ids:
        db_ids = args.db_ids
    else:
        # Get all databases that have malloy files
        db_ids = [f.replace('.malloy', '') for f in os.listdir(FULL_LAYERS_DIR)
                  if f.endswith('.malloy')]

    if args.limit:
        db_ids = db_ids[:args.limit]

    print(f"Processing {len(db_ids)} databases...")

    success_count = 0
    for db_id in db_ids:
        print(f"\nProcessing: {db_id}")
        try:
            if process_database(db_id, client, use_llm=args.use_llm):
                success_count += 1
        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nDone! Successfully processed {success_count}/{len(db_ids)} databases")


if __name__ == "__main__":
    main()
