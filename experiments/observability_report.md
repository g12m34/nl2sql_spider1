# NL2Malloy Evaluation Report

*Generated: 2026-01-12T05:55:37.122489*

## Model Comparison

| Model | Prompt Mode | Runs | Avg Accuracy | Best Accuracy | Compile Rate |
|-------|-------------|------|--------------|---------------|--------------|
| gemini-2.5-pro | standard | 1 | 47.0% | 47.0% | 55.0% |
| gemini-2.5-flash | standard | 1 | 46.0% | 46.0% | 55.0% |
| gpt-5-mini | standard | 1 | 14.1% | 14.1% | 45.5% |

## Error Analysis

| Error Type | Count |
|------------|-------|
| compile | 144 |
| execution | 26 |
| logic | 22 |

## Consistently Failing Questions

| Q# | Database | Success Rate | Attempts | Error Types |
|----|----------|--------------|----------|-------------|
| 2463 | movie_1 | 0.0% | 3 | compile |
| 2466 | movie_1 | 0.0% | 3 | logic,execution |
| 2472 | movie_1 | 0.0% | 3 | compile |
| 2473 | movie_1 | 0.0% | 3 | logic,compile |
| 2483 | movie_1 | 0.0% | 3 | logic,compile |
| 2496 | movie_1 | 0.0% | 3 | compile,execution |
| 2514 | movie_1 | 0.0% | 3 | compile,logic |
| 3111 | behavior_monitoring | 0.0% | 3 | compile |
| 5665 | customers_and_products_contacts | 0.0% | 3 | compile |
| 5666 | customers_and_products_contacts | 0.0% | 3 | compile |
| 6043 | game_1 | 0.0% | 3 | logic,compile |
| 6053 | game_1 | 0.0% | 3 | compile,execution |
| 6785 | activity_1 | 0.0% | 3 | compile,logic |
| 6792 | activity_1 | 0.0% | 3 | logic,compile |
| 6793 | activity_1 | 0.0% | 3 | logic,compile |
| 6800 | activity_1 | 0.0% | 3 | logic,compile |
| 7187 | geo | 0.0% | 3 | compile |
| 7306 | geo | 0.0% | 3 | compile |
| 7307 | geo | 0.0% | 3 | compile |
| 7404 | geo | 0.0% | 3 | compile |