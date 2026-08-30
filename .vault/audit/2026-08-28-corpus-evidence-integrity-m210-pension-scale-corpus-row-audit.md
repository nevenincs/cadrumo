---
tags:
  - '#audit'
  - '#corpus-evidence-integrity'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c000b9ba686eeb729c99b551724a7b66bc40a6c46764c1dca26b65e98a00edd3'
related:
  - "[[2026-08-28-registry-legal-grounding-windows-m303-transitional-rate-citation-audit]]"
---

# `corpus-evidence-integrity` audit: `The bundled TRLIRNR art 25.1.b excerpt drops the pension scale first row`

## Scope

## Findings

## Recommendations

## Finding

`m210-pension-tarifa-2025` encodes the TRLIRNR art. 25.1.b scale for pensions
paid to non-residents, and its first bracket is:

```toml
lower_bound = "0"      upper_bound = "12000"
fixed_addition = "0"   marginal_rate = "0.08"
```

The bundled corpus excerpt it cites — `trlirnr-rdleg-5-2004.html#a25-1-b` —
**does not contain that row**. Its transcription of the scale reads, in full:

> Importe anual pension hasta 12.000 euros, cuota 960 euros, resto pension hasta
> 6.700 euros, tipo aplicable **30 por ciento**; importe anual pension hasta
> 18.700 euros, cuota 2.970 euros, resto pension en adelante, tipo aplicable
> **40 por ciento**.

Two rows where the statute has three. The tokens `8 por ciento` and `ocho por
ciento` do not occur anywhere in the file. This is a transcription defect in the
excerpt, not a citation choice: the catalogue entry's own `notes` state the
complete tariff — "8 percent up to 12,000 euros, 960 euros plus 30 percent over
12,000 up to 18,700, and 2,970 euros plus 40 percent above 18,700".

## The excerpt proves its own omission

No external source is needed to establish that a row is missing. The bundled text
carries the *consequence* of the 8 % row while omitting the row:

- it states cuota **960** at an importe of **12.000**, and `960 / 12.000 = 0.08`
  exactly — an accumulated cuota only a first tranche taxed at 8 % produces;
- it states cuota **2.970** at **18.700**, and `960 + 0,30 x 6.700 = 2.970`
  exactly, so the second and third rows are mutually consistent and anchored on
  that same 960.

A transcription that opens at 30 % with a pre-loaded cuota of 960 is internally
incoherent. The registry's 0.08 is right and the corpus is short a row.

## `required_text` pins the two rungs that survived

The catalogue entry requires `tipo aplicable 30 por ciento` and `tipo aplicable
40 por ciento`, and nothing for the 8 % rung. So the evidence gate is satisfied by
exactly the portion of the scale the excerpt happens to contain, and the rung the
engine actually applies to the first 12.000 euros is corroborated by nothing.

## Direction — over-payment, the unwatched side

No liability error today; the engine applies 8 %. The exposure is what the broken
evidence chain invites. "Align the parameter to its cited source" would delete the
first row and tax the first 12.000 euros at 30 %:

| annual pension | correct cuota | first row deleted | over-payment |
|---|---|---|---|
| 12.000 € | 960,00 | 3.600,00 | **+2.640,00** |
| 18.700 € | 2.970,00 | 5.610,00 | **+2.640,00** |

This is the campaign's organising question landing on its own terms: the error
direction is over-payment, and over-payment produces a valid return, no refusal,
and no signal to the taxpayer.

## The healthy direction, recorded beside the defect

The registry side **is** guarded, and a deletion would not pass silently:

- `domain/calculations/registry/tests/test_modelo_210_registry.py:479` pins the
  bracket tuple `(0, 12000, 0, 0.08)`;
- `application/calculations/tests/test_modelo_210_irnr_continuity.py:262` drives
  the engine and asserts the effective rate `0.08` with cuota `800.00`.

So the concrete over-payment above would red two tests before it shipped. What is
unguarded is the *evidence*: nothing compares the scale in the corpus against the
scale in the registry, which is why a two-row transcription of a three-row statute
has sat behind a green `required_text` check.

## Remediation — owner's decision, not taken here

Restore the missing first row to the excerpt from the BOE consolidated text, and
add a `required_text` phrase pinning the 8 % rung once the text carries it.

**I did not author the correction.** The rule against writing a corpus excerpt
from a secondary source binds even where the missing content is arithmetically
provable, and this file is already a hand-assembled "snippet de catalogo" rather
than a verbatim BOE capture — which is plausibly how the row was lost. The
replacement wording must come from BOE.

No production code, registry data, corpus text or test was changed by this audit.
