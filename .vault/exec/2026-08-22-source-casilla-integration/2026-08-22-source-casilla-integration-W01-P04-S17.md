---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6a3abc37f735ce8ceee904037918113128ad24a99a7fc1c55351bcc844b6282f'
step_id: 'S17'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# define the canonical machine-readable census manifest

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`

## Description

- Establish the versioned canonical source-connectivity census manifest.
- Keep generated capability and registry facts at their existing authoritative homes.
- Reserve manifest entries for reviewed decisions addressed by stable evidence locators.

## Outcome

The project now has one machine-readable canonical home for connectivity dispositions without copying repository, selector, resolver, or casilla schemas into another authority.

## Notes

The TOML parsed exactly as schema version 1 with the canonical census identity. Reviewed entries are added by the following bounded steps.
