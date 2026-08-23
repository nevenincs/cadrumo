---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:862cc5ca5927d5defb55aa56688dbdffe67169e56bdd3d47380e266219b6ca5e'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]"
---



# `secure-storage-performance-hardening` audit: `S56 clean source and editable lane review`

## Scope

Audit the S56 clean-checkout test for tracked-source isolation, truthful editable-install execution, complete CommandSpec consumer parity, real help/completion behavior, forbidden artifact absence, and development-import exclusion.

## Findings

### S56 clean source and editable lane review | critical | Editable target was not processed

The initial editable lane put a target containing only a PEP 660 `.pth` and distribution metadata on `PYTHONPATH`. Python does not process `.pth` files from an ordinary `PYTHONPATH` entry, and the probe resolved `cadrumo` through the current worktree's existing editable installation. This made the lane capable of passing without using the archived install.

### S56 clean source and editable lane review | high | Projection comparisons were one-sided

The initial input set was built from schema references and compared back to those references, while MCP descriptors were only required to be a subset. A wrong same-sized result set or dropped descriptor could pass.

### S56 clean source and editable lane review | medium | Completion was declaration-only

The initial probe inspected the root completion flag but did not invoke the assembled CLI's completion surface.

## Recommendations

Run the probe with `python -S`, process only the archived editable target as a site directory, append dependencies without processing their editable hooks, and require every first-party module origin to resolve inside the archive.

Derive expected result-schema and exposable identities directly and independently from the immutable command nodes, then require exact equality from schema references, schema types, verb inputs, operator projection, and MCP descriptors.

Invoke `--show-completion bash` in both lanes and require successful AEAT completion script output.

All recommendations were implemented. The independent re-review recorded critical 0, high 0, medium 0, and low 0. Ruff, ty, diff validation, and the isolated integration proof passed during review.
