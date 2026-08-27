---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:8b1671b210e76ad4c162f0ce60ad9b1ede02e959216ab50258e786496855ff4d'
related: []
---

# `tui-architecture` audit: Modelo 100 2024 savings scale citation window

## What was checked

A grounding sweep over all 458 numeric registry parameters, classifying each by
whether its `legal_refs` resolve to a catalogue provision with a `corpus_ref`,
and whether the cross-check text pins any number at all.

Structural grounding is intact: zero parameters lack `legal_refs`, zero cite a
provision absent from the catalogue, zero cite a provision without a
`corpus_ref`, and zero `corpus_ref`s point at a missing file.

99 of 458 carry a `required_text` that pins no digit, so the cross-check would
pass for any year's figures. 90 are the autonomic scale tables already recorded
in `2026-08-26-tui-architecture-autonomic-scale-delegating-article-audit`. Of the
remainder, `modelo-720-asset-declaration-threshold-eur` was read against the
bundled corpus and is sound in substance -- both RGAT art. 42 bis and 42 ter
state "50.000 euros" -- so only its cross-check is weak. Two `renta-2025-ric-*`
entries are false positives of the digit filter: they pin "tres anos" and
"cinco anos", the number spelled in words.

## The finding

Modelo 100 revision 2024's savings-base scale encodes the correct top marginal
rate and cites a redaction that states a different one.

- `renta-2024-escala-estatal-base-ahorro` encodes a 0.14 top tranche and cites
  `ley-35-2006:art-66`.
- `renta-2024-escala-autonomica-base-ahorro` encodes 0.14 and cites
  `ley-35-2006:art-76`.

The `art-66` corpus text states the top tranche as "300.000,00 35.940 En
adelante 15" -- 15 percent, the state half of 30 percent. The redaction that
states 14 is `ley-35-2006:art-66-2023`, whose declared window is 2023-01-01 to
2024-12-21.

The value is correct. The citation is the defect. Those are separate claims and
only the second is made here.

## Why no repair was landed

Repointing 2024 at the `art-66-2023` / `art-76-2023` redaction was attempted
across all 41 files of the revision's savings-scale chain, and is refused by
`_check_revision_scoped_legal_windows` in
`src/cadrumo/domain/calculations/registry/_snapshot_internals.py:540`:

    legal reference 'ley-35-2006:art-66-2023' (effective_from 2023-01-01,
    effective_to 2024-12-21) does not cover revision '2024''s devengo date
    2024-12-31

Two registry contracts are in genuine conflict for this one revision:

- `aeat-calculation-grounding` requires the cited clause to state the number
  encoded. Only the 2023 redaction does.
- The revision-scoped window check requires the cited provision to be in force
  at the revision's devengo date. Only the current redaction is.

Neither available citation satisfies both, so no citation change can be correct
without an adjudication. The change was reverted and the loading state restored
in `cfc6c30469`.

## Root cause

Ley 7/2024 entered into force on 2024-12-22, nine days before the IRPF devengo
of 2024-12-31, but its savings-scale change takes effect from 2025-01-01 -- as
the catalogue's own note on `ley-35-2006:art-66` states. For fiscal year 2024
the text in force at devengo is therefore not the text that governs the year.

2024 is the only year where these diverge. 2020 through 2023 each pin the
redaction in force for that year, with zero unpinned references; 2025 correctly
uses the current redaction:

| year | pinned-redaction files | unpinned-current files | top rate |
|---|---|---|---|
| 2020 | 31 | 0 | 0.115 |
| 2021 | 32 | 0 | 0.13 |
| 2022 | 36 | 0 | 0.13 |
| 2023 | 41 | 0 | 0.14 |
| 2024 | 0 | 41 | 0.14 |
| 2025 | 0 | 45 | 0.15 |

## Remediation, for an owner

The choice is a tax-semantics ruling and is not made here. Two shapes are
available without fabricating a citation:

- Catalogue the Ley 7/2024 effect-date provision and cite it alongside the
  redaction, so the chain records why 2024 keeps the earlier scale.
- Teach the window check to compare against the provision's effect date rather
  than its in-force date, where the two differ.

Do not resolve it by relaxing either gate: each is load-bearing, and silencing
one settles the question invisibly.
