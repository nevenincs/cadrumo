---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
---



# `schema-hardening-m184-standardization` Code Review

M184STD-001 | INFO | Mechanical split commit preserves loader semantics

The split removed `184.toml`, added `manifest.toml`, and placed the single
`2015-y-siguientes` revision into generic fragment-directory form. The
`7e3622864` layout commit reconstructs the pre-split `184.toml` source exactly,
and no loader, schema, or validator code changed in the M184 layout slice.

M184STD-002 | INFO | Verification covers the affected registry and row surfaces

Focused coverage passed for Modelo 184 and loader directory-mode behavior. The
broader gate also passed committed registry loading, referential integrity,
detail-record row builders, detail-record modelo coverage, row-set assembly,
and detail-record round-trip tests.

M184STD-003 | INFO | External review caught later cross-commit semantic drift

The `vaultspec-code-reviewer` pass correctly flagged that current HEAD no
longer reconstructs the pre-split `184.toml` byte-for-byte because later
cross-campaign commit `13f5e39db` changed the M184 `declaracion_pdf`
extraction profile. That change is outside the mechanical layout split and was
not reverted here. The M184 standardization audit therefore distinguishes the
exact mechanical split commit from the current post-split semantic corpus.

M184STD-004 | INFO | Current HEAD verification includes the later profile change

After the reviewer finding, the current HEAD gate was rerun with the later
profile change included. The combined M184 registry, loader, referential
integrity, detail-record, row-set, and parser-boundary surface passed with 256
tests.

M184STD-005 | INFO | Next standardization target is Modelo 193

After the M184 split, `193.toml` is the largest remaining root-level
single-file modelo at 472 lines. It should be the next mechanical registry
layout standardization slice.
