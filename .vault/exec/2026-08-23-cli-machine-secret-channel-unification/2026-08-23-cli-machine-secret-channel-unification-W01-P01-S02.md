---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:c47341a331999cfee4ab9d31b7ab7e276fd6673aaa26a62fa3480910fc006507'
step_id: 'S02'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---




# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and prove aliases, defaults, order, help, strict parsing, size bounds, descriptor refusal and closure, one-shot reads, and secret-free errors for the canonical capability

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_secure_input_machine_channels.py`

## Description

- Materialize the shared Typer annotations through a real command and assert exact aliases, parameter order, defaults, flag shape, and populated help.
- Prove the canonical payload base rejects extra fields and mutation.
- Exercise absent, stdin, and descriptor selections and prove dual-channel conflict leaves the descriptor unread.
- Refuse invalid UTF-8, malformed JSON, non-object JSON, top-level and nested duplicate keys, missing fields, extra fields, and payloads above the shared bound.
- Drive stdin through a real child process and descriptors through real pipes, temporary storage, and fd 0.
- Prove negative, stdout, stderr, closed, malformed, and oversized descriptor behavior plus closure after success and every post-read refusal.
- Assert a consumed descriptor refuses a second read and no supplied secret value enters any refusal, stdout, or stderr surface.

## Outcome

The canonical transport capability is covered by twenty-two focused tests spanning declaration, selection, parsing, size enforcement, descriptor lifecycle, and redaction. Every expected contract passed without production correction.

## Notes

The tests use operating-system pipes, duplicated descriptors, temporary file descriptors, fd 0 rebinding, and an actual stdin subprocess. They do not mock or replace the production readers. Command-level subprocess behavior across the five adopters remains assigned to S13 and S14.
