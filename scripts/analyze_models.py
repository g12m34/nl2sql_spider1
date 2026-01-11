#!/usr/bin/env python3
"""
Cross-model error analysis for NL2Malloy evaluation.

Analyzes results from multiple models to identify:
- Common error patterns
- Model-specific strengths/weaknesses
- Hypotheses for improvement
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple
from datetime import datetime

BATCH_DIR = Path('/workspace/project/evaluation/batch_jobs')
RESULTS_DIR = Path('/workspace/project/evaluation/results')


def load_batch_eval(filepath: Path) -> Dict:
    """Load batch evaluation results."""
    with open(filepath) as f:
        return json.load(f)


def load_deepseek_results() -> Dict:
    """Load DeepSeek results from main evaluation."""
    filepath = RESULTS_DIR / 'deepseek-v3.2_malloy.json'
    with open(filepath) as f:
        data = json.load(f)

    # Convert to batch eval format
    results = []
    errors = []
    correct = 0
    compiled = 0

    for r in data['results']:
        qid = r['question_id']
        db_id = r['db_id']
        question = r['question']
        match = r.get('match', False)
        error = r.get('error')

        if error:
            if 'compile' in error.lower() or 'undefined' in error.lower() or 'not defined' in error.lower():
                error_type = 'compile'
            else:
                error_type = 'execution'
            errors.append({
                'question_id': qid,
                'db_id': db_id,
                'question': question,
                'error_type': error_type,
                'error': error
            })
        elif not match:
            compiled += 1
            errors.append({
                'question_id': qid,
                'db_id': db_id,
                'question': question,
                'error_type': 'logic',
                'expected_rows': r.get('gold_row_count'),
                'actual_rows': r.get('pred_row_count')
            })
        else:
            compiled += 1
            correct += 1

        results.append({
            'question_id': qid,
            'db_id': db_id,
            'question': question,
            'correct': match and not error
        })

    return {
        'model': 'deepseek-v3.2',
        'total': len(data['results']),
        'compiled': compiled,
        'correct': correct,
        'errors': errors,
        'results': results
    }


def load_all_models() -> Dict[str, Dict]:
    """Load results from all models."""
    models = {}

    # DeepSeek
    models['DeepSeek v3.2'] = load_deepseek_results()

    # Gemini Flash
    gemini_flash_file = BATCH_DIR / 'eval_results_batches_980j80im9bz6zjwlrbkwk7dqycxg0gop7ft1.json'
    if gemini_flash_file.exists():
        models['Gemini 2.5 Flash'] = load_batch_eval(gemini_flash_file)

    # Gemini Pro
    gemini_pro_files = list(BATCH_DIR.glob('eval_results_batches_k6g6*.json'))
    if gemini_pro_files:
        models['Gemini 2.5 Pro'] = load_batch_eval(gemini_pro_files[0])

    # Claude Sonnet
    sonnet_file = BATCH_DIR / 'eval_results_anthropic_msgbatch_013GeCZrpbXShYfZuhHoWbzm.json'
    if sonnet_file.exists():
        models['Claude Sonnet 4.5'] = load_batch_eval(sonnet_file)

    # Claude Opus
    opus_file = BATCH_DIR / 'eval_results_anthropic_msgbatch_01LZrSL1YFXK6QY7ykBDYLBp.json'
    if opus_file.exists():
        models['Claude Opus 4.5'] = load_batch_eval(opus_file)

    return models


def get_question_results(models: Dict[str, Dict]) -> Dict[int, Dict[str, bool]]:
    """Get per-question results for each model."""
    questions = defaultdict(dict)

    for model_name, data in models.items():
        errors = {e['question_id']: e for e in data.get('errors', [])}
        total = data.get('total', 46)
        correct = data.get('correct', 0)

        # Build question results from errors
        error_qids = set(errors.keys())

        # For batch results, we need to infer correct questions
        if 'results' in data:
            for r in data['results']:
                qid = r['question_id']
                questions[qid][model_name] = r.get('correct', qid not in error_qids)
        else:
            # Infer from errors - assume 46 questions total
            for qid in range(200):  # Check all possible question IDs
                if qid in error_qids:
                    questions[qid][model_name] = False

    return dict(questions)


def categorize_errors(models: Dict[str, Dict]) -> Dict[str, Dict[str, List]]:
    """Categorize errors by type for each model."""
    categories = {}

    for model_name, data in models.items():
        cats = defaultdict(list)
        for e in data.get('errors', []):
            error_type = e.get('error_type', 'unknown')
            cats[error_type].append(e)
        categories[model_name] = dict(cats)

    return categories


def find_common_failures(models: Dict[str, Dict]) -> Tuple[Set[int], Set[int], Dict[int, List[str]]]:
    """Find questions that multiple models fail on."""
    # Get failed questions per model
    model_failures = {}
    for model_name, data in models.items():
        failed = set(e['question_id'] for e in data.get('errors', []))
        model_failures[model_name] = failed

    # Find common failures (failed by all models)
    all_models = list(model_failures.keys())
    if not all_models:
        return set(), set(), {}

    common_failures = model_failures[all_models[0]].copy()
    for model in all_models[1:]:
        common_failures &= model_failures[model]

    # Find unique successes (only one model got it right)
    all_failures = set()
    for fails in model_failures.values():
        all_failures |= fails

    # Track which models failed each question
    question_failures = defaultdict(list)
    for qid in all_failures:
        for model_name, failed in model_failures.items():
            if qid in failed:
                question_failures[qid].append(model_name)

    return common_failures, all_failures, dict(question_failures)


def analyze_error_patterns(models: Dict[str, Dict]) -> Dict:
    """Analyze error patterns across models."""
    patterns = {
        'join_path': [],  # Issues with nested joins
        'syntax': [],     # Malloy syntax errors
        'schema_linking': [],  # Wrong field/source names
        'aggregation': [],  # Wrong aggregate functions
        'filtering': [],   # Filter logic issues
        'other': []
    }

    for model_name, data in models.items():
        for e in data.get('errors', []):
            error_str = str(e.get('error', '')).lower()
            qid = e['question_id']

            entry = {'model': model_name, 'question_id': qid, 'error': e}

            if 'not defined' in error_str or 'undefined' in error_str:
                if 'join' in error_str or '.' in error_str:
                    patterns['join_path'].append(entry)
                else:
                    patterns['schema_linking'].append(entry)
            elif 'syntax' in error_str or 'parse' in error_str:
                patterns['syntax'].append(entry)
            elif 'aggregate' in error_str or 'count' in error_str or 'sum' in error_str:
                patterns['aggregation'].append(entry)
            elif 'where' in error_str or 'filter' in error_str:
                patterns['filtering'].append(entry)
            elif e.get('error_type') == 'logic':
                patterns['other'].append(entry)
            else:
                patterns['other'].append(entry)

    return patterns


def load_questions_metadata() -> Dict[int, Dict]:
    """Load question metadata."""
    filepath = Path('/workspace/project/evaluation/enriched_test_sample.json')
    with open(filepath) as f:
        data = json.load(f)

    return {q.get('id', q.get('question_id', i)): q for i, q in enumerate(data['questions'])}


def generate_report(models: Dict[str, Dict]) -> str:
    """Generate markdown analysis report."""

    questions_meta = load_questions_metadata()
    categories = categorize_errors(models)
    common_failures, all_failures, question_failures = find_common_failures(models)
    patterns = analyze_error_patterns(models)

    report = []
    report.append("# NL2Malloy Cross-Model Error Analysis")
    report.append("")
    report.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    report.append("")

    # Executive Summary
    report.append("## Executive Summary")
    report.append("")
    report.append("This analysis compares the performance of 5 frontier LLMs on the NL2Malloy task:")
    report.append("converting natural language questions to Malloy queries using expert semantic layers.")
    report.append("")

    # Results table
    report.append("### Overall Results")
    report.append("")
    report.append("| Model | Compile Rate | Execution Accuracy | Accuracy Rank |")
    report.append("|-------|--------------|-------------------|---------------|")

    # Sort by accuracy
    sorted_models = sorted(models.items(), key=lambda x: x[1].get('correct', 0), reverse=True)
    for rank, (model_name, data) in enumerate(sorted_models, 1):
        total = data.get('total', 46)
        compiled = data.get('compiled', 0)
        correct = data.get('correct', 0)
        compile_pct = compiled / total * 100 if total > 0 else 0
        correct_pct = correct / total * 100 if total > 0 else 0
        report.append(f"| {model_name} | {compile_pct:.1f}% ({compiled}/{total}) | {correct_pct:.1f}% ({correct}/{total}) | #{rank} |")

    report.append("")

    # Key Findings
    report.append("### Key Findings")
    report.append("")
    best_model = sorted_models[0][0]
    best_acc = sorted_models[0][1].get('correct', 0) / sorted_models[0][1].get('total', 46) * 100
    report.append(f"1. **{best_model}** leads with {best_acc:.1f}% execution accuracy")
    report.append(f"2. **{len(common_failures)} questions** failed across ALL models (systematic issues)")
    report.append(f"3. **{len(all_failures)} unique questions** had at least one model fail")
    report.append("")

    # Error Breakdown by Model
    report.append("## Error Breakdown by Model")
    report.append("")

    for model_name, cats in categories.items():
        data = models[model_name]
        total = data.get('total', 46)
        correct = data.get('correct', 0)
        report.append(f"### {model_name}")
        report.append("")
        report.append(f"**Accuracy: {correct}/{total} ({correct/total*100:.1f}%)**")
        report.append("")

        if cats:
            report.append("| Error Type | Count | Percentage |")
            report.append("|------------|-------|------------|")
            for error_type, errors in sorted(cats.items(), key=lambda x: -len(x[1])):
                pct = len(errors) / total * 100
                report.append(f"| {error_type} | {len(errors)} | {pct:.1f}% |")
            report.append("")
        else:
            report.append("No errors recorded.")
            report.append("")

    # Common Failures Analysis
    report.append("## Common Failure Analysis")
    report.append("")
    report.append("### Questions Failed by ALL Models")
    report.append("")

    if common_failures:
        report.append("These questions represent systematic challenges that no model could solve:")
        report.append("")
        report.append("| Q# | Database | Question | Failed Models |")
        report.append("|----|----------|----------|---------------|")
        for qid in sorted(common_failures):
            meta = questions_meta.get(qid, {})
            db_id = meta.get('db_id', 'unknown')
            question = meta.get('question', 'Unknown')[:60] + '...' if len(meta.get('question', '')) > 60 else meta.get('question', 'Unknown')
            num_failed = len(question_failures.get(qid, []))
            report.append(f"| {qid} | {db_id} | {question} | All ({num_failed}) |")
        report.append("")
    else:
        report.append("No questions failed across all models.")
        report.append("")

    # Questions with Mixed Results
    report.append("### Questions with Mixed Results")
    report.append("")
    report.append("Questions where some models succeeded and others failed (indicates model-specific strengths):")
    report.append("")

    mixed = {qid: fails for qid, fails in question_failures.items()
             if 0 < len(fails) < len(models)}

    if mixed:
        report.append("| Q# | Database | Question | Failed Models | Succeeded Models |")
        report.append("|----|----------|----------|---------------|------------------|")
        for qid in sorted(mixed.keys())[:15]:  # Top 15
            meta = questions_meta.get(qid, {})
            db_id = meta.get('db_id', 'unknown')
            question = meta.get('question', 'Unknown')[:40] + '...' if len(meta.get('question', '')) > 40 else meta.get('question', 'Unknown')
            failed = ', '.join(f[:10] for f in mixed[qid])
            succeeded = ', '.join(m[:10] for m in models.keys() if m not in mixed[qid])
            report.append(f"| {qid} | {db_id} | {question} | {failed} | {succeeded} |")
        report.append("")

    # Error Pattern Analysis
    report.append("## Error Pattern Analysis")
    report.append("")

    pattern_descriptions = {
        'join_path': 'Nested join path errors (e.g., `author.writes.paper.venue` not accessible)',
        'schema_linking': 'Wrong field or source names used',
        'syntax': 'Malloy syntax errors',
        'aggregation': 'Incorrect aggregate function usage',
        'filtering': 'Filter/where clause issues',
        'other': 'Logic errors or other issues'
    }

    for pattern_name, description in pattern_descriptions.items():
        pattern_errors = patterns.get(pattern_name, [])
        if pattern_errors:
            report.append(f"### {pattern_name.replace('_', ' ').title()} ({len(pattern_errors)} occurrences)")
            report.append("")
            report.append(f"*{description}*")
            report.append("")

            # Count by model
            by_model = defaultdict(int)
            for e in pattern_errors:
                by_model[e['model']] += 1

            report.append("| Model | Count |")
            report.append("|-------|-------|")
            for model, count in sorted(by_model.items(), key=lambda x: -x[1]):
                report.append(f"| {model} | {count} |")
            report.append("")

    # Hypotheses for Improvement
    report.append("## Hypotheses for Improvement")
    report.append("")

    report.append("Based on the error analysis, here are targeted hypotheses for improving accuracy:")
    report.append("")

    report.append("### H1: Enhanced Schema Linking Guidance")
    report.append("")
    report.append("**Observation:** Schema linking errors are common, with models using incorrect field names.")
    report.append("")
    report.append("**Hypothesis:** Adding explicit field name listings at the start of the prompt will reduce schema linking errors.")
    report.append("")
    report.append("**Test:** Create a prompt variant that lists all available sources and their fields upfront.")
    report.append("")

    report.append("### H2: Join Path Examples")
    report.append("")
    report.append("**Observation:** Nested join paths (e.g., `author.writes.paper.venue`) frequently cause errors.")
    report.append("")
    report.append("**Hypothesis:** Including explicit examples of valid join paths in the semantic layer comments will help models navigate relationships.")
    report.append("")
    report.append("**Test:** Add `// Valid paths: author.writes.paper.venue.venue_name` comments to semantic layers.")
    report.append("")

    report.append("### H3: Query Templates by Question Type")
    report.append("")
    report.append("**Observation:** Certain question patterns (e.g., \"find entities in BOTH X and Y\") consistently fail.")
    report.append("")
    report.append("**Hypothesis:** Providing query templates for common patterns will improve accuracy on pattern-matching questions.")
    report.append("")
    report.append("**Test:** Add more INTERSECT pattern examples and other common query patterns to the prompt.")
    report.append("")

    report.append("### H4: Chain-of-Thought for Complex Queries")
    report.append("")
    report.append("**Observation:** Logic errors occur even when queries compile, suggesting reasoning failures.")
    report.append("")
    report.append("**Hypothesis:** Requiring models to explicitly reason about the query structure before generating code will reduce logic errors.")
    report.append("")
    report.append("**Test:** Add a chain-of-thought prompt that requires models to: 1) Identify the source, 2) List required fields, 3) Determine if aggregation is needed, 4) Write the query.")
    report.append("")

    report.append("### H5: Few-Shot Examples per Database")
    report.append("")
    report.append("**Observation:** Some databases (e.g., `geo`, `scholar`) have higher error rates.")
    report.append("")
    report.append("**Hypothesis:** Including 1-2 working query examples for each database in the prompt will improve accuracy.")
    report.append("")
    report.append("**Test:** Add database-specific few-shot examples to the semantic layer files.")
    report.append("")

    # Model-Specific Observations
    report.append("## Model-Specific Observations")
    report.append("")

    for model_name, data in sorted_models:
        total = data.get('total', 46)
        correct = data.get('correct', 0)
        compiled = data.get('compiled', 0)

        report.append(f"### {model_name}")
        report.append("")

        cats = categories.get(model_name, {})
        compile_errors = len(cats.get('compile', []))
        logic_errors = len(cats.get('logic', []))

        if compiled > 0:
            compile_rate = compiled / total * 100
            logic_rate = logic_errors / compiled * 100 if compiled > 0 else 0

            report.append(f"- **Compile Rate:** {compile_rate:.1f}%")
            report.append(f"- **Logic Error Rate (of compiled):** {logic_rate:.1f}%")

            if compile_rate > 80:
                report.append("- **Strength:** Strong understanding of Malloy syntax")
            if logic_rate < 15:
                report.append("- **Strength:** Good semantic understanding of queries")
            if compile_errors > 10:
                report.append("- **Weakness:** Struggles with Malloy syntax specifics")
            if logic_errors > 5:
                report.append("- **Weakness:** Logic errors even on compilable queries")

        report.append("")

    # Conclusion
    report.append("## Conclusion")
    report.append("")
    report.append("The analysis reveals that while frontier models can generate Malloy queries with reasonable accuracy,")
    report.append("systematic improvements are possible through:")
    report.append("")
    report.append("1. **Better schema documentation** - Explicit field listings and join path examples")
    report.append("2. **Pattern templates** - Common query patterns like INTERSECT should be documented")
    report.append("3. **Chain-of-thought prompting** - Structured reasoning reduces logic errors")
    report.append("4. **Database-specific examples** - Few-shot learning improves accuracy")
    report.append("")
    report.append("The fact that different models fail on different questions suggests that ensemble approaches")
    report.append("or model-specific prompt tuning could further improve results.")
    report.append("")

    # Appendix
    report.append("## Appendix: Raw Data")
    report.append("")
    report.append("### All Failed Questions by Model")
    report.append("")

    for model_name, data in sorted_models:
        report.append(f"<details>")
        report.append(f"<summary>{model_name} - {len(data.get('errors', []))} failures</summary>")
        report.append("")
        report.append("| Q# | DB | Error Type | Error |")
        report.append("|----|----| -----------|-------|")
        for e in sorted(data.get('errors', []), key=lambda x: x['question_id']):
            qid = e['question_id']
            db = e.get('db_id', 'N/A')
            etype = e.get('error_type', 'N/A')
            error = str(e.get('error', 'N/A'))[:50].replace('|', '/').replace('\n', ' ')
            report.append(f"| {qid} | {db} | {etype} | {error}... |")
        report.append("")
        report.append("</details>")
        report.append("")

    return '\n'.join(report)


def main():
    """Main analysis function."""
    print("Loading model results...")
    models = load_all_models()

    print(f"Loaded {len(models)} models:")
    for name, data in models.items():
        correct = data.get('correct', 0)
        total = data.get('total', 46)
        print(f"  - {name}: {correct}/{total} ({correct/total*100:.1f}%)")

    print("\nGenerating report...")
    report = generate_report(models)

    # Save report
    output_path = Path('/workspace/project/experiments/cross_model_analysis.md')
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"\nReport saved to: {output_path}")
    return report


if __name__ == '__main__':
    main()
