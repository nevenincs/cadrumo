---
tags:
  - '#plan'
  - '#just-tooling-bootstrap'
date: '2026-06-04'
modified: '2026-06-04'
tier: L1
related:
  - '[[2026-06-04-just-tooling-bootstrap-research]]'
  - '[[2026-06-04-just-tooling-bootstrap-adr]]'
---


# `just-tooling-bootstrap` `implementation` plan

- [x] `S01` - Declare missing audit dependencies; `pyproject.toml`.
- [x] `S02` - Add quality audit recipes; `justfile`.
- [x] `S03` - Verify new command surface; `just tooling`.
Implement the modern quality-audit bootstrap command surface for the project.

## Description

This plan wires the quality discovery tools identified by the research and ADR into
the Python dependency bootstrap and `just` command surface. It keeps existing hard
gates separate from advisory audit dashboards so contributors can distinguish daily
green checks from refactor-planning reports.

## Steps

## Parallelization

The dependency declaration and recipe implementation are ordered because recipes
must refer to installed tools. Verification follows both edits.

## Verification

The plan is complete when the dependency metadata is updated, the `just` recipes are
available through `just --summary`, representative installed tools are spawnable, and
the modified plan steps have execution records.
