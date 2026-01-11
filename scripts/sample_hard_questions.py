#!/usr/bin/env python3
"""
Sample hard and extra-hard questions from Spider train set for LLM evaluation.

Creates a balanced sample with equal hard and extra-hard questions.
Uses fixed random seed for reproducibility.
"""

import json
import random
from pathlib import Path
from collections import Counter
from datetime import datetime

# Fixed seed for reproducibility
RANDOM_SEED = 42
SAMPLE_SIZE = 200  # Total questions (100 hard + 100 extra)

SPIDER_DIR = Path('/workspace/spider_db/spider')
OUTPUT_DIR = Path('/workspace/project/evaluation')


def get_difficulty(sql_struct):
    """
    Compute Spider difficulty based on SQL components.

    Categories:
    - easy: single table, no complex operations
    - medium: joins OR GROUP BY/ORDER BY
    - hard: multiple joins with GROUP BY, or subqueries
    - extra: set operations (UNION, INTERSECT, EXCEPT)
    """
    has_union = sql_struct.get('union') is not None
    has_intersect = sql_struct.get('intersect') is not None
    has_except = sql_struct.get('except') is not None

    # Set operations = extra hard
    if has_union or has_intersect or has_except:
        return 'extra'

    # Check for nested queries in FROM clause
    from_clause = sql_struct.get('from', {})
    has_subquery = False
    if isinstance(from_clause, dict):
        table_units = from_clause.get('table_units', [])
        for unit in table_units:
            if isinstance(unit, list) and len(unit) > 0 and unit[0] == 'sql':
                has_subquery = True
                break

    # Check WHERE for nested queries
    where_clause = sql_struct.get('where', [])
    def check_nested(clause):
        if isinstance(clause, dict):
            return True  # nested SQL
        if isinstance(clause, list):
            for item in clause:
                if check_nested(item):
                    return True
        return False

    if check_nested(where_clause):
        has_subquery = True

    if has_subquery:
        return 'hard'

    # Check for GROUP BY, ORDER BY, HAVING
    has_groupby = bool(sql_struct.get('groupBy'))
    has_orderby = bool(sql_struct.get('orderBy'))
    has_having = bool(sql_struct.get('having'))

    # Count joins (multiple tables)
    num_tables = 0
    if isinstance(from_clause, dict):
        num_tables = len(from_clause.get('table_units', []))

    has_joins = num_tables > 1

    if has_groupby or has_having:
        return 'hard' if has_joins else 'medium'

    if has_joins or has_orderby:
        return 'medium'

    return 'easy'


def load_train_data():
    """Load all training data from Spider."""
    all_questions = []

    # Load train_spider
    with open(SPIDER_DIR / 'train_spider.json') as f:
        train_spider = json.load(f)
        for q in train_spider:
            q['source'] = 'train_spider'
        all_questions.extend(train_spider)

    # Load train_others
    with open(SPIDER_DIR / 'train_others.json') as f:
        train_others = json.load(f)
        for q in train_others:
            q['source'] = 'train_others'
        all_questions.extend(train_others)

    return all_questions


def get_db_path(db_id):
    """Get the path to the SQLite database file."""
    return SPIDER_DIR / 'database' / db_id / f'{db_id}.sqlite'


def main():
    print("=" * 60)
    print("SAMPLING HARD + EXTRA QUESTIONS FROM SPIDER TRAIN")
    print("=" * 60)
    print(f"Random seed: {RANDOM_SEED}")
    print(f"Target sample size: {SAMPLE_SIZE} (100 hard + 100 extra)")
    print()

    # Set random seed for reproducibility
    random.seed(RANDOM_SEED)

    # Load training data
    print("Loading training data...")
    all_questions = load_train_data()
    print(f"Loaded {len(all_questions)} total questions")

    # Categorize by difficulty
    by_difficulty = {'easy': [], 'medium': [], 'hard': [], 'extra': []}

    for q in all_questions:
        diff = get_difficulty(q['sql'])
        q['difficulty'] = diff
        by_difficulty[diff].append(q)

    print("\nDifficulty distribution in train:")
    for diff in ['easy', 'medium', 'hard', 'extra']:
        print(f"  {diff}: {len(by_difficulty[diff])}")

    # Verify we have enough questions
    n_hard = len(by_difficulty['hard'])
    n_extra = len(by_difficulty['extra'])

    print(f"\nAvailable: {n_hard} hard, {n_extra} extra")

    if n_hard < 100:
        raise ValueError(f"Not enough hard questions: {n_hard} < 100")
    if n_extra < 100:
        raise ValueError(f"Not enough extra questions: {n_extra} < 100")

    # Sample 100 of each
    print("\nSampling 100 hard and 100 extra questions...")

    sampled_hard = random.sample(by_difficulty['hard'], 100)
    sampled_extra = random.sample(by_difficulty['extra'], 100)

    # Combine and shuffle
    sampled = sampled_hard + sampled_extra
    random.shuffle(sampled)

    # Verify database files exist
    print("\nVerifying database files exist...")
    missing_dbs = set()
    for q in sampled:
        db_path = get_db_path(q['db_id'])
        if not db_path.exists():
            missing_dbs.add(q['db_id'])

    if missing_dbs:
        print(f"WARNING: Missing databases: {missing_dbs}")
    else:
        print("All database files found!")

    # Prepare output format
    output_questions = []
    for i, q in enumerate(sampled):
        output_questions.append({
            'id': i,
            'db_id': q['db_id'],
            'question': q['question'],
            'gold_sql': q['query'],
            'difficulty': q['difficulty'],
            'source': q['source'],
            'db_path': str(get_db_path(q['db_id']))
        })

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save sampled questions
    output_file = OUTPUT_DIR / 'hard_extra_sample_200.json'
    with open(output_file, 'w') as f:
        json.dump({
            'metadata': {
                'description': 'Sampled hard and extra-hard questions from Spider train set',
                'created': datetime.now().isoformat(),
                'random_seed': RANDOM_SEED,
                'total_questions': len(output_questions),
                'hard_count': 100,
                'extra_count': 100,
                'source_files': ['train_spider.json', 'train_others.json']
            },
            'questions': output_questions
        }, f, indent=2)

    print(f"\nSaved {len(output_questions)} questions to: {output_file}")

    # Print summary statistics
    print("\n" + "=" * 60)
    print("SAMPLE STATISTICS")
    print("=" * 60)

    # Count by difficulty
    diff_counts = Counter(q['difficulty'] for q in output_questions)
    print(f"By difficulty:")
    for diff, count in sorted(diff_counts.items()):
        print(f"  {diff}: {count}")

    # Count by source
    source_counts = Counter(q['source'] for q in output_questions)
    print(f"\nBy source:")
    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count}")

    # Count by database
    db_counts = Counter(q['db_id'] for q in output_questions)
    print(f"\nUnique databases: {len(db_counts)}")
    print(f"Most common databases:")
    for db, count in db_counts.most_common(5):
        print(f"  {db}: {count}")

    # Show a few sample questions
    print("\n" + "=" * 60)
    print("SAMPLE QUESTIONS")
    print("=" * 60)
    for q in output_questions[:3]:
        print(f"\n[{q['difficulty'].upper()}] {q['db_id']}")
        print(f"Q: {q['question']}")
        print(f"SQL: {q['gold_sql'][:100]}..." if len(q['gold_sql']) > 100 else f"SQL: {q['gold_sql']}")


if __name__ == '__main__':
    main()
