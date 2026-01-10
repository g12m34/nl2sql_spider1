# Cost Analysis: NL2SQL with Malloy

## Overview

This document analyzes the estimated API costs for running the Spider dataset through various LLM configurations. We'll start with a 1000-question sample to establish cost/performance tradeoffs before scaling to the full dataset.

## Dataset Summary

| Split | Questions | Notes |
|-------|-----------|-------|
| Training | 7,000 | For fine-tuning and few-shot examples |
| Development | 1,034 | For validation and hyperparameter tuning |
| **Total** | **8,034** | Full Spider 1.0 dataset |
| Databases | 166 | Unique schemas across 138 domains |

## Token Analysis

Based on analysis of the actual Spider dataset:

### Input Components

| Component | Min | Median | Mean | Max | P95 |
|-----------|-----|--------|------|-----|-----|
| Question | 4 | 17 | 18 | 56 | - |
| Schema | 54 | 146 | 208 | 1,813 | 1,149 |
| System prompt | - | - | ~200 | - | - |
| Few-shot examples | - | - | ~400 | - | - |
| **Full prompt** | 661 | 780 | **853** | 2,458 | 1,149 |

### Output Components

| Component | Min | Median | Mean | Max | P95 |
|-----------|-----|--------|------|-----|-----|
| SQL query | 4 | 23 | 27 | 144 | - |
| + Reasoning | - | - | ~100 | - | - |
| **Full output** | 104 | 123 | **127** | 244 | 156 |

### Schema Size Distribution

| Size | Count | Percentage |
|------|-------|------------|
| < 100 tokens | 34 | 20% |
| 100-300 tokens | 101 | 61% |
| 300-500 tokens | 23 | 14% |
| 500+ tokens | 8 | 5% |

## Model Pricing (January 2025)

| Model | Input ($/M) | Output ($/M) | Notes |
|-------|-------------|--------------|-------|
| **Anthropic** | | | |
| Claude Opus 4.5 | $5.00 | $25.00 | Best reasoning |
| Claude Sonnet 4.5 | $3.00 | $15.00 | Balanced |
| Claude Haiku 4.5 | $1.00 | $5.00 | Fast, cheap |
| **Google** | | | |
| Gemini 2.5 Pro | $1.25 | $10.00 | Strong reasoning |
| Gemini 2.5 Flash | $0.30 | $2.50 | Good value |
| Gemini 2.5 Flash-Lite | $0.10 | $0.40 | Budget option |
| **Mistral** | | | |
| Mistral Large 2512 | $0.50 | $1.50 | Good value |
| **DeepSeek** | | | |
| DeepSeek V3 | $0.56 | $1.68 | Excellent value |
| **MiniMax** | | | |
| MiniMax M2 | $0.30 | $1.20 | Budget, but verbose |

## Cost Estimates: 1000-Question Sample

### Single-Agent Architecture

| Model | Input Cost | Output Cost | **Total** | Per Question |
|-------|------------|-------------|-----------|--------------|
| Gemini 2.5 Flash-Lite | $0.09 | $0.05 | **$0.14** | $0.00014 |
| MiniMax M2 | $0.26 | $0.15 | **$0.41** | $0.00041 |
| Gemini 2.5 Flash | $0.26 | $0.32 | **$0.57** | $0.00057 |
| Mistral Large 2512 | $0.43 | $0.19 | **$0.62** | $0.00062 |
| DeepSeek V3 | $0.48 | $0.21 | **$0.69** | $0.00069 |
| Claude Haiku 4.5 | $0.85 | $0.64 | **$1.49** | $0.00149 |
| Gemini 2.5 Pro | $1.07 | $1.27 | **$2.34** | $0.00234 |
| Claude Sonnet 4.5 | $2.56 | $1.91 | **$4.46** | $0.00446 |
| Claude Opus 4.5 | $4.27 | $3.18 | **$7.44** | $0.00744 |

### 3-Agent Architecture

For 1000 questions with ~18 unique databases:

| Agent | Role | Input Tokens | Output Tokens |
|-------|------|--------------|---------------|
| Agent 1 | Semantic Layer Builder | 5.4K | 9K |
| Agent 2 | Malloy Query Generator | 1.12M | 150K |
| Agent 3 | Error Corrector (30%) | 240K | 60K |
| **Total** | | **1.36M** | **219K** |

| Model | Total Cost | Per Question |
|-------|------------|--------------|
| Gemini 2.5 Flash-Lite | **$0.22** | $0.00022 |
| MiniMax M2 | **$0.67** | $0.00067 |
| Gemini 2.5 Flash | **$0.96** | $0.00096 |
| Mistral Large 2512 | **$1.01** | $0.00101 |
| DeepSeek V3 | **$1.13** | $0.00113 |
| Claude Haiku 4.5 | **$2.46** | $0.00246 |
| Gemini 2.5 Pro | **$3.89** | $0.00389 |
| Claude Sonnet 4.5 | **$7.38** | $0.00738 |
| Claude Opus 4.5 | **$12.29** | $0.01229 |

### Hybrid Configurations

| Configuration | Agent 1 | Agent 2 | Agent 3 | **Total** |
|---------------|---------|---------|---------|-----------|
| All Gemini Flash | Flash | Flash | Flash | **$0.96** |
| All DeepSeek V3 | DeepSeek | DeepSeek | DeepSeek | **$1.13** |
| All Haiku 4.5 | Haiku | Haiku | Haiku | **$2.46** |
| Haiku + Sonnet + Haiku | Haiku | Sonnet | Haiku | **$6.19** |
| Flash + Sonnet + Haiku | Flash | Sonnet | Haiku | **$6.16** |

## Experimental Budget Planning

### Phase 1: Baseline Establishment (1000 questions)

| Experiment | Model(s) | Est. Cost |
|------------|----------|-----------|
| Baseline single-agent | Gemini Flash | $0.57 |
| Baseline single-agent | DeepSeek V3 | $0.69 |
| Baseline single-agent | Haiku 4.5 | $1.49 |
| Baseline single-agent | Sonnet 4.5 | $4.46 |
| **Subtotal** | | **$7.21** |

### Phase 2: 3-Agent Architecture (1000 questions)

| Experiment | Configuration | Est. Cost |
|------------|---------------|-----------|
| 3-agent baseline | All Gemini Flash | $0.96 |
| 3-agent baseline | All DeepSeek V3 | $1.13 |
| 3-agent baseline | All Haiku 4.5 | $2.46 |
| 3-agent hybrid | Haiku + Sonnet + Haiku | $6.19 |
| **Subtotal** | | **$10.74** |

### Phase 3: Ablation Studies (1000 questions each)

| Experiment | Description | Est. Cost |
|------------|-------------|-----------|
| No semantic layer | Skip Agent 1, use raw schema | $0.80 |
| No error correction | Skip Agent 3 | $0.75 |
| Enhanced few-shot | 8 examples vs 4 | $1.20 |
| Schema enrichment variants | 3 different approaches | $2.88 |
| **Subtotal** | | **$5.63** |

### Total Estimated Budget

| Phase | Cost |
|-------|------|
| Phase 1: Baselines | $7.21 |
| Phase 2: 3-Agent | $10.74 |
| Phase 3: Ablations | $5.63 |
| Buffer (20%) | $4.72 |
| **Total** | **~$28** |

## Cost Optimization Strategies

### 1. Prompt Caching
- **Anthropic**: 90% savings on cache hits (5-min TTL)
- **Google**: Similar caching available
- Schemas are repeated across questions in same DB → high cache hit rate

### 2. Batch API
- **50% discount** on both Anthropic and Google
- Trade-off: async processing, delayed results
- Good for overnight evaluation runs

### 3. Strategic Model Selection
- Use cheaper models (Flash, Haiku) for:
  - Semantic layer generation (structured output)
  - Error correction (simpler task)
- Reserve expensive models (Sonnet, Opus) for:
  - Query generation (requires reasoning)
  - Final evaluation comparisons

### 4. Early Stopping
- If a configuration shows poor accuracy at 200 questions, abort early
- Saves ~80% of that experiment's cost

## Full Dataset Projections

Once we identify winning configurations from the 1000-question sample:

| Configuration | 1000 Qs | Full (8034 Qs) |
|---------------|---------|----------------|
| Gemini Flash (3-agent) | $0.96 | $7.71 |
| DeepSeek V3 (3-agent) | $1.13 | $9.11 |
| Haiku 4.5 (3-agent) | $2.46 | $19.79 |
| Hybrid (Haiku+Sonnet+Haiku) | $6.19 | $49.81 |
| Sonnet 4.5 (3-agent) | $7.38 | $59.38 |

## Next Steps

1. [ ] Download and prepare Spider dataset
2. [ ] Create 1000-question stratified sample (balanced by difficulty)
3. [ ] Implement baseline single-agent evaluator
4. [ ] Run Phase 1 experiments
5. [ ] Analyze results and identify promising configurations
6. [ ] Implement 3-agent architecture
7. [ ] Run Phase 2 and 3 experiments
8. [ ] Plot cost/performance Pareto frontier
9. [ ] Select optimal configuration for full dataset run

---

*Last updated: January 2025*
