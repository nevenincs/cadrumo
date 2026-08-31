---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:02ef6b21c16e30270915993f26d25cd9bab993d46bc1efdcdeca4aabb5c25aaf'
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

## Re-verified at HEAD, with the exact figures and a sharper diagnosis

The conflict persists, and the numbers make it precise. Ley 7/2024 raised the top
state savings tranche **nine days before the IRPF devengo**, and the catalogue
tiles the two redactions across that boundary:

| entry | window | top tranche stated |
|---|---|---|
| `ley-35-2006:art-66-2023` | 2023-01-01 → **2024-12-21** | `300.000,00 35.940 En adelante **14**` |
| `ley-35-2006:art-66` | **2024-12-22** → open | `300.000,00 35.940 En adelante **15**` |

The registry's encoded values, read from the loaded snapshots, are right:

| filing year | encoded top tranche |
|---|---|
| 2023 | 0.14 |
| **2024** | **0.14** |
| 2025 | 0.15 |

So the authors treat the increase as applying **from 2025**, which is the correct
treatment: the amendment is prospective, and filing year 2024's savings scale is
the one that governed the period.

### The diagnosis is sharper than "two gates conflict"

`_check_revision_scoped_legal_windows` requires the cited provision to be in force
at the **devengo date** — 31 December for IRPF. That rule is right in general and
wrong here, because it asks *which redaction existed on one day* rather than
*which redaction governed the period*. For a scale amended prospectively in the
last days of a tax year, those differ: `art-66-2023` governed 356 days of 2024 and
`art-66` governed nine, and it is the former that determines the 2024 liability.

So the position is: the value is correct, the provision that states it is
out-of-window by ten days, and the provision in window states a different number.
No citation satisfies both gates because the gates encode two different and
individually reasonable theories of which redaction applies.

### The danger, and why this is worth keeping open rather than tidying

The tempting repair is to repoint 2024 at `art-66`, which is in window. That
citation states **15**. Nothing would then flag the mismatch, because the evidence
gate only checks that the phrase appears in the source, never that it matches the
encoded value — and the current `required_text`, `["base liquidable del ahorro",
"tipos de gravamen"]`, states no number at all.

The step after that is the real hazard: someone reconciling value to citation and
changing 2024's top tranche from 14 to 15. That is a live liability error on the
highest savings tranche, in the over-declaration direction, reached by two
individually plausible tidying edits.

**Do not repoint this citation to `art-66`.** If the window rule is to be relaxed,
it should be relaxed deliberately — for a provision that governed the filing
period rather than merely the devengo instant — and not by moving the citation to
whichever entry passes.

### Correction: the mismatch is already in the record, not a future risk

The section above says "the tempting repair is to repoint 2024 at `art-66`" and
warns against it. **It is already pointed there.**
`renta-2024-escala-estatal-base-ahorro` declares:

```toml
legal_refs = ["ley-35-2006:art-66"]
required_text = ["base liquidable del ahorro", "tipos de gravamen"]
```

`ley-35-2006:art-66` is the redaction in force from 2024-12-22, and its corpus
text states the top tranche as **"En adelante 15"**. The parameter encodes
**0.14**. So the citation already contradicts the value it is supposed to ground.

The registry had no alternative. `_check_revision_scoped_legal_windows` runs at
build and requires the cited provision to be in force at the devengo date, so
citing `art-66-2023` — the redaction that governed the period and states 14 —
would fail the build. Since the tree loads, every citation in it is in-window by
construction; this one is in-window and wrong about the number.

That makes the finding more urgent than the earlier wording implied, and the
direction of the residual risk unchanged: nothing detects the contradiction,
because the evidence gate never compares phrase to value and this `required_text`
states no number. A reviewer reconciling the two would most naturally "correct"
the value to match its cited source, changing 2024's top savings tranche from 14
to 15 — a live over-declaration on the highest tranche.

The value is right. The citation is the defect, and it is the only citation the
window rule permits. That is the conflict, stated exactly.
