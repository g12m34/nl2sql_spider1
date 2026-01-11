# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the NL2SQL Spider evaluation project.

## What is an ADR?

An ADR documents a significant decision made during the project, including the context, the decision itself, the rationale, and consequences. This creates a historical record of why things were built a certain way.

## ADR Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| [001](001-hard-extra-questions-only.md) | Hard+Extra Questions Only | Accepted | 2025-01-11 |
| [002](002-sample-size-200.md) | Sample Size of 200 Questions | Accepted | 2025-01-11 |
| [003](003-execution-based-evaluation.md) | Execution-Based Evaluation | Accepted | 2025-01-11 |
| [004](004-reproducible-sampling.md) | Reproducible Sampling with Fixed Seed | Accepted | 2025-01-11 |

## ADR Status Definitions

- **Proposed**: Under discussion
- **Accepted**: Decision made and implemented
- **Deprecated**: No longer relevant
- **Superseded**: Replaced by another ADR

## Template

When adding a new ADR, use this template:

```markdown
# ADR-XXX: Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX

**Date:** YYYY-MM-DD

## Context

What is the issue that we're seeing that is motivating this decision?

## Decision

What is the change that we're proposing and/or doing?

## Rationale

Why is this the best choice among the alternatives?

## Consequences

What are the resulting context and trade-offs after applying the decision?
```
