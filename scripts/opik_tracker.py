#!/usr/bin/env python3
"""
Opik integration for NL2Malloy experiment tracking.

Logs evaluation results to Opik by Comet for experiment tracking and comparison.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path, override=True)

import opik
from opik import Opik

# Directories
BATCH_DIR = Path('/workspace/project/evaluation/batch_jobs')
RESULTS_DIR = Path('/workspace/project/evaluation/results')


def init_opik() -> Opik:
    """Initialize Opik client."""
    api_key = os.getenv('OPIK_API_KEY')
    if not api_key:
        raise ValueError("OPIK_API_KEY not set in environment")

    # Configure opik non-interactively
    opik.configure(
        api_key=api_key,
        workspace="gmoorr3",
        use_local=False
    )
    return Opik()


def load_evaluation_results() -> Dict[str, Dict]:
    """Load all evaluation results from batch jobs."""
    results = {}

    # Load batch evaluation results
    for eval_file in BATCH_DIR.glob('eval_results_*.json'):
        with open(eval_file) as f:
            data = json.load(f)
        model = data.get('model', 'unknown')
        results[model] = data

    # Load DeepSeek results from main evaluation
    deepseek_file = RESULTS_DIR / 'deepseek-v3.2_malloy.json'
    if deepseek_file.exists():
        with open(deepseek_file) as f:
            data = json.load(f)

        # Convert to standard format
        correct = sum(1 for r in data['results'] if r.get('match') and not r.get('error'))
        total = len(data['results'])
        errors = []
        for r in data['results']:
            if r.get('error') or not r.get('match'):
                errors.append({
                    'question_id': r['question_id'],
                    'db_id': r['db_id'],
                    'error_type': 'compile' if r.get('error') else 'logic'
                })

        results['deepseek-v3.2'] = {
            'model': 'deepseek-v3.2',
            'total': total,
            'correct': correct,
            'compiled': sum(1 for r in data['results'] if not r.get('error') or 'compile' not in str(r.get('error', '')).lower()),
            'errors': errors
        }

    return results


def create_dataset(client: Opik, name: str = "nl2malloy-test-46") -> opik.Dataset:
    """Create or get the test dataset in Opik."""
    # Load questions
    questions_file = Path('/workspace/project/evaluation/enriched_test_sample.json')
    with open(questions_file) as f:
        data = json.load(f)

    dataset = client.get_or_create_dataset(name=name)

    # Insert questions if dataset is empty
    items = []
    for q in data['questions']:
        items.append({
            "input": {
                "question_id": q.get('id', q.get('question_id')),
                "db_id": q['db_id'],
                "question": q['question']
            },
            "expected_output": q.get('gold_sql', '')
        })

    if items:
        dataset.insert(items)

    return dataset


def log_experiment(client: Opik, model_name: str, results: Dict, experiment_name: str = None):
    """Log an experiment run to Opik."""
    if experiment_name is None:
        experiment_name = f"nl2malloy-{model_name}-{datetime.now().strftime('%Y%m%d-%H%M')}"

    total = results.get('total', 46)
    correct = results.get('correct', 0)
    compiled = results.get('compiled', 0)
    errors = results.get('errors', [])

    # Calculate metrics
    accuracy = correct / total if total > 0 else 0
    compile_rate = compiled / total if total > 0 else 0

    compile_errors = len([e for e in errors if e.get('error_type') == 'compile'])
    logic_errors = len([e for e in errors if e.get('error_type') == 'logic'])

    # Create experiment trace
    trace = client.trace(
        name=experiment_name,
        input={"model": model_name, "total_questions": total},
        output={
            "accuracy": accuracy,
            "compile_rate": compile_rate,
            "correct": correct,
            "compiled": compiled,
            "compile_errors": compile_errors,
            "logic_errors": logic_errors
        },
        metadata={
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "errors": errors[:10]  # Sample of errors
        }
    )

    print(f"Logged experiment: {experiment_name}")
    print(f"  Accuracy: {accuracy*100:.1f}%")
    print(f"  Compile Rate: {compile_rate*100:.1f}%")

    return trace


def log_all_experiments(client: Opik):
    """Log all available experiment results to Opik."""
    results = load_evaluation_results()

    print(f"Found {len(results)} model results to log")

    for model_name, data in results.items():
        log_experiment(client, model_name, data)
        print()


def create_comparison_report(client: Opik) -> Dict:
    """Create a comparison summary of all experiments."""
    results = load_evaluation_results()

    comparison = {
        "timestamp": datetime.now().isoformat(),
        "models": [],
        "best_model": None,
        "best_accuracy": 0
    }

    for model_name, data in sorted(results.items(), key=lambda x: -x[1].get('correct', 0)):
        total = data.get('total', 46)
        correct = data.get('correct', 0)
        compiled = data.get('compiled', 0)
        accuracy = correct / total if total > 0 else 0
        compile_rate = compiled / total if total > 0 else 0

        model_summary = {
            "model": model_name,
            "accuracy": accuracy,
            "compile_rate": compile_rate,
            "correct": correct,
            "total": total
        }
        comparison["models"].append(model_summary)

        if accuracy > comparison["best_accuracy"]:
            comparison["best_accuracy"] = accuracy
            comparison["best_model"] = model_name

    return comparison


def main():
    """Main function to log experiments to Opik."""
    print("Initializing Opik client...")
    client = init_opik()

    print("\nCreating/updating dataset...")
    dataset = create_dataset(client)
    print(f"Dataset: {dataset.name}")

    print("\nLogging experiments...")
    log_all_experiments(client)

    print("\nComparison Summary:")
    comparison = create_comparison_report(client)
    print(f"Best Model: {comparison['best_model']} ({comparison['best_accuracy']*100:.1f}%)")

    print("\n" + "="*60)
    print("All experiments logged to Opik!")
    print("View results at: https://www.comet.com/opik")


if __name__ == '__main__':
    main()
