#!/usr/bin/env python3
"""
Main evaluation harness for NL2SQL with Malloy semantic layers.

Tests LLM ability to generate Malloy queries from natural language.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb
from malloy import Runtime
from malloy.data.duckdb import DuckDbConnection

from llm_providers import get_provider, list_providers, LLMProvider, LLMResponse
from shared_utils import results_match, normalize_value  # Consolidated from evaluation.py
import re

SPIDER_DIR = Path('/workspace/spider_db/spider')
MALLOY_DIR = Path('/workspace/project/malloy/full')

# Prompt mode: 'standard', 'cot' (chain-of-thought), 'enhanced', or 'reasoning'
PROMPT_MODE = 'standard'

# Reasoning traces for 'reasoning' mode
REASONING_TRACES = {}

EVALUATION_DIR = Path('/workspace/project/evaluation')
RESULTS_DIR = EVALUATION_DIR / 'results'
GOLD_SQL_BUGS_FILE = EVALUATION_DIR / 'gold_sql_bugs.json'

# Cache for gold SQL corrections
_gold_sql_corrections: Dict[int, str] = {}


def load_reasoning_traces(traces_file: Path = None) -> Dict[str, Dict]:
    """Load reasoning traces from JSON file."""
    global REASONING_TRACES
    if REASONING_TRACES:
        return REASONING_TRACES

    if traces_file is None:
        traces_file = EVALUATION_DIR / 'reasoning_traces_hard_extra.json'

    if traces_file.exists():
        with open(traces_file) as f:
            data = json.load(f)
        REASONING_TRACES = data.get('traces', {})
    return REASONING_TRACES


def get_reasoning_trace(question_id: int) -> Optional[Dict]:
    """Get reasoning trace for a question."""
    traces = load_reasoning_traces()
    return traces.get(str(question_id))


def format_reasoning_trace(trace: Dict) -> str:
    """Format a reasoning trace for inclusion in prompt."""
    if not trace:
        return ""

    reasoning = trace.get('reasoning', {})

    parts = []
    parts.append(f"Goal: {reasoning.get('goal', 'N/A')}")

    tables = reasoning.get('tables_needed', [])
    if tables:
        parts.append(f"Tables needed: {', '.join(tables)}")

    join_path = reasoning.get('join_path', '')
    if join_path:
        parts.append(f"Join path: {join_path}")

    filters = reasoning.get('filters', [])
    if filters:
        parts.append(f"Filters: {', '.join(str(f) for f in filters)}")

    agg = reasoning.get('aggregation', {})
    if isinstance(agg, dict):
        agg_parts = []
        if agg.get('group_by'):
            agg_parts.append(f"group by {agg['group_by']}")
        if agg.get('measure'):
            agg_parts.append(f"measure: {agg['measure']}")
        if agg.get('order'):
            agg_parts.append(f"order: {agg['order']}")
        if agg.get('limit'):
            agg_parts.append(f"limit: {agg['limit']}")
        if agg.get('having'):
            agg_parts.append(f"having: {agg['having']}")
        if agg.get('pattern'):
            agg_parts.append(f"pattern: {agg['pattern']}")
        if agg_parts:
            parts.append(f"Aggregation: {', '.join(agg_parts)}")

    approach = reasoning.get('malloy_approach', '')
    if approach:
        parts.append(f"Malloy approach: {approach}")

    return '\n'.join(parts)


def load_gold_sql_corrections() -> Dict[int, str]:
    """Load corrected gold SQL from bugs file."""
    global _gold_sql_corrections
    if _gold_sql_corrections:
        return _gold_sql_corrections

    if GOLD_SQL_BUGS_FILE.exists():
        with open(GOLD_SQL_BUGS_FILE) as f:
            data = json.load(f)
        for bug in data.get('bugs', []):
            qid = bug['question_id']
            corrected = bug.get('gold_sql_corrected')
            if corrected:
                _gold_sql_corrections[qid] = corrected
    return _gold_sql_corrections


def get_gold_sql(question_id: int, original_gold_sql: str) -> str:
    """Get gold SQL, using corrected version if available."""
    corrections = load_gold_sql_corrections()
    return corrections.get(question_id, original_gold_sql)


def extract_sources_from_layer(malloy_layer: str) -> List[str]:
    """Extract source names from a Malloy semantic layer."""
    # Match "source: name is" patterns
    pattern = r'source:\s+(\w+)\s+is'
    sources = re.findall(pattern, malloy_layer)
    # Filter out _base sources for cleaner listing
    full_sources = [s for s in sources if not s.endswith('_base')]
    return full_sources


def load_questions(sample_file: Path) -> List[Dict]:
    """Load sampled questions from JSON file."""
    with open(sample_file) as f:
        data = json.load(f)
    return data['questions']


def load_malloy_layer(db_id: str) -> Optional[str]:
    """Load the Malloy semantic layer for a database."""
    malloy_file = MALLOY_DIR / f"{db_id}.malloy"
    if malloy_file.exists():
        return malloy_file.read_text()
    return None


def build_malloy_prompt(malloy_layer: str, question: str, mode: str = None, question_id: int = None) -> str:
    """
    Build prompt for generating Malloy queries.

    Structure optimized for prompt caching:
    1. Static content (syntax guide, instructions) - cached across all calls
    2. Per-database content (semantic layer) - cached per database
    3. Per-question content (question) - at the end, never cached

    Modes:
    - 'standard': Original prompt
    - 'enhanced': Better schema linking guidance
    - 'cot': Chain-of-thought reasoning before query
    - 'reasoning': Includes pre-computed reasoning trace
    """
    mode = mode or PROMPT_MODE

    # Extract available sources for enhanced mode
    sources = extract_sources_from_layer(malloy_layer)
    sources_list = ', '.join(sources) if sources else 'See semantic layer below'

    base_syntax = """## Malloy Syntax Reference

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
- Use `count(distinct field)` - DEPRECATED, use `count(field)` instead"""

    if mode == 'cot':
        return f"""# Malloy Query Generation

{base_syntax}

## Available Sources: {sources_list}

## Semantic Layer

```malloy
{malloy_layer}
```

## Question

{question}

## Your Task

First, briefly answer these questions in your head (do NOT write them out):
1. Which source from [{sources_list}] matches this question?
2. What fields do I need?
3. Do I need a pipeline for aggregate filtering?

Then output ONLY the Malloy query. No explanation. Just the query starting with `run:`

Query:"""
    elif mode == 'enhanced':
        return f"""# Malloy Query Generation

{base_syntax}

## Available Sources: {sources_list}

## Semantic Layer

```malloy
{malloy_layer}
```

## Question

{question}

## Instructions

Output ONLY the Malloy query. No explanation. No markdown. Just the query starting with `run:`

Query:"""
    elif mode == 'reasoning':
        # Get reasoning trace for this question
        reasoning_text = ""
        if question_id:
            trace = get_reasoning_trace(question_id)
            if trace:
                reasoning_text = format_reasoning_trace(trace)

        if reasoning_text:
            return f"""# Malloy Query Generation

{base_syntax}

## Available Sources: {sources_list}

## Semantic Layer

```malloy
{malloy_layer}
```

## Question

{question}

## Solution Strategy

{reasoning_text}

## Instructions

Using the solution strategy above, generate the Malloy query. Use source names and field names exactly as defined in the semantic layer.
Output ONLY the Malloy query. No explanation. No markdown. Just the query starting with `run:`

Query:"""
        else:
            # Fall back to enhanced mode if no trace available
            return f"""# Malloy Query Generation

{base_syntax}

## Available Sources: {sources_list}

## Semantic Layer

```malloy
{malloy_layer}
```

## Question

{question}

## Instructions

Output ONLY the Malloy query. No explanation. No markdown. Just the query starting with `run:`

Query:"""
    else:  # standard
        return f"""# Malloy Query Generation

{base_syntax}

## Instructions

Generate a Malloy query. Use source names and field names exactly as defined in the semantic layer.
Return ONLY the query - no explanation, no markdown code blocks.

## Semantic Layer

```malloy
{malloy_layer}
```

## Question

{question}

## Query"""


async def compile_malloy_query(db_id: str, malloy_query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Compile a Malloy query to SQL.

    Returns:
        (sql, None) on success
        (None, error_message) on failure
    """
    try:
        conn = DuckDbConnection(name="duckdb")
        runtime = Runtime()
        runtime.add_connection(conn)

        malloy_file = MALLOY_DIR / f"{db_id}.malloy"
        runtime.load_file(str(malloy_file))

        # Compile the query
        result = await runtime.get_sql(query=malloy_query)
        if result and result[0]:
            return result[0], None
        else:
            return None, "Failed to compile Malloy query"
    except Exception as e:
        return None, str(e)


def execute_sql_duckdb(sql: str) -> Tuple[Optional[List[Tuple]], Optional[str]]:
    """Execute SQL via DuckDB and return results."""
    try:
        db = duckdb.connect()
        results = db.execute(sql).fetchall()
        db.close()
        return results, None
    except Exception as e:
        return None, str(e)


def execute_gold_sql(db_path: str, gold_sql: str) -> Tuple[Optional[List[Tuple]], Optional[str]]:
    """Execute gold SQL via DuckDB with sqlite_scan."""
    try:
        db = duckdb.connect()
        # We need to handle the gold SQL which is written for SQLite
        # Execute directly since the Malloy-generated SQL also uses sqlite_scan
        results = db.execute(gold_sql).fetchall()
        db.close()
        return results, None
    except Exception as e:
        # Try via sqlite_scan wrapper if direct execution fails
        return None, str(e)


# Note: normalize_value and results_match are now imported from shared_utils
# The shared_utils.results_match is more robust and handles column permutations


async def evaluate_question(
    provider: LLMProvider,
    question: Dict,
    verbose: bool = False
) -> Dict:
    """Evaluate a single question with Malloy."""

    db_id = question['db_id']
    q_text = question['question']
    gold_sql = question['gold_sql']
    db_path = question['db_path']

    # Load Malloy semantic layer
    malloy_layer = load_malloy_layer(db_id)
    if not malloy_layer:
        return {
            'question_id': question['id'],
            'db_id': db_id,
            'question': q_text,
            'gold_sql': gold_sql,
            'predicted_malloy': '',
            'predicted_sql': '',
            'match': False,
            'error': f'Malloy layer not found for {db_id}',
            'latency_ms': 0,
            'raw_response': ''
        }

    # Build prompt and call LLM
    q_id = question.get('id', question.get('question_id'))
    prompt = build_malloy_prompt(malloy_layer, q_text, question_id=q_id)
    llm_response = provider.generate_sql(prompt, "")  # question already in prompt

    if llm_response.error:
        return {
            'question_id': question['id'],
            'db_id': db_id,
            'question': q_text,
            'gold_sql': gold_sql,
            'predicted_malloy': '',
            'predicted_sql': '',
            'match': False,
            'error': f'LLM error: {llm_response.error}',
            'latency_ms': llm_response.latency_ms,
            'raw_response': llm_response.raw_response
        }

    malloy_query = llm_response.sql  # Actually Malloy code

    # Compile Malloy to SQL
    compiled_sql, compile_error = await compile_malloy_query(db_id, malloy_query)

    if compile_error:
        return {
            'question_id': question['id'],
            'db_id': db_id,
            'question': q_text,
            'gold_sql': gold_sql,
            'predicted_malloy': malloy_query,
            'predicted_sql': '',
            'match': False,
            'error': f'Malloy compile error: {compile_error}',
            'latency_ms': llm_response.latency_ms,
            'raw_response': llm_response.raw_response
        }

    # Execute compiled SQL
    pred_results, exec_error = execute_sql_duckdb(compiled_sql)

    if exec_error:
        return {
            'question_id': question['id'],
            'db_id': db_id,
            'question': q_text,
            'gold_sql': gold_sql,
            'predicted_malloy': malloy_query,
            'predicted_sql': compiled_sql,
            'match': False,
            'error': f'SQL execution error: {exec_error}',
            'latency_ms': llm_response.latency_ms,
            'raw_response': llm_response.raw_response
        }

    # Get corrected gold SQL if available (for known Spider bugs)
    effective_gold_sql = get_gold_sql(question['id'], gold_sql)
    gold_sql_was_corrected = (effective_gold_sql != gold_sql)

    # Execute gold SQL (need to wrap for DuckDB)
    # The gold SQL is for SQLite, so we need to use sqlite_scan
    try:
        db = duckdb.connect()
        # Try to execute gold SQL by wrapping table references
        # This is tricky - gold SQL uses SQLite syntax
        # For now, use direct SQLite execution
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(effective_gold_sql)
        gold_results = cursor.fetchall()
        conn.close()
    except Exception as e:
        return {
            'question_id': question['id'],
            'db_id': db_id,
            'question': q_text,
            'gold_sql': gold_sql,
            'gold_sql_corrected': effective_gold_sql if gold_sql_was_corrected else None,
            'predicted_malloy': malloy_query,
            'predicted_sql': compiled_sql,
            'match': False,
            'error': f'Gold SQL error: {str(e)}',
            'latency_ms': llm_response.latency_ms,
            'raw_response': llm_response.raw_response
        }

    # Compare results
    order_matters = 'order by' in effective_gold_sql.lower()
    match = results_match(gold_results, pred_results, order_matters)

    result = {
        'question_id': question['id'],
        'db_id': db_id,
        'question': q_text,
        'gold_sql': gold_sql,
        'predicted_malloy': malloy_query,
        'predicted_sql': compiled_sql,
        'match': match,
        'error': None,
        'latency_ms': llm_response.latency_ms,
        'raw_response': llm_response.raw_response,
        'pred_row_count': len(pred_results),
        'gold_row_count': len(gold_results)
    }
    if gold_sql_was_corrected:
        result['gold_sql_corrected'] = effective_gold_sql
    return result


async def run_evaluation_async(
    provider: LLMProvider,
    questions: List[Dict],
    output_file: Path,
    resume: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False
) -> Dict:
    """Run evaluation for a single provider."""

    # Load existing results if resuming
    existing_results = {}
    if resume and output_file.exists():
        with open(output_file) as f:
            data = json.load(f)
            for r in data.get('results', []):
                existing_results[r['question_id']] = r

    results = []
    correct = 0
    errors = 0
    total = 0

    questions_to_run = questions[:limit] if limit else questions

    for i, q in enumerate(questions_to_run):
        q_id = q['id']

        # Skip if already evaluated
        if q_id in existing_results:
            results.append(existing_results[q_id])
            if existing_results[q_id]['match']:
                correct += 1
            if existing_results[q_id].get('error'):
                errors += 1
            total += 1
            if verbose:
                print(f"[{i+1}/{len(questions_to_run)}] Skipped (cached): {q_id}")
            continue

        if verbose:
            print(f"[{i+1}/{len(questions_to_run)}] {q['db_id']}: {q['question'][:50]}...")

        result = await evaluate_question(provider, q, verbose)
        results.append(result)

        if result['match']:
            correct += 1
        if result.get('error'):
            errors += 1
        total += 1

        # Save incrementally
        save_results(output_file, provider.name, results, correct, total, errors)

        if verbose:
            status = "PASS" if result['match'] else "FAIL"
            print(f"  -> {status} ({result['latency_ms']:.0f}ms)")
            if result.get('error'):
                print(f"     Error: {result['error'][:80]}")

    return {
        'provider': provider.name,
        'correct': correct,
        'total': total,
        'errors': errors,
        'accuracy': correct / total if total > 0 else 0.0
    }


def run_evaluation(
    provider: LLMProvider,
    questions: List[Dict],
    output_file: Path,
    resume: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False
) -> Dict:
    """Synchronous wrapper for async evaluation."""
    return asyncio.run(run_evaluation_async(
        provider, questions, output_file, resume, limit, verbose
    ))


def save_results(output_file: Path, provider_name: str, results: List[Dict],
                 correct: int, total: int, errors: int):
    """Save results to JSON file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'metadata': {
            'provider': provider_name,
            'timestamp': datetime.now().isoformat(),
            'total': total,
            'correct': correct,
            'errors': errors,
            'accuracy': correct / total if total > 0 else 0.0,
            'evaluation_type': 'malloy'
        },
        'results': results
    }

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)


def print_summary(summaries: List[Dict]):
    """Print summary table of results."""
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY (Malloy)")
    print("=" * 60)
    print(f"{'Provider':<25} {'Accuracy':>10} {'Correct':>10} {'Errors':>10}")
    print("-" * 60)

    for s in sorted(summaries, key=lambda x: x['accuracy'], reverse=True):
        acc_str = f"{s['accuracy']:.1%}"
        print(f"{s['provider']:<25} {acc_str:>10} {s['correct']:>10} {s['errors']:>10}")

    print("=" * 60)


def main():
    global MALLOY_DIR, PROMPT_MODE  # Allow overriding the defaults
    parser = argparse.ArgumentParser(description='Run NL2Malloy evaluation')
    parser.add_argument('--providers', '-p', nargs='+',
                        help='Providers to evaluate (default: all available)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List available providers')
    parser.add_argument('--sample-file', '-s', type=Path,
                        default=EVALUATION_DIR / 'hard_extra_sample_200.json',
                        help='Path to sampled questions JSON')
    parser.add_argument('--malloy-dir', '-m', type=Path,
                        default=MALLOY_DIR,
                        help='Path to Malloy semantic layers directory')
    parser.add_argument('--prompt-mode', choices=['standard', 'enhanced', 'cot', 'reasoning'],
                        default='standard',
                        help='Prompt mode: standard, enhanced, cot (chain-of-thought), or reasoning (with pre-computed traces)')
    parser.add_argument('--resume', '-r', action='store_true',
                        help='Resume from previous run')
    parser.add_argument('--limit', '-n', type=int,
                        help='Limit number of questions (for testing)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print detailed progress')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry run - check setup without calling APIs')

    args = parser.parse_args()

    # Override globals if specified
    if args.malloy_dir != MALLOY_DIR:
        MALLOY_DIR = args.malloy_dir
        print(f"Using Malloy directory: {MALLOY_DIR}")

    PROMPT_MODE = args.prompt_mode
    if PROMPT_MODE != 'standard':
        print(f"Using prompt mode: {PROMPT_MODE}")

    if args.list:
        print("Available providers:")
        for name in list_providers():
            print(f"  - {name}")
        return

    # Load questions
    print(f"Loading questions from {args.sample_file}...")
    questions = load_questions(args.sample_file)
    print(f"Loaded {len(questions)} questions")

    # Verify Malloy layers exist
    print("Checking Malloy semantic layers...")
    missing = []
    for q in questions:
        if not load_malloy_layer(q['db_id']):
            missing.append(q['db_id'])
    if missing:
        print(f"Warning: Missing Malloy layers for {len(set(missing))} databases")
    else:
        print("All Malloy layers found!")

    if args.dry_run:
        print("\n[DRY RUN] Setup verified. Would evaluate:")
        providers_to_run = args.providers or list_providers()
        for p in providers_to_run:
            print(f"  - {p}")
        print(f"\nQuestions: {len(questions)}")
        print(f"Limit: {args.limit or 'none'}")
        return

    # Determine which providers to run
    providers_to_run = args.providers or list_providers()

    summaries = []
    for provider_name in providers_to_run:
        print(f"\n{'='*60}")
        print(f"Evaluating: {provider_name}")
        print(f"{'='*60}")

        try:
            provider = get_provider(provider_name)
        except ValueError as e:
            print(f"Error: {e}")
            continue
        except Exception as e:
            print(f"Error initializing {provider_name}: {e}")
            continue

        output_file = RESULTS_DIR / f"{provider_name.replace('/', '_')}_malloy.json"

        summary = run_evaluation(
            provider=provider,
            questions=questions,
            output_file=output_file,
            resume=args.resume,
            limit=args.limit,
            verbose=args.verbose
        )

        summaries.append(summary)
        print(f"\n{provider_name}: {summary['accuracy']:.1%} ({summary['correct']}/{summary['total']})")

    if summaries:
        print_summary(summaries)


if __name__ == '__main__':
    main()
