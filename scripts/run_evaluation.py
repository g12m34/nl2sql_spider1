#!/usr/bin/env python3
"""
Main evaluation harness for NL2SQL with multiple LLM providers.

Runs evaluation on sampled hard+extra questions from Spider.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from evaluation import eval_exec_match, EvalResult
from llm_providers import get_provider, list_providers, LLMProvider, LLMResponse

SPIDER_DIR = Path('/workspace/spider_db/spider')
EVALUATION_DIR = Path('/workspace/project/evaluation')
RESULTS_DIR = EVALUATION_DIR / 'results'


def load_questions(sample_file: Path) -> List[Dict]:
    """Load sampled questions from JSON file."""
    with open(sample_file) as f:
        data = json.load(f)
    return data['questions']


def load_schemas() -> Dict[str, Dict]:
    """Load all database schemas from tables.json."""
    with open(SPIDER_DIR / 'tables.json') as f:
        tables = json.load(f)

    schemas = {}
    for db in tables:
        db_id = db['db_id']
        schemas[db_id] = db
    return schemas


def format_schema(db_schema: Dict) -> str:
    """Format a database schema as a string for the LLM prompt."""
    lines = []
    db_id = db_schema['db_id']
    lines.append(f"Database: {db_id}")
    lines.append("")

    # Group columns by table
    table_names = db_schema['table_names_original']
    columns = db_schema['column_names_original']
    column_types = db_schema['column_types']

    # Build table -> columns mapping
    tables = {i: {'name': name, 'columns': []} for i, name in enumerate(table_names)}

    for col_idx, (table_idx, col_name) in enumerate(columns):
        if table_idx >= 0:  # Skip the * column
            col_type = column_types[col_idx] if col_idx < len(column_types) else 'text'
            tables[table_idx]['columns'].append((col_name, col_type))

    # Format each table
    for table_idx in sorted(tables.keys()):
        table = tables[table_idx]
        lines.append(f"Table: {table['name']}")
        for col_name, col_type in table['columns']:
            lines.append(f"  - {col_name} ({col_type})")
        lines.append("")

    # Add primary keys
    if db_schema.get('primary_keys'):
        lines.append("Primary Keys:")
        for pk_idx in db_schema['primary_keys']:
            if pk_idx < len(columns):
                table_idx, col_name = columns[pk_idx]
                if table_idx >= 0:
                    table_name = table_names[table_idx]
                    lines.append(f"  - {table_name}.{col_name}")
        lines.append("")

    # Add foreign keys
    if db_schema.get('foreign_keys'):
        lines.append("Foreign Keys:")
        for fk in db_schema['foreign_keys']:
            if len(fk) == 2:
                col1_idx, col2_idx = fk
                if col1_idx < len(columns) and col2_idx < len(columns):
                    t1_idx, c1_name = columns[col1_idx]
                    t2_idx, c2_name = columns[col2_idx]
                    if t1_idx >= 0 and t2_idx >= 0:
                        t1_name = table_names[t1_idx]
                        t2_name = table_names[t2_idx]
                        lines.append(f"  - {t1_name}.{c1_name} -> {t2_name}.{c2_name}")

    return "\n".join(lines)


def run_evaluation(
    provider: LLMProvider,
    questions: List[Dict],
    schemas: Dict[str, Dict],
    output_file: Path,
    resume: bool = False,
    limit: Optional[int] = None,
    verbose: bool = False
) -> Dict:
    """
    Run evaluation for a single provider.

    Args:
        provider: LLM provider to use
        questions: List of questions to evaluate
        schemas: Database schemas
        output_file: Where to save results
        resume: If True, skip already-evaluated questions
        limit: Max questions to evaluate (for testing)
        verbose: Print progress

    Returns:
        Summary metrics
    """
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

        # Get schema for this database
        db_id = q['db_id']
        if db_id not in schemas:
            print(f"Warning: Schema not found for {db_id}, skipping")
            continue

        schema_str = format_schema(schemas[db_id])

        # Generate SQL
        if verbose:
            print(f"[{i+1}/{len(questions_to_run)}] {db_id}: {q['question'][:50]}...")

        llm_response = provider.generate_sql(schema_str, q['question'])

        if llm_response.error:
            result = {
                'question_id': q_id,
                'db_id': db_id,
                'question': q['question'],
                'gold_sql': q['gold_sql'],
                'predicted_sql': '',
                'match': False,
                'error': f"LLM error: {llm_response.error}",
                'latency_ms': llm_response.latency_ms,
                'raw_response': llm_response.raw_response
            }
            errors += 1
        else:
            # Evaluate the generated SQL
            eval_result = eval_exec_match(
                db_path=q['db_path'],
                predicted_sql=llm_response.sql,
                gold_sql=q['gold_sql']
            )

            result = {
                'question_id': q_id,
                'db_id': db_id,
                'question': q['question'],
                'gold_sql': q['gold_sql'],
                'predicted_sql': llm_response.sql,
                'match': eval_result.match,
                'error': eval_result.error,
                'latency_ms': llm_response.latency_ms,
                'raw_response': llm_response.raw_response
            }

            if eval_result.match:
                correct += 1
            if eval_result.error:
                errors += 1

        results.append(result)
        total += 1

        # Save incrementally
        save_results(output_file, provider.name, results, correct, total, errors)

        if verbose:
            status = "PASS" if result['match'] else "FAIL"
            print(f"  -> {status} ({llm_response.latency_ms:.0f}ms)")
            if result.get('error'):
                print(f"     Error: {result['error'][:100]}")

    return {
        'provider': provider.name,
        'correct': correct,
        'total': total,
        'errors': errors,
        'accuracy': correct / total if total > 0 else 0.0
    }


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
            'accuracy': correct / total if total > 0 else 0.0
        },
        'results': results
    }

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)


def print_summary(summaries: List[Dict]):
    """Print summary table of results."""
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"{'Provider':<25} {'Accuracy':>10} {'Correct':>10} {'Errors':>10}")
    print("-" * 60)

    for s in sorted(summaries, key=lambda x: x['accuracy'], reverse=True):
        acc_str = f"{s['accuracy']:.1%}"
        print(f"{s['provider']:<25} {acc_str:>10} {s['correct']:>10} {s['errors']:>10}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Run NL2SQL evaluation')
    parser.add_argument('--providers', '-p', nargs='+',
                        help='Providers to evaluate (default: all available)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List available providers')
    parser.add_argument('--sample-file', '-s', type=Path,
                        default=EVALUATION_DIR / 'hard_extra_sample_200.json',
                        help='Path to sampled questions JSON')
    parser.add_argument('--resume', '-r', action='store_true',
                        help='Resume from previous run')
    parser.add_argument('--limit', '-n', type=int,
                        help='Limit number of questions (for testing)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Print detailed progress')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry run - check setup without calling APIs')

    args = parser.parse_args()

    if args.list:
        print("Available providers:")
        for name in list_providers():
            print(f"  - {name}")
        return

    # Load questions and schemas
    print(f"Loading questions from {args.sample_file}...")
    questions = load_questions(args.sample_file)
    print(f"Loaded {len(questions)} questions")

    print("Loading database schemas...")
    schemas = load_schemas()
    print(f"Loaded {len(schemas)} schemas")

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

        output_file = RESULTS_DIR / f"{provider_name.replace('/', '_')}.json"

        summary = run_evaluation(
            provider=provider,
            questions=questions,
            schemas=schemas,
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
