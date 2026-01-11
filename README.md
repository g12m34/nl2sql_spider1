# NL2SQL with Malloy Semantic Layer

## Overview

This project explores a novel approach to Natural Language to SQL (NL2SQL) translation by leveraging the [Malloy](https://www.malloydata.dev/) semantic layer. Our hypothesis is that embracing semantic layer formalism will improve accuracy by cleanly separating concerns across specialized sub-agents.

## Motivation

Many top-performing NL2SQL approaches essentially re-implement aspects of a semantic layer:
- Enriching column descriptions passed to the model
- Implementing correct join conditions in prompts
- Managing table relationships and metadata

Rather than ad-hoc prompt engineering, we believe a formal semantic layer provides a principled foundation for these enhancements.

## Architecture

We propose a multi-agent ecosystem with three specialized sub-agents:

| Sub-Agent | Responsibility |
|-----------|----------------|
| **Semantic Layer Agent** | Creates and enriches the Malloy semantic model - column names, definitions, relationships, joins |
| **Query Agent** | Translates natural language questions into Malloy queries |
| **Error Correction Agent** | Identifies and fixes syntax errors, semantic issues, and query failures |

## Goals

### 1. Build the Sub-Agent Ecosystem
Design and implement a coordinated multi-agent system where each agent focuses on its specialty, enabling:
- Better separation of concerns
- Easier debugging and improvement of individual components
- Composable, testable pipeline stages

### 2. Improve Malloy Query Generation
Current LLMs (including Claude) struggle with Malloy:
- Incorrectly believing certain operations aren't supported
- Syntax errors in generated queries
- Missing Malloy-specific idioms and patterns

We'll explore multiple approaches to improvement:
- **Prompting strategies** - Better examples, documentation, few-shot learning
- **Fine-tuning** - Training on correct Malloy query examples
- **Tool use** - Malloy validation and auto-correction tools

## Methodology

### Dataset
We use the [Spider](https://yale-lily.github.io/spider) benchmark - a large-scale, cross-domain NL2SQL dataset with complex queries spanning multiple tables.

### Data Splits
Following ML best practices:
- **Training set** - For model development and fine-tuning
- **Validation set** - For hyperparameter tuning and approach selection
- **Test set** - For final evaluation (held out until end)

### Evaluation
- **Ablation studies** - Systematically remove components to measure individual contribution
- **Sensitivity analysis** - Understand which changes have the largest impact on accuracy
- **Error analysis** - Categorize failure modes to guide improvements

## Project Structure

```
.
├── README.md
├── data/               # Spider dataset and processed files
├── agents/             # Sub-agent implementations
│   ├── semantic/       # Semantic layer agent
│   ├── query/          # Malloy query generation agent
│   └── correction/     # Error correction agent
├── malloy/             # Malloy models and schemas
├── evaluation/         # Evaluation scripts and metrics
├── experiments/        # Ablation studies and experiments
└── notebooks/          # Analysis and exploration
```

## Getting Started

*Coming soon*

## References

- [Spider Dataset](https://yale-lily.github.io/spider) - Yale LILY Lab
- [Malloy](https://www.malloydata.dev/) - Semantic data modeling language
- [Malloy Documentation](https://docs.malloydata.dev/)

## License

TBD
