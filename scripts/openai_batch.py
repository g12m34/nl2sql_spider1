#!/usr/bin/env python3
"""
OpenAI Batch API client for NL2Malloy evaluation.

Submits evaluation questions as a batch job to OpenAI for 50% cost savings.
Handles job submission, status polling, and result retrieval.
"""

import argparse
import json
import os
import time
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
    MALLOY_DIR,
    load_reasoning_traces
)
from shared_utils import extract_malloy_code, BatchJobManager, results_match

# Directories
EVALUATION_DIR = Path('/workspace/project/evaluation')
BATCH_DIR = EVALUATION_DIR / 'batch_jobs'
BATCH_DIR.mkdir(parents=True, exist_ok=True)

# Batch job manager for consistent metadata handling
batch_manager = BatchJobManager(BATCH_DIR, 'openai')


def get_openai_client():
    """Initialize the OpenAI client."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")

    import openai
    client = openai.OpenAI(api_key=api_key)
    return client


def prepare_batch_requests(
    questions: List[Dict],
    model: str = "gpt-5.2",
    prompt_mode: str = "standard"
) -> Tuple[List[Dict], Dict[str, Dict]]:
    """
    Prepare batch requests from evaluation questions.

    Returns:
        - List of JSONL request objects for OpenAI batch API
        - Mapping of custom_ids to question metadata
    """
    requests = []
    id_to_question = {}

    # Pre-load reasoning traces if using reasoning mode
    if prompt_mode == 'reasoning':
        load_reasoning_traces()

    for q in questions:
        db_id = q['db_id']
        question_text = q['question']
        # Support both 'id' and 'question_id' field names
        question_id = q.get('question_id', q.get('id', 0))

        # Load semantic layer
        malloy_layer = load_malloy_layer(db_id)
        if not malloy_layer:
            print(f"Warning: No semantic layer for {db_id}, skipping Q{question_id}")
            continue

        # Build prompt (pass question_id for reasoning mode)
        prompt = build_malloy_prompt(malloy_layer, question_text, mode=prompt_mode, question_id=question_id)

        # Create custom_id for tracking
        custom_id = f"q{question_id}_{db_id}"

        # Build batch request in OpenAI format
        request = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": 1024
            }
        }

        requests.append(request)
        id_to_question[custom_id] = {
            'question_id': question_id,
            'db_id': db_id,
            'question': question_text,
            'gold_sql': q.get('gold_sql', q.get('query', ''))
        }

    return requests, id_to_question


def submit_batch_job(
    client,
    requests: List[Dict],
    display_name: str = None
) -> str:
    """
    Submit a batch job to OpenAI.

    Returns:
        Batch job ID
    """
    if display_name is None:
        display_name = f"nl2malloy-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"Submitting batch job with {len(requests)} requests...")
    print(f"Display name: {display_name}")

    # Write requests to JSONL file
    batch_input_file = BATCH_DIR / f"{display_name}_input.jsonl"
    with open(batch_input_file, 'w') as f:
        for req in requests:
            f.write(json.dumps(req) + '\n')

    print(f"Batch input file: {batch_input_file}")

    # Upload the file
    with open(batch_input_file, 'rb') as f:
        uploaded_file = client.files.create(file=f, purpose="batch")

    print(f"Uploaded file ID: {uploaded_file.id}")

    # Create the batch job
    batch_job = client.batches.create(
        input_file_id=uploaded_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": display_name}
    )

    print(f"Batch job created: {batch_job.id}")
    print(f"Status: {batch_job.status}")

    return batch_job.id


def check_batch_status(client, job_id: str) -> Dict:
    """
    Check the status of a batch job.

    Returns:
        Dict with job status information
    """
    batch_job = client.batches.retrieve(job_id)

    return {
        'id': batch_job.id,
        'status': batch_job.status,
        'created_at': batch_job.created_at,
        'completed_at': batch_job.completed_at,
        'failed_at': batch_job.failed_at,
        'request_counts': {
            'total': batch_job.request_counts.total,
            'completed': batch_job.request_counts.completed,
            'failed': batch_job.request_counts.failed
        } if batch_job.request_counts else None,
        'output_file_id': batch_job.output_file_id,
        'error_file_id': batch_job.error_file_id
    }


def wait_for_completion(
    client,
    job_id: str,
    poll_interval: int = 30,
    max_wait_hours: float = 24
) -> Dict:
    """
    Poll batch job until completion.

    Returns:
        Final job status
    """
    max_wait_seconds = max_wait_hours * 3600
    start_time = time.time()

    terminal_states = ['completed', 'failed', 'expired', 'cancelled']

    print(f"Waiting for batch job {job_id}...")

    while True:
        batch_job = client.batches.retrieve(job_id)
        status = batch_job.status

        elapsed = time.time() - start_time
        progress = ""
        if batch_job.request_counts:
            progress = f" ({batch_job.request_counts.completed}/{batch_job.request_counts.total})"
        print(f"  [{elapsed/60:.1f}m] Status: {status}{progress}")

        if status in terminal_states:
            return {
                'job': batch_job,
                'status': status,
                'elapsed_seconds': elapsed
            }

        if elapsed > max_wait_seconds:
            print(f"Timeout after {max_wait_hours} hours")
            return {
                'job': batch_job,
                'status': 'TIMEOUT',
                'elapsed_seconds': elapsed
            }

        time.sleep(poll_interval)


def extract_results(client, batch_job, id_to_question: Dict) -> List[Dict]:
    """
    Extract results from completed batch job.

    Returns:
        List of result dicts with question metadata and model responses
    """
    results = []

    if not batch_job.output_file_id:
        print("No output file available")
        return results

    # Download the output file
    output_content = client.files.content(batch_job.output_file_id)
    output_lines = output_content.text.strip().split('\n')

    for line in output_lines:
        if not line.strip():
            continue

        response_data = json.loads(line)
        custom_id = response_data.get('custom_id')

        if custom_id not in id_to_question:
            print(f"Warning: Unknown custom_id {custom_id}")
            continue

        question_meta = id_to_question[custom_id]

        # Extract response
        response_body = response_data.get('response', {}).get('body', {})
        choices = response_body.get('choices', [])

        response_text = ""
        if choices:
            response_text = choices[0].get('message', {}).get('content', '')

        # Extract Malloy query from response
        malloy_query = extract_malloy_code(response_text)

        results.append({
            'question_id': question_meta['question_id'],
            'db_id': question_meta['db_id'],
            'question': question_meta['question'],
            'gold_sql': question_meta['gold_sql'],
            'raw_response': response_text,
            'malloy_query': malloy_query,
            'custom_id': custom_id
        })

    return results


def cmd_submit(args):
    """Submit a new batch job."""
    # Load questions
    sample_file = Path(args.questions)
    questions = load_questions(sample_file)
    print(f"Loaded {len(questions)} questions from {sample_file}")

    # Use expert layer if available
    global MALLOY_DIR
    expert_dir = Path('/workspace/project/malloy/expert')
    if expert_dir.exists():
        import run_evaluation
        run_evaluation.MALLOY_DIR = expert_dir
        print(f"Using expert semantic layers from {expert_dir}")

    # Prepare requests
    requests, id_to_question = prepare_batch_requests(
        questions,
        model=args.model,
        prompt_mode=args.prompt_mode
    )
    print(f"Prepared {len(requests)} batch requests")

    # Submit batch job
    client = get_openai_client()
    display_name = args.name or f"nl2malloy-{args.model}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    job_id = submit_batch_job(client, requests, display_name=display_name)

    # Save job info
    batch_manager.save_job_info(job_id, id_to_question, args.model, display_name)

    print(f"\nBatch job submitted: {job_id}")
    print(f"Use 'python openai_batch.py status {job_id}' to check status")
    print(f"Use 'python openai_batch.py wait {job_id}' to wait for completion")


def cmd_status(args):
    """Check status of a batch job."""
    client = get_openai_client()
    status = check_batch_status(client, args.job_id)

    print(f"Job ID: {status['id']}")
    print(f"Status: {status['status']}")
    print(f"Created: {status['created_at']}")
    if status['completed_at']:
        print(f"Completed: {status['completed_at']}")
    if status['request_counts']:
        rc = status['request_counts']
        print(f"Progress: {rc['completed']}/{rc['total']} ({rc['failed']} failed)")


def cmd_wait(args):
    """Wait for a batch job to complete."""
    client = get_openai_client()

    result = wait_for_completion(
        client,
        args.job_id,
        poll_interval=args.poll_interval
    )

    print(f"\nFinal status: {result['status']}")
    print(f"Elapsed time: {result['elapsed_seconds']/60:.1f} minutes")

    if result['status'] == 'completed':
        # Load saved question mapping
        job_info = batch_manager.load_job_info(args.job_id)
        if job_info:
            id_to_question = job_info['questions']
            results = extract_results(client, result['job'], id_to_question)
            batch_manager.save_results(results, args.job_id, job_info['model'])
            print(f"Extracted {len(results)} results")
        else:
            print("Warning: Could not find saved job info for result extraction")


def cmd_results(args):
    """Retrieve results from a completed batch job."""
    client = get_openai_client()
    batch_job = client.batches.retrieve(args.job_id)

    if batch_job.status != 'completed':
        print(f"Job not yet complete. Status: {batch_job.status}")
        return

    # Load saved question mapping
    job_info = batch_manager.load_job_info(args.job_id)
    if not job_info:
        print("Error: Could not find saved job info")
        return

    id_to_question = job_info['questions']
    results = extract_results(client, batch_job, id_to_question)
    results_file = batch_manager.save_results(results, args.job_id, job_info['model'])

    print(f"Extracted {len(results)} results to {results_file}")


def cmd_list(args):
    """List all batch jobs."""
    client = get_openai_client()

    print("OpenAI Batch Jobs:")
    print("-" * 60)

    try:
        jobs = client.batches.list(limit=20)
        for job in jobs.data:
            print(f"  {job.id}")
            print(f"    Status: {job.status}")
            if job.request_counts:
                print(f"    Progress: {job.request_counts.completed}/{job.request_counts.total}")
            if job.metadata:
                print(f"    Description: {job.metadata.get('description', 'N/A')}")
            print()
    except Exception as e:
        print(f"Error listing jobs: {e}")


def cmd_evaluate(args):
    """Evaluate results from a completed batch job."""
    import asyncio
    import run_evaluation
    from run_evaluation import (
        compile_malloy_query,
        execute_sql_duckdb,
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
        # Try batch_jobs directory
        results_file = BATCH_DIR / args.results_file
        if not results_file.exists():
            print(f"Results file not found: {args.results_file}")
            return

    with open(results_file) as f:
        data = json.load(f)

    results = data['results']
    model = data.get('model', 'unknown')

    print(f"Evaluating {len(results)} results from {model}")
    print("=" * 60)

    # Track results
    total = 0
    compiled = 0
    correct = 0
    errors = []

    async def evaluate_one(r):
        nonlocal total, compiled, correct

        qid = r['question_id']
        db_id = r['db_id']
        malloy_query = r['malloy_query']
        gold_sql = r['gold_sql']
        question = r['question']

        total += 1

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
        description="OpenAI Batch API client for NL2Malloy evaluation"
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Submit command
    submit_parser = subparsers.add_parser('submit', help='Submit a new batch job')
    submit_parser.add_argument(
        '--questions', '-q',
        default='/workspace/project/evaluation/test_hard_extra_100.json',
        help='Path to questions JSON file'
    )
    submit_parser.add_argument(
        '--model', '-m',
        default='gpt-5.2',
        help='OpenAI model to use (default: gpt-5.2)'
    )
    submit_parser.add_argument(
        '--prompt-mode', '-p',
        choices=['standard', 'enhanced', 'cot', 'reasoning'],
        default='standard',
        help='Prompt mode (default: standard)'
    )
    submit_parser.add_argument(
        '--name', '-n',
        help='Display name for the batch job'
    )
    submit_parser.set_defaults(func=cmd_submit)

    # Status command
    status_parser = subparsers.add_parser('status', help='Check batch job status')
    status_parser.add_argument('job_id', help='Batch job ID')
    status_parser.set_defaults(func=cmd_status)

    # Wait command
    wait_parser = subparsers.add_parser('wait', help='Wait for batch job completion')
    wait_parser.add_argument('job_id', help='Batch job ID')
    wait_parser.add_argument(
        '--poll-interval', '-i',
        type=int,
        default=30,
        help='Poll interval in seconds (default: 30)'
    )
    wait_parser.set_defaults(func=cmd_wait)

    # Results command
    results_parser = subparsers.add_parser('results', help='Retrieve batch results')
    results_parser.add_argument('job_id', help='Batch job ID')
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
