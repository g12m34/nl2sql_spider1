#!/usr/bin/env python3
"""
Validate Malloy semantic layers against Spider questions.

This script:
1. Loads Spider questions for each database
2. Tests that each Malloy layer compiles
3. Runs basic Malloy queries to verify functionality
4. Reports validation results
"""

import json
import subprocess
import os
from pathlib import Path
from collections import defaultdict
import tempfile

MALLOY_DIR = Path('/workspace/project/malloy/full')
SPIDER_DIR = Path('/workspace/spider_db/spider')


def load_spider_questions():
    """Load all Spider questions grouped by database."""
    db_questions = defaultdict(list)

    # Load dev questions
    with open(SPIDER_DIR / 'dev.json') as f:
        for q in json.load(f):
            db_questions[q['db_id']].append({
                'question': q['question'],
                'sql': q['query']
            })

    # Load train questions
    with open(SPIDER_DIR / 'train_spider.json') as f:
        for q in json.load(f):
            db_questions[q['db_id']].append({
                'question': q['question'],
                'sql': q['query']
            })

    return db_questions


def get_source_names_from_malloy(malloy_path):
    """Extract source names from a Malloy file."""
    sources = []
    with open(malloy_path) as f:
        for line in f:
            if line.strip().startswith('source:'):
                # Extract source name: "source: name is ..."
                parts = line.strip().split()
                if len(parts) >= 2:
                    sources.append(parts[1])
    return sources


def run_malloy_query(malloy_path, source_name, query_type='count'):
    """Run a Malloy query and return success/failure."""
    # Create a temporary query file
    if query_type == 'count':
        query = f"""
import "{malloy_path}"

run: {source_name} -> {{
  aggregate: row_count
}}
"""
    else:  # sample
        query = f"""
import "{malloy_path}"

run: {source_name} -> {{
  select: *
  limit: 5
}}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.malloy', delete=False) as f:
        f.write(query)
        query_path = f.name

    try:
        result = subprocess.run(
            ['malloy-cli', 'run', query_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        os.unlink(query_path)

        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        os.unlink(query_path)
        return False, "Query timed out"
    except Exception as e:
        if os.path.exists(query_path):
            os.unlink(query_path)
        return False, str(e)


def validate_database(db_id, questions, max_tests=10):
    """Validate a single database's semantic layer."""
    malloy_path = MALLOY_DIR / f"{db_id}.malloy"

    if not malloy_path.exists():
        return {
            'status': 'SKIP',
            'reason': 'Malloy file not found',
            'tests': []
        }

    # Get source names
    sources = get_source_names_from_malloy(malloy_path)
    if not sources:
        return {
            'status': 'FAIL',
            'reason': 'No sources found in Malloy file',
            'tests': []
        }

    # Test each source with a count query
    test_results = []
    all_passed = True

    for source in sources:
        success, output = run_malloy_query(str(malloy_path), source, 'count')
        test_results.append({
            'source': source,
            'query_type': 'count',
            'passed': success,
            'output': output[:200] if not success else 'OK'
        })
        if not success:
            all_passed = False

    return {
        'status': 'PASS' if all_passed else 'FAIL',
        'sources_tested': len(sources),
        'tests': test_results
    }


def main():
    print("Loading Spider questions...")
    db_questions = load_spider_questions()
    print(f"Found questions for {len(db_questions)} databases")

    # Get all Malloy files
    malloy_files = list(MALLOY_DIR.glob('*.malloy'))
    print(f"Found {len(malloy_files)} Malloy semantic layers")

    results = {
        'passed': [],
        'failed': [],
        'skipped': []
    }

    error_details = []

    for malloy_file in sorted(malloy_files):
        db_id = malloy_file.stem
        questions = db_questions.get(db_id, [])

        print(f"  Testing {db_id}...", end=' ')
        result = validate_database(db_id, questions)

        if result['status'] == 'PASS':
            results['passed'].append(db_id)
            print(f"PASS ({result['sources_tested']} sources)")
        elif result['status'] == 'SKIP':
            results['skipped'].append(db_id)
            print(f"SKIP - {result['reason']}")
        else:
            results['failed'].append(db_id)
            print(f"FAIL")
            # Collect error details
            for test in result['tests']:
                if not test['passed']:
                    error_details.append({
                        'db_id': db_id,
                        'source': test['source'],
                        'error': test['output']
                    })

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"Passed:  {len(results['passed'])}")
    print(f"Failed:  {len(results['failed'])}")
    print(f"Skipped: {len(results['skipped'])}")

    if results['failed']:
        print(f"\nFailed databases: {', '.join(results['failed'][:10])}")
        if len(results['failed']) > 10:
            print(f"  ... and {len(results['failed']) - 10} more")

    # Save detailed results
    output_path = Path('/workspace/project/malloy/validation_results.json')
    with open(output_path, 'w') as f:
        json.dump({
            'summary': {
                'passed': len(results['passed']),
                'failed': len(results['failed']),
                'skipped': len(results['skipped'])
            },
            'results': results,
            'errors': error_details[:50]  # First 50 errors
        }, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")

    return len(results['failed']) == 0


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
