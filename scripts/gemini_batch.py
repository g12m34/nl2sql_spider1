#!/usr/bin/env python3
"""
Gemini Batch API client for NL2Malloy evaluation.

Submits evaluation questions as a batch job to Gemini for 50% cost savings.
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
    MALLOY_DIR
)

# Directories
EVALUATION_DIR = Path('/workspace/project/evaluation')
BATCH_DIR = EVALUATION_DIR / 'batch_jobs'
BATCH_DIR.mkdir(parents=True, exist_ok=True)


def get_genai_client():
    """Initialize the Google GenAI client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment")

    from google import genai
    client = genai.Client(api_key=api_key)
    return client


def prepare_batch_requests(
    questions: List[Dict],
    model: str = "gemini-2.5-flash",
    prompt_mode: str = "standard"
) -> Tuple[List[Dict], Dict[str, Dict]]:
    """
    Prepare batch requests from evaluation questions.

    Returns:
        - List of inline request objects for Gemini batch API
        - Mapping of request keys to question metadata
    """
    inline_requests = []
    key_to_question = {}

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

        # Build prompt
        prompt = build_malloy_prompt(malloy_layer, question_text, mode=prompt_mode)

        # Create request key
        request_key = f"q{question_id}_{db_id}"

        # Build inline request
        request = {
            'contents': [
                {
                    'parts': [{'text': prompt}],
                    'role': 'user'
                }
            ]
        }

        inline_requests.append(request)
        key_to_question[request_key] = {
            'question_id': question_id,
            'db_id': db_id,
            'question': question_text,
            'gold_sql': q.get('gold_sql', q.get('query', '')),
            'request_index': len(inline_requests) - 1
        }

    return inline_requests, key_to_question


def submit_batch_job(
    client,
    requests: List[Dict],
    model: str = "gemini-2.5-flash",
    display_name: str = None
) -> str:
    """
    Submit a batch job to Gemini.

    Returns:
        Batch job name/ID
    """
    if display_name is None:
        display_name = f"nl2malloy-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"Submitting batch job with {len(requests)} requests...")
    print(f"Model: {model}")
    print(f"Display name: {display_name}")

    batch_job = client.batches.create(
        model=f"models/{model}",
        src=requests,
        config={'display_name': display_name}
    )

    print(f"Batch job created: {batch_job.name}")
    print(f"State: {batch_job.state}")

    return batch_job.name


def check_batch_status(client, job_name: str) -> Dict:
    """
    Check the status of a batch job.

    Returns:
        Dict with job status information
    """
    batch_job = client.batches.get(name=job_name)

    return {
        'name': batch_job.name,
        'state': str(batch_job.state),
        'display_name': getattr(batch_job, 'display_name', None),
        'create_time': str(getattr(batch_job, 'create_time', None)),
    }


def wait_for_completion(
    client,
    job_name: str,
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

    terminal_states = ['JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED']

    print(f"Waiting for batch job {job_name}...")

    while True:
        batch_job = client.batches.get(name=job_name)
        state = str(batch_job.state)
        state_name = state.split('.')[-1] if '.' in state else state

        elapsed = time.time() - start_time
        print(f"  [{elapsed/60:.1f}m] State: {state_name}")

        if state_name in terminal_states or any(s in state for s in terminal_states):
            return {
                'job': batch_job,
                'state': state_name,
                'elapsed_seconds': elapsed
            }

        if elapsed > max_wait_seconds:
            print(f"Timeout after {max_wait_hours} hours")
            return {
                'job': batch_job,
                'state': 'TIMEOUT',
                'elapsed_seconds': elapsed
            }

        time.sleep(poll_interval)


def extract_results(batch_job, key_to_question: Dict) -> List[Dict]:
    """
    Extract results from completed batch job.

    Returns:
        List of result dicts with question metadata and model responses
    """
    results = []

    # Check for inline responses
    if hasattr(batch_job, 'dest') and hasattr(batch_job.dest, 'inlined_responses'):
        responses = batch_job.dest.inlined_responses or []

        # Map responses back to questions by index
        index_to_key = {v['request_index']: k for k, v in key_to_question.items()}

        for idx, response in enumerate(responses):
            key = index_to_key.get(idx)
            if key is None:
                continue

            question_meta = key_to_question[key]

            # Extract response text
            response_text = ""
            if hasattr(response, 'response'):
                if hasattr(response.response, 'text'):
                    response_text = response.response.text
                elif hasattr(response.response, 'candidates'):
                    candidates = response.response.candidates
                    if candidates and len(candidates) > 0:
                        parts = candidates[0].content.parts
                        if parts and len(parts) > 0:
                            response_text = parts[0].text

            # Extract Malloy query from response
            malloy_query = extract_malloy_code(response_text)

            results.append({
                'question_id': question_meta['question_id'],
                'db_id': question_meta['db_id'],
                'question': question_meta['question'],
                'gold_sql': question_meta['gold_sql'],
                'raw_response': response_text,
                'malloy_query': malloy_query,
                'request_key': key
            })

    return results


def extract_malloy_code(response: str) -> str:
    """Extract Malloy code from model response."""
    text = response.strip()

    # Remove markdown code blocks
    if text.startswith("```malloy"):
        text = text[9:]
    elif text.startswith("```sql"):
        text = text[6:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def save_batch_job_info(job_name: str, key_to_question: Dict, model: str):
    """Save batch job info for later retrieval."""
    info = {
        'job_name': job_name,
        'model': model,
        'submitted_at': datetime.now().isoformat(),
        'questions': key_to_question
    }

    info_file = BATCH_DIR / f"{job_name.replace('/', '_')}.json"
    with open(info_file, 'w') as f:
        json.dump(info, f, indent=2)

    print(f"Job info saved to: {info_file}")
    return info_file


def load_batch_job_info(job_name: str) -> Optional[Dict]:
    """Load saved batch job info."""
    info_file = BATCH_DIR / f"{job_name.replace('/', '_')}.json"
    if info_file.exists():
        with open(info_file) as f:
            return json.load(f)
    return None


def save_results(results: List[Dict], job_name: str, model: str):
    """Save batch results for evaluation."""
    output = {
        'job_name': job_name,
        'model': model,
        'completed_at': datetime.now().isoformat(),
        'num_results': len(results),
        'results': results
    }

    results_file = BATCH_DIR / f"results_{job_name.replace('/', '_')}.json"
    with open(results_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Results saved to: {results_file}")
    return results_file


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
        from run_evaluation import MALLOY_DIR as orig_dir
        import run_evaluation
        run_evaluation.MALLOY_DIR = expert_dir
        print(f"Using expert semantic layers from {expert_dir}")

    # Prepare requests
    requests, key_to_question = prepare_batch_requests(
        questions,
        model=args.model,
        prompt_mode=args.prompt_mode
    )
    print(f"Prepared {len(requests)} batch requests")

    # Submit batch job
    client = get_genai_client()
    job_name = submit_batch_job(
        client,
        requests,
        model=args.model,
        display_name=args.name
    )

    # Save job info
    save_batch_job_info(job_name, key_to_question, args.model)

    print(f"\nBatch job submitted: {job_name}")
    print(f"Use 'python gemini_batch.py status {job_name}' to check status")
    print(f"Use 'python gemini_batch.py wait {job_name}' to wait for completion")


def cmd_status(args):
    """Check status of a batch job."""
    client = get_genai_client()
    status = check_batch_status(client, args.job_name)

    print(f"Job: {status['name']}")
    print(f"State: {status['state']}")
    print(f"Display Name: {status['display_name']}")
    print(f"Created: {status['create_time']}")


def cmd_wait(args):
    """Wait for a batch job to complete."""
    client = get_genai_client()

    result = wait_for_completion(
        client,
        args.job_name,
        poll_interval=args.poll_interval
    )

    print(f"\nFinal state: {result['state']}")
    print(f"Elapsed time: {result['elapsed_seconds']/60:.1f} minutes")

    if 'SUCCEEDED' in result['state']:
        # Load saved question mapping
        job_info = load_batch_job_info(args.job_name)
        if job_info:
            key_to_question = job_info['questions']
            results = extract_results(result['job'], key_to_question)
            save_results(results, args.job_name, job_info['model'])
            print(f"Extracted {len(results)} results")
        else:
            print("Warning: Could not find saved job info for result extraction")


def cmd_results(args):
    """Retrieve results from a completed batch job."""
    client = get_genai_client()
    batch_job = client.batches.get(name=args.job_name)

    state = str(batch_job.state)
    if 'SUCCEEDED' not in state:
        print(f"Job not yet complete. State: {state}")
        return

    # Load saved question mapping
    job_info = load_batch_job_info(args.job_name)
    if not job_info:
        print("Error: Could not find saved job info")
        return

    key_to_question = job_info['questions']
    results = extract_results(batch_job, key_to_question)
    results_file = save_results(results, args.job_name, job_info['model'])

    print(f"Extracted {len(results)} results to {results_file}")


def cmd_list(args):
    """List all batch jobs."""
    client = get_genai_client()

    print("Batch Jobs:")
    print("-" * 60)

    # List jobs from API
    try:
        jobs = client.batches.list()
        for job in jobs:
            name = job.name
            state = str(job.state).split('.')[-1]
            display = getattr(job, 'display_name', 'N/A')
            print(f"  {name}")
            print(f"    State: {state}")
            print(f"    Display: {display}")
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
        # Try batch_jobs directory
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
        description="Gemini Batch API client for NL2Malloy evaluation"
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
        default='gemini-2.5-flash',
        help='Gemini model to use (default: gemini-2.5-flash)'
    )
    submit_parser.add_argument(
        '--prompt-mode', '-p',
        choices=['standard', 'enhanced', 'cot'],
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
    status_parser.add_argument('job_name', help='Batch job name/ID')
    status_parser.set_defaults(func=cmd_status)

    # Wait command
    wait_parser = subparsers.add_parser('wait', help='Wait for batch job completion')
    wait_parser.add_argument('job_name', help='Batch job name/ID')
    wait_parser.add_argument(
        '--poll-interval', '-i',
        type=int,
        default=30,
        help='Poll interval in seconds (default: 30)'
    )
    wait_parser.set_defaults(func=cmd_wait)

    # Results command
    results_parser = subparsers.add_parser('results', help='Retrieve batch results')
    results_parser.add_argument('job_name', help='Batch job name/ID')
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
