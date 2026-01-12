#!/usr/bin/env python3
"""
Anthropic Message Batches API client for NL2Malloy evaluation.

Submits evaluation questions as a batch job to Claude for 50% cost savings.
Handles job submission, status polling, and result retrieval.
"""

import argparse
import json
import os
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path, override=True)

# Import prompt building from evaluation script
from run_evaluation import (
    load_questions,
    load_malloy_layer,
    build_malloy_prompt,
    MALLOY_DIR
)
from shared_utils import extract_malloy_code, BatchJobManager, results_match

# Directories
EVALUATION_DIR = Path('/workspace/project/evaluation')
BATCH_DIR = EVALUATION_DIR / 'batch_jobs'
BATCH_DIR.mkdir(parents=True, exist_ok=True)

# Batch job manager for consistent metadata handling
batch_manager = BatchJobManager(BATCH_DIR, 'anthropic')

# Anthropic API base URL
API_BASE = "https://api.anthropic.com/v1"

# Model aliases
MODEL_ALIASES = {
    "opus": "claude-opus-4-5-20251101",
    "opus-4.5": "claude-opus-4-5-20251101",
    "sonnet": "claude-sonnet-4-5-20250929",
    "sonnet-4.5": "claude-sonnet-4-5-20250929",
    "sonnet-4": "claude-sonnet-4-20250514",
    "haiku": "claude-3-5-haiku-20241022",
    "haiku-4.5": "claude-haiku-4-5-20251001",
}


def get_api_key():
    """Get Anthropic API key from environment."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    return api_key


def get_headers():
    """Get headers for Anthropic API requests."""
    return {
        "Content-Type": "application/json",
        "X-Api-Key": get_api_key(),
        "anthropic-version": "2023-06-01"
    }


def resolve_model(model: str) -> str:
    """Resolve model alias to full model ID."""
    return MODEL_ALIASES.get(model, model)


def prepare_batch_requests(
    questions: List[Dict],
    model: str = "claude-sonnet-4-5-20250929",
    prompt_mode: str = "standard"
) -> Tuple[List[Dict], Dict[str, Dict]]:
    """
    Prepare batch requests from evaluation questions.

    Returns:
        - List of request objects for Anthropic batch API
        - Mapping of custom_ids to question metadata
    """
    batch_requests = []
    id_to_question = {}

    model = resolve_model(model)

    for q in questions:
        db_id = q['db_id']
        question_text = q['question']
        question_id = q.get('question_id', q.get('id', 0))

        # Load semantic layer
        malloy_layer = load_malloy_layer(db_id)
        if not malloy_layer:
            print(f"Warning: No semantic layer for {db_id}, skipping Q{question_id}")
            continue

        # Build prompt
        prompt = build_malloy_prompt(malloy_layer, question_text, mode=prompt_mode)

        # Create custom ID
        custom_id = f"q{question_id}_{db_id}"

        # Build batch request
        request = {
            "custom_id": custom_id,
            "params": {
                "model": model,
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        }

        batch_requests.append(request)
        id_to_question[custom_id] = {
            'question_id': question_id,
            'db_id': db_id,
            'question': question_text,
            'gold_sql': q.get('gold_sql', q.get('query', ''))
        }

    return batch_requests, id_to_question


def submit_batch_job(requests: List[Dict]) -> Dict:
    """
    Submit a batch job to Anthropic.

    Returns:
        Batch job response dict
    """
    print(f"Submitting batch job with {len(requests)} requests...")

    response = requests_lib.post(
        f"{API_BASE}/messages/batches",
        headers=get_headers(),
        json={"requests": requests}
    )

    if response.status_code != 200:
        raise Exception(f"Batch submission failed: {response.status_code} - {response.text}")

    batch = response.json()
    print(f"Batch job created: {batch['id']}")
    print(f"Status: {batch['processing_status']}")
    print(f"Expires at: {batch['expires_at']}")

    return batch


def check_batch_status(batch_id: str) -> Dict:
    """
    Check the status of a batch job.

    Returns:
        Batch job status dict
    """
    response = requests_lib.get(
        f"{API_BASE}/messages/batches/{batch_id}",
        headers=get_headers()
    )

    if response.status_code != 200:
        raise Exception(f"Status check failed: {response.status_code} - {response.text}")

    return response.json()


def wait_for_completion(
    batch_id: str,
    poll_interval: int = 30,
    max_wait_hours: float = 24
) -> Dict:
    """
    Poll batch job until completion.

    Returns:
        Final batch status
    """
    max_wait_seconds = max_wait_hours * 3600
    start_time = time.time()

    print(f"Waiting for batch job {batch_id}...")

    while True:
        batch = check_batch_status(batch_id)
        status = batch['processing_status']
        counts = batch.get('request_counts', {})

        elapsed = time.time() - start_time
        print(f"  [{elapsed/60:.1f}m] Status: {status} | "
              f"Processing: {counts.get('processing', 0)} | "
              f"Succeeded: {counts.get('succeeded', 0)} | "
              f"Errored: {counts.get('errored', 0)}")

        if status == 'ended':
            return batch

        if elapsed > max_wait_seconds:
            print(f"Timeout after {max_wait_hours} hours")
            batch['timed_out'] = True
            return batch

        time.sleep(poll_interval)


def download_results(results_url: str) -> List[Dict]:
    """
    Download results from the results URL.

    Returns:
        List of result dicts
    """
    response = requests_lib.get(
        results_url,
        headers=get_headers()
    )

    if response.status_code != 200:
        raise Exception(f"Results download failed: {response.status_code}")

    # Parse JSONL
    results = []
    for line in response.text.strip().split('\n'):
        if line:
            results.append(json.loads(line))

    return results


def extract_results(raw_results: List[Dict], id_to_question: Dict) -> List[Dict]:
    """
    Extract and format results with question metadata.

    Returns:
        List of result dicts with question info and model responses
    """
    results = []

    for item in raw_results:
        custom_id = item.get('custom_id')
        if custom_id not in id_to_question:
            continue

        question_meta = id_to_question[custom_id]

        # Extract response
        result_data = item.get('result', {})
        result_type = result_data.get('type')

        response_text = ""
        error = None

        if result_type == 'succeeded':
            message = result_data.get('message', {})
            content = message.get('content', [])
            if content and len(content) > 0:
                response_text = content[0].get('text', '')
        elif result_type == 'errored':
            error = result_data.get('error', {})

        # Extract Malloy query
        malloy_query = extract_malloy_code(response_text)

        results.append({
            'question_id': question_meta['question_id'],
            'db_id': question_meta['db_id'],
            'question': question_meta['question'],
            'gold_sql': question_meta['gold_sql'],
            'raw_response': response_text,
            'malloy_query': malloy_query,
            'custom_id': custom_id,
            'error': error
        })

    return results


# Alias requests module to avoid naming conflict
requests_lib = requests


def cmd_submit(args):
    """Submit a new batch job."""
    # Load questions
    sample_file = Path(args.questions)
    questions = load_questions(sample_file)
    print(f"Loaded {len(questions)} questions from {sample_file}")

    # Use expert layer if available
    expert_dir = Path('/workspace/project/malloy/expert')
    if expert_dir.exists():
        import run_evaluation
        run_evaluation.MALLOY_DIR = expert_dir
        print(f"Using expert semantic layers from {expert_dir}")

    model = resolve_model(args.model)
    print(f"Model: {model}")

    # Prepare requests
    batch_requests, id_to_question = prepare_batch_requests(
        questions,
        model=model,
        prompt_mode=args.prompt_mode
    )
    print(f"Prepared {len(batch_requests)} batch requests")

    # Submit batch job
    batch = submit_batch_job(batch_requests)
    batch_id = batch['id']

    # Save job info
    batch_manager.save_job_info(batch_id, id_to_question, model)

    print(f"\nBatch job submitted: {batch_id}")
    print(f"Use 'python anthropic_batch.py status {batch_id}' to check status")
    print(f"Use 'python anthropic_batch.py wait {batch_id}' to wait for completion")


def cmd_status(args):
    """Check status of a batch job."""
    batch = check_batch_status(args.batch_id)

    print(f"Batch ID: {batch['id']}")
    print(f"Status: {batch['processing_status']}")
    print(f"Created: {batch['created_at']}")
    print(f"Expires: {batch['expires_at']}")

    counts = batch.get('request_counts', {})
    print(f"\nRequest counts:")
    print(f"  Processing: {counts.get('processing', 0)}")
    print(f"  Succeeded: {counts.get('succeeded', 0)}")
    print(f"  Errored: {counts.get('errored', 0)}")
    print(f"  Canceled: {counts.get('canceled', 0)}")
    print(f"  Expired: {counts.get('expired', 0)}")

    if batch.get('results_url'):
        print(f"\nResults URL: {batch['results_url']}")


def cmd_wait(args):
    """Wait for a batch job to complete."""
    batch = wait_for_completion(
        args.batch_id,
        poll_interval=args.poll_interval
    )

    print(f"\nFinal status: {batch['processing_status']}")

    counts = batch.get('request_counts', {})
    print(f"Succeeded: {counts.get('succeeded', 0)}")
    print(f"Errored: {counts.get('errored', 0)}")

    if batch.get('results_url'):
        # Load saved question mapping
        job_info = batch_manager.load_job_info(args.batch_id)
        if job_info:
            print("\nDownloading results...")
            raw_results = download_results(batch['results_url'])
            results = extract_results(raw_results, job_info['questions'])
            batch_manager.save_results(results, args.batch_id, job_info['model'])
            print(f"Extracted {len(results)} results")
        else:
            print("Warning: Could not find saved job info for result extraction")


def cmd_results(args):
    """Retrieve results from a completed batch job."""
    batch = check_batch_status(args.batch_id)

    if batch['processing_status'] != 'ended':
        print(f"Job not yet complete. Status: {batch['processing_status']}")
        return

    if not batch.get('results_url'):
        print("No results URL available")
        return

    # Load saved question mapping
    job_info = batch_manager.load_job_info(args.batch_id)
    if not job_info:
        print("Error: Could not find saved job info")
        return

    print("Downloading results...")
    raw_results = download_results(batch['results_url'])
    results = extract_results(raw_results, job_info['questions'])
    results_file = batch_manager.save_results(results, args.batch_id, job_info['model'])

    print(f"Extracted {len(results)} results to {results_file}")


def cmd_list(args):
    """List all batch jobs."""
    response = requests_lib.get(
        f"{API_BASE}/messages/batches",
        headers=get_headers()
    )

    if response.status_code != 200:
        print(f"Error listing jobs: {response.status_code}")
        return

    data = response.json()
    batches = data.get('data', [])

    print("Anthropic Batch Jobs:")
    print("-" * 60)

    for batch in batches:
        batch_id = batch['id']
        status = batch['processing_status']
        created = batch.get('created_at', 'N/A')
        counts = batch.get('request_counts', {})

        print(f"  {batch_id}")
        print(f"    Status: {status}")
        print(f"    Created: {created}")
        print(f"    Succeeded: {counts.get('succeeded', 0)} / "
              f"Processing: {counts.get('processing', 0)} / "
              f"Errored: {counts.get('errored', 0)}")
        print()


def cmd_evaluate(args):
    """Evaluate results from a completed batch job."""
    import asyncio
    import run_evaluation
    from run_evaluation import (
        compile_malloy_query,
        execute_sql_duckdb,
        execute_gold_sql,
        results_match,
        get_gold_sql,
        SPIDER_DIR
    )

    # Use expert semantic layers for compilation
    expert_dir = Path('/workspace/project/malloy/expert')
    if expert_dir.exists():
        run_evaluation.MALLOY_DIR = expert_dir

    # Load results file
    results_file = Path(args.results_file)
    if not results_file.exists():
        results_file = BATCH_DIR / args.results_file
        if not results_file.exists():
            print(f"Results file not found: {args.results_file}")
            return

    with open(results_file) as f:
        data = json.load(f)

    results = data['results']
    model = data.get('model', 'unknown')

    # Load question metadata for alt_gold_sql
    sample_file = Path('/workspace/project/evaluation/enriched_test_sample.json')
    question_meta = {}
    if sample_file.exists():
        with open(sample_file) as f:
            sample_data = json.load(f)
        for q in sample_data['questions']:
            question_meta[q.get('id', q.get('question_id'))] = q

    print(f"Evaluating {len(results)} results from {model}")
    print("=" * 60)

    # Track results
    total = 0
    compiled = 0
    correct = 0
    errors = []
    skipped = 0

    async def evaluate_one(r):
        nonlocal total, compiled, correct, skipped

        qid = r['question_id']
        db_id = r['db_id']
        malloy_query = r['malloy_query']
        gold_sql = r['gold_sql']
        question = r['question']

        # Check if question should be skipped
        q_meta = question_meta.get(qid, {})
        if q_meta.get('skip'):
            skipped += 1
            print(f"  Q{qid} ({db_id}): SKIPPED - {q_meta.get('skip_reason', 'flagged')}")
            return

        total += 1

        # Skip if there was an API error
        if r.get('error'):
            errors.append({
                'question_id': qid,
                'db_id': db_id,
                'question': question,
                'error_type': 'api_error',
                'error': str(r['error'])
            })
            return

        # Get corrected gold SQL if available
        gold_sql = get_gold_sql(qid, gold_sql)

        # Compile Malloy to SQL
        compiled_sql, compile_error = await compile_malloy_query(db_id, malloy_query)

        if compile_error:
            errors.append({
                'question_id': qid,
                'db_id': db_id,
                'question': question,
                'error_type': 'compile',
                'error': compile_error,
                'malloy_query': malloy_query
            })
            return

        compiled += 1

        # Execute generated SQL
        gen_results, gen_error = execute_sql_duckdb(compiled_sql)
        if gen_error:
            errors.append({
                'question_id': qid,
                'db_id': db_id,
                'question': question,
                'error_type': 'execution',
                'error': gen_error
            })
            return

        # Execute gold SQL using SQLite directly
        db_path = SPIDER_DIR / 'database' / db_id / f"{db_id}.sqlite"
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(gold_sql)
            gold_results = cursor.fetchall()
            conn.close()
        except Exception as gold_error:
            errors.append({
                'question_id': qid,
                'db_id': db_id,
                'question': question,
                'error_type': 'gold_execution',
                'error': str(gold_error)
            })
            return

        # Compare results
        if results_match(gen_results, gold_results):
            correct += 1
            print(f"  Q{qid} ({db_id}): CORRECT")
        else:
            # Check alternative gold SQLs if available
            alt_match = False
            q_meta = question_meta.get(qid, {})
            alt_gold_sqls = q_meta.get('alt_gold_sql', [])

            for alt_sql in alt_gold_sqls:
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute(alt_sql)
                    alt_results = cursor.fetchall()
                    conn.close()
                    if results_match(gen_results, alt_results):
                        alt_match = True
                        break
                except:
                    continue

            if alt_match:
                correct += 1
                print(f"  Q{qid} ({db_id}): CORRECT (alt)")
            else:
                print(f"  Q{qid} ({db_id}): WRONG")
                print(f"    Expected {len(gold_results)} rows, got {len(gen_results)} rows")
                errors.append({
                    'question_id': qid,
                    'db_id': db_id,
                    'question': question,
                    'error_type': 'logic',
                    'expected_rows': len(gold_results),
                    'actual_rows': len(gen_results)
                })

    # Run evaluations
    for r in results:
        asyncio.run(evaluate_one(r))

    # Print summary
    print("\n" + "=" * 60)
    print(f"RESULTS for {model}")
    print("=" * 60)
    if skipped:
        print(f"Skipped: {skipped} (problematic gold SQL)")
    print(f"Total questions: {total}")
    print(f"Compiled successfully: {compiled} ({compiled/total*100:.1f}%)")
    print(f"Execution correct: {correct} ({correct/total*100:.1f}%)")
    print()

    # Error breakdown
    error_types = {}
    for e in errors:
        et = e['error_type']
        error_types[et] = error_types.get(et, 0) + 1

    print("Error breakdown:")
    for et, count in sorted(error_types.items()):
        print(f"  {et}: {count}")

    # Save evaluation results
    eval_output = {
        'model': model,
        'evaluated_at': datetime.now().isoformat(),
        'total': total,
        'compiled': compiled,
        'correct': correct,
        'accuracy': correct / total if total > 0 else 0,
        'errors': errors
    }

    eval_file = BATCH_DIR / f"eval_{results_file.stem}.json"
    with open(eval_file, 'w') as f:
        json.dump(eval_output, f, indent=2)

    print(f"\nEvaluation saved to: {eval_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Anthropic Message Batches API client for NL2Malloy evaluation"
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Submit command
    submit_parser = subparsers.add_parser('submit', help='Submit a new batch job')
    submit_parser.add_argument(
        '--questions', '-q',
        default='/workspace/project/evaluation/enriched_test_sample.json',
        help='Path to questions JSON file'
    )
    submit_parser.add_argument(
        '--model', '-m',
        default='sonnet',
        help='Model to use (opus, sonnet, haiku, or full model ID)'
    )
    submit_parser.add_argument(
        '--prompt-mode', '-p',
        choices=['standard', 'enhanced', 'cot'],
        default='standard',
        help='Prompt mode (default: standard)'
    )
    submit_parser.set_defaults(func=cmd_submit)

    # Status command
    status_parser = subparsers.add_parser('status', help='Check batch job status')
    status_parser.add_argument('batch_id', help='Batch job ID')
    status_parser.set_defaults(func=cmd_status)

    # Wait command
    wait_parser = subparsers.add_parser('wait', help='Wait for batch job completion')
    wait_parser.add_argument('batch_id', help='Batch job ID')
    wait_parser.add_argument(
        '--poll-interval', '-i',
        type=int,
        default=30,
        help='Poll interval in seconds (default: 30)'
    )
    wait_parser.set_defaults(func=cmd_wait)

    # Results command
    results_parser = subparsers.add_parser('results', help='Retrieve batch results')
    results_parser.add_argument('batch_id', help='Batch job ID')
    results_parser.set_defaults(func=cmd_results)

    # List command
    list_parser = subparsers.add_parser('list', help='List all batch jobs')
    list_parser.set_defaults(func=cmd_list)

    # Evaluate command
    eval_parser = subparsers.add_parser('evaluate', help='Evaluate batch results')
    eval_parser.add_argument('results_file', help='Path to results JSON file')
    eval_parser.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == '__main__':
    main()
