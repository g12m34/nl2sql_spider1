#!/usr/bin/env python3
"""
Observability platform for NL2Malloy evaluation.

Provides structured logging, metrics tracking, and reporting for
evaluation runs across different models and experiments.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class EvaluationResult:
    """Result of evaluating a single question."""
    question_id: int
    db_id: str
    question: str
    gold_sql: str
    malloy_query: str
    compiled_sql: str
    match: bool
    error_type: Optional[str] = None  # 'compile', 'execution', 'logic', 'gold_execution'
    error_message: Optional[str] = None
    expected_rows: Optional[int] = None
    actual_rows: Optional[int] = None
    latency_ms: Optional[float] = None


@dataclass
class EvaluationRun:
    """Metadata for an evaluation run."""
    run_id: str
    model: str
    prompt_mode: str
    started_at: str
    completed_at: Optional[str] = None
    total_questions: int = 0
    compiled: int = 0
    correct: int = 0
    accuracy: float = 0.0
    compile_rate: float = 0.0
    notes: str = ""
    experiment: str = ""
    results: List[EvaluationResult] = field(default_factory=list)


# =============================================================================
# Observability Database
# =============================================================================

class ObservabilityDB:
    """SQLite-based observability database for evaluation tracking."""

    def __init__(self, db_path: Path = None):
        """Initialize the database connection."""
        if db_path is None:
            db_path = Path('/workspace/project/evaluation/observability.db')

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_conn()

        conn.executescript("""
            -- Evaluation runs table
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                prompt_mode TEXT NOT NULL,
                experiment TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                total_questions INTEGER DEFAULT 0,
                compiled INTEGER DEFAULT 0,
                correct INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0.0,
                compile_rate REAL DEFAULT 0.0,
                notes TEXT
            );

            -- Individual question results
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                db_id TEXT NOT NULL,
                question TEXT NOT NULL,
                gold_sql TEXT,
                malloy_query TEXT,
                compiled_sql TEXT,
                match BOOLEAN NOT NULL,
                error_type TEXT,
                error_message TEXT,
                expected_rows INTEGER,
                actual_rows INTEGER,
                latency_ms REAL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_results_run_id ON results(run_id);
            CREATE INDEX IF NOT EXISTS idx_results_question_id ON results(question_id);
            CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model);
            CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs(experiment);
        """)

        conn.commit()
        conn.close()

    def log_run(self, run: EvaluationRun) -> str:
        """Log an evaluation run and its results."""
        conn = self._get_conn()

        # Insert run metadata
        conn.execute("""
            INSERT OR REPLACE INTO runs
            (run_id, model, prompt_mode, experiment, started_at, completed_at,
             total_questions, compiled, correct, accuracy, compile_rate, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run.run_id, run.model, run.prompt_mode, run.experiment,
            run.started_at, run.completed_at, run.total_questions,
            run.compiled, run.correct, run.accuracy, run.compile_rate, run.notes
        ))

        # Insert individual results
        for result in run.results:
            conn.execute("""
                INSERT INTO results
                (run_id, question_id, db_id, question, gold_sql, malloy_query,
                 compiled_sql, match, error_type, error_message, expected_rows,
                 actual_rows, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id, result.question_id, result.db_id, result.question,
                result.gold_sql, result.malloy_query, result.compiled_sql,
                result.match, result.error_type, result.error_message,
                result.expected_rows, result.actual_rows, result.latency_ms
            ))

        conn.commit()
        conn.close()

        return run.run_id

    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get a specific run by ID."""
        conn = self._get_conn()

        row = conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()

        if not row:
            conn.close()
            return None

        run = dict(row)

        # Get results
        results = conn.execute(
            "SELECT * FROM results WHERE run_id = ? ORDER BY question_id",
            (run_id,)
        ).fetchall()

        run['results'] = [dict(r) for r in results]

        conn.close()
        return run

    def list_runs(
        self,
        model: str = None,
        experiment: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """List evaluation runs with optional filters."""
        conn = self._get_conn()

        query = "SELECT * FROM runs WHERE 1=1"
        params = []

        if model:
            query += " AND model = ?"
            params.append(model)

        if experiment:
            query += " AND experiment = ?"
            params.append(experiment)

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        return [dict(r) for r in rows]

    def get_model_comparison(self, experiment: str = None) -> List[Dict]:
        """Get accuracy comparison across models."""
        conn = self._get_conn()

        query = """
            SELECT
                model,
                prompt_mode,
                experiment,
                COUNT(*) as num_runs,
                AVG(accuracy) as avg_accuracy,
                MAX(accuracy) as max_accuracy,
                AVG(compile_rate) as avg_compile_rate
            FROM runs
            WHERE 1=1
        """
        params = []

        if experiment:
            query += " AND experiment = ?"
            params.append(experiment)

        query += " GROUP BY model, prompt_mode ORDER BY avg_accuracy DESC"

        rows = conn.execute(query, params).fetchall()
        conn.close()

        return [dict(r) for r in rows]

    def get_error_analysis(self, run_id: str = None) -> Dict:
        """Get error breakdown by type."""
        conn = self._get_conn()

        query = """
            SELECT
                error_type,
                COUNT(*) as count,
                GROUP_CONCAT(DISTINCT db_id) as affected_dbs
            FROM results
            WHERE error_type IS NOT NULL
        """
        params = []

        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)

        query += " GROUP BY error_type ORDER BY count DESC"

        rows = conn.execute(query, params).fetchall()

        # Also get common error messages
        error_messages = {}
        for error_type in ['compile', 'execution', 'logic']:
            msg_query = """
                SELECT error_message, COUNT(*) as count
                FROM results
                WHERE error_type = ?
            """
            msg_params = [error_type]

            if run_id:
                msg_query += " AND run_id = ?"
                msg_params.append(run_id)

            msg_query += " GROUP BY error_message ORDER BY count DESC LIMIT 10"

            msg_rows = conn.execute(msg_query, msg_params).fetchall()
            error_messages[error_type] = [dict(r) for r in msg_rows]

        conn.close()

        return {
            'by_type': [dict(r) for r in rows],
            'common_messages': error_messages
        }

    def get_question_history(self, question_id: int) -> List[Dict]:
        """Get evaluation history for a specific question across runs."""
        conn = self._get_conn()

        rows = conn.execute("""
            SELECT r.*, runs.model, runs.prompt_mode, runs.experiment
            FROM results r
            JOIN runs ON r.run_id = runs.run_id
            WHERE r.question_id = ?
            ORDER BY runs.started_at DESC
        """, (question_id,)).fetchall()

        conn.close()
        return [dict(r) for r in rows]

    def get_hard_questions(self, min_attempts: int = 3) -> List[Dict]:
        """Find questions that consistently fail across multiple runs."""
        conn = self._get_conn()

        rows = conn.execute("""
            SELECT
                question_id,
                db_id,
                question,
                COUNT(*) as attempts,
                SUM(CASE WHEN match THEN 1 ELSE 0 END) as successes,
                ROUND(AVG(CASE WHEN match THEN 1.0 ELSE 0.0 END) * 100, 1) as success_rate,
                GROUP_CONCAT(DISTINCT error_type) as error_types
            FROM results
            GROUP BY question_id
            HAVING COUNT(*) >= ?
            ORDER BY success_rate ASC, attempts DESC
            LIMIT 50
        """, (min_attempts,)).fetchall()

        conn.close()
        return [dict(r) for r in rows]


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(db: ObservabilityDB, run_id: str = None) -> str:
    """Generate a markdown report for evaluation results."""
    lines = []
    lines.append("# NL2Malloy Evaluation Report")
    lines.append(f"\n*Generated: {datetime.now().isoformat()}*\n")

    if run_id:
        # Single run report
        run = db.get_run(run_id)
        if not run:
            return f"Run {run_id} not found"

        lines.append(f"## Run: {run_id}")
        lines.append(f"\n- **Model:** {run['model']}")
        lines.append(f"- **Prompt Mode:** {run['prompt_mode']}")
        lines.append(f"- **Experiment:** {run['experiment'] or 'N/A'}")
        lines.append(f"- **Started:** {run['started_at']}")
        lines.append(f"- **Completed:** {run['completed_at'] or 'In Progress'}")
        lines.append(f"\n### Results")
        lines.append(f"\n| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Questions | {run['total_questions']} |")
        lines.append(f"| Compiled | {run['compiled']} ({run['compile_rate']*100:.1f}%) |")
        lines.append(f"| Correct | {run['correct']} ({run['accuracy']*100:.1f}%) |")

    else:
        # Overview report
        lines.append("## Model Comparison\n")
        comparison = db.get_model_comparison()

        if comparison:
            lines.append("| Model | Prompt Mode | Runs | Avg Accuracy | Best Accuracy | Compile Rate |")
            lines.append("|-------|-------------|------|--------------|---------------|--------------|")
            for c in comparison:
                lines.append(
                    f"| {c['model']} | {c['prompt_mode']} | {c['num_runs']} | "
                    f"{c['avg_accuracy']*100:.1f}% | {c['max_accuracy']*100:.1f}% | "
                    f"{c['avg_compile_rate']*100:.1f}% |"
                )

    # Error analysis
    lines.append("\n## Error Analysis\n")
    errors = db.get_error_analysis(run_id)

    if errors['by_type']:
        lines.append("| Error Type | Count |")
        lines.append("|------------|-------|")
        for e in errors['by_type']:
            lines.append(f"| {e['error_type']} | {e['count']} |")

    # Hard questions
    if not run_id:
        lines.append("\n## Consistently Failing Questions\n")
        hard = db.get_hard_questions()

        if hard:
            lines.append("| Q# | Database | Success Rate | Attempts | Error Types |")
            lines.append("|----|----------|--------------|----------|-------------|")
            for q in hard[:20]:
                lines.append(
                    f"| {q['question_id']} | {q['db_id']} | {q['success_rate']}% | "
                    f"{q['attempts']} | {q['error_types'] or 'N/A'} |"
                )

    return "\n".join(lines)


# =============================================================================
# Import from Batch Results
# =============================================================================

def import_batch_results(
    db: ObservabilityDB,
    results_file: Path,
    eval_file: Path = None,
    experiment: str = ""
) -> str:
    """Import results from batch evaluation files into observability DB."""

    # Load batch results
    with open(results_file) as f:
        batch_data = json.load(f)

    # Load evaluation results if available
    eval_data = None
    if eval_file and eval_file.exists():
        with open(eval_file) as f:
            eval_data = json.load(f)

    # Build run metadata
    run_id = results_file.stem
    model = batch_data.get('model', 'unknown')

    # Determine stats
    results = batch_data.get('results', [])
    total = len(results)

    # If we have eval data, use it
    if eval_data:
        compiled = eval_data.get('compiled', 0)
        correct = eval_data.get('correct', 0)
        errors = eval_data.get('errors', [])

        # Build error lookup
        error_lookup = {e['question_id']: e for e in errors}
    else:
        compiled = 0
        correct = 0
        error_lookup = {}

    # Build evaluation results
    eval_results = []
    for r in results:
        qid = r.get('question_id')
        error_info = error_lookup.get(qid, {})

        is_match = error_info.get('error_type') is None if error_lookup else False

        eval_results.append(EvaluationResult(
            question_id=qid,
            db_id=r.get('db_id', ''),
            question=r.get('question', ''),
            gold_sql=r.get('gold_sql', ''),
            malloy_query=r.get('malloy_query', ''),
            compiled_sql='',  # Not stored in batch results
            match=is_match,
            error_type=error_info.get('error_type'),
            error_message=error_info.get('error'),
            expected_rows=error_info.get('expected_rows'),
            actual_rows=error_info.get('actual_rows')
        ))

    # Create run
    run = EvaluationRun(
        run_id=run_id,
        model=model,
        prompt_mode='standard',  # Could be enhanced to detect from filename
        experiment=experiment,
        started_at=batch_data.get('completed_at', datetime.now().isoformat()),
        completed_at=batch_data.get('completed_at'),
        total_questions=total,
        compiled=compiled if eval_data else total,
        correct=correct,
        accuracy=correct / total if total > 0 else 0.0,
        compile_rate=compiled / total if total > 0 and eval_data else 0.0,
        results=eval_results
    )

    # Log to database
    db.log_run(run)

    return run_id


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="NL2Malloy Observability Platform")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # List runs
    list_parser = subparsers.add_parser('list', help='List evaluation runs')
    list_parser.add_argument('--model', '-m', help='Filter by model')
    list_parser.add_argument('--experiment', '-e', help='Filter by experiment')
    list_parser.add_argument('--limit', '-l', type=int, default=20, help='Max runs to show')

    # Report
    report_parser = subparsers.add_parser('report', help='Generate evaluation report')
    report_parser.add_argument('--run-id', '-r', help='Specific run ID (or show overview)')
    report_parser.add_argument('--output', '-o', help='Output file (default: stdout)')

    # Import
    import_parser = subparsers.add_parser('import', help='Import batch results')
    import_parser.add_argument('results_file', help='Batch results JSON file')
    import_parser.add_argument('--eval-file', '-e', help='Evaluation results JSON file')
    import_parser.add_argument('--experiment', help='Experiment name')

    # Compare models
    compare_parser = subparsers.add_parser('compare', help='Compare model performance')
    compare_parser.add_argument('--experiment', '-e', help='Filter by experiment')

    # Question history
    history_parser = subparsers.add_parser('history', help='Show question history')
    history_parser.add_argument('question_id', type=int, help='Question ID')

    # Hard questions
    hard_parser = subparsers.add_parser('hard', help='Find consistently failing questions')
    hard_parser.add_argument('--min-attempts', '-m', type=int, default=3,
                            help='Minimum attempts required')

    args = parser.parse_args()

    db = ObservabilityDB()

    if args.command == 'list':
        runs = db.list_runs(
            model=args.model,
            experiment=args.experiment,
            limit=args.limit
        )

        print(f"{'Run ID':<40} {'Model':<20} {'Accuracy':>10} {'Date'}")
        print("-" * 80)
        for r in runs:
            print(f"{r['run_id']:<40} {r['model']:<20} {r['accuracy']*100:>9.1f}% {r['started_at'][:10]}")

    elif args.command == 'report':
        report = generate_report(db, run_id=args.run_id)

        if args.output:
            Path(args.output).write_text(report)
            print(f"Report saved to: {args.output}")
        else:
            print(report)

    elif args.command == 'import':
        results_file = Path(args.results_file)
        eval_file = Path(args.eval_file) if args.eval_file else None

        run_id = import_batch_results(
            db, results_file, eval_file,
            experiment=args.experiment or ""
        )
        print(f"Imported run: {run_id}")

    elif args.command == 'compare':
        comparison = db.get_model_comparison(experiment=args.experiment)

        print(f"{'Model':<25} {'Prompt Mode':<12} {'Runs':>5} {'Avg Acc':>10} {'Best':>8}")
        print("-" * 65)
        for c in comparison:
            print(
                f"{c['model']:<25} {c['prompt_mode']:<12} {c['num_runs']:>5} "
                f"{c['avg_accuracy']*100:>9.1f}% {c['max_accuracy']*100:>7.1f}%"
            )

    elif args.command == 'history':
        history = db.get_question_history(args.question_id)

        print(f"History for Question {args.question_id}:")
        print("-" * 60)
        for h in history:
            status = "CORRECT" if h['match'] else f"WRONG ({h['error_type']})"
            print(f"  {h['model']:<20} {status:<20} {h.get('experiment', '')}")

    elif args.command == 'hard':
        hard = db.get_hard_questions(min_attempts=args.min_attempts)

        print(f"{'Q#':>5} {'Database':<15} {'Success':>10} {'Attempts':>10} {'Error Types'}")
        print("-" * 70)
        for q in hard:
            print(
                f"{q['question_id']:>5} {q['db_id']:<15} {q['success_rate']:>9.1f}% "
                f"{q['attempts']:>10} {q['error_types'] or 'N/A'}"
            )

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
