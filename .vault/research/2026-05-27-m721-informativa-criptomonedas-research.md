---
tags:
  - '#research'
  - '#m721-informativa-criptomonedas'
date: '2026-05-27'
modified: '2026-05-27'
related: []
---


# `m721-informativa-criptomonedas` research: registry gap triage

Eva round-9 persona exercise surfaced a SHOW-STOPPER: Modelo 721
(Declaración informativa sobre monedas virtuales situadas en el extranjero)
is entirely absent from the registry.

## Confirmed absence

`src/aeat/_data/registry/aeat/modelos/` contains modelos: 036, 100, 111,
115, 123, 130, 131, 180, 184, 190, 193, 200, 202, 232, 303, 309, 322, 347,
349, 353, 360, 369, 390, 720, 840. No `721/` directory exists. No TOML
files in the codebase reference `"721"` as a modelo identifier, `Ley 11/2021`
article refs, or `Orden HFP/887/2023` in any file. The legal authority for
M721 has no registry footprint at all.

## Legal authority

M721 was introduced by Ley 11/2021, de 9 de julio, de medidas de prevención
y lucha contra el fraude fiscal, specifically Disposición Adicional Décima
which created the obligation to declare monedas virtuales held abroad. The
form itself is regulated by Orden HFP/887/2023, de 26 de julio, which
approved the model and its electronic submission procedure (BOE núm. 180,
28-VII-2023).

Key legal references for registry authoring:
- `ley-11-2021:da-10` — obligation to declare virtual currencies abroad
- `orden-hfp-887-2023:art-1` — approved Modelo 721 form
- `orden-hfp-887-2023:art-2` — submission procedure
- `orden-hfp-887-2023:art-3` — thresholds (>50.000 EUR aggregate value)
- `rd-1065-2007:art-42-quater` — reglamento base for informative declarations

## Applicable revision

M721 is annual (cadencia anual), period type `0A` (same as M720).
The first obligation year was fiscal year 2022 (first filing in 2023).
The applicable revision anchor: `2023-y-siguientes` (Orden HFP/887/2023
applies from filing year 2022 onwards with no subsequent amendment through
2025).

## Casilla outline (minimal)

M721 follows M720's informative structure but for virtual currencies abroad.
Approximate section structure from the official form (BOE A-2023-17052):

- Section A — Identification data (NIF, denomination)
- Section B — Virtual currencies held abroad by third-party custodians
  (exchange/wallet provider name, ISIN-equivalent token identifier,
  country, quantity units, value in EUR at 31 December)
- Section C — Virtual currencies held abroad without third-party custody
  (self-custody wallets: wallet type, value in EUR)
- Section D — Virtual currencies acquired/transmitted during the year
  held abroad

Casilla count is modest (~30-40 per declaration line) but each section
can have multiple lines (one per token per custodian).

## Decision: registry-stub-with-explicit-refusal (recommended)

**Registry-authoring full** would be correct long-term but is HEAVY
(comparable to M720 authoring: manifest + revision TOML + casilla set +
completeness manifest + section declarations). Estimating 3-4 days of
TOML authoring with no existing formula dependencies (pure informative,
no computed casillas). No formula engine required — M721 is purely
declarative/informative with no tax liability computation.

**Registry-stub-with-explicit-refusal** (recommended for now) means:
- Author `src/aeat/_data/registry/aeat/modelos/721/manifest.toml` with
  correct `id`, `title`, `tax_domain = "informative"`, `cadence = "annual"`,
  `jurisdiction = "ES-AEAT"`, and the four legal_refs above.
- Author `src/aeat/_data/registry/aeat/modelos/721/revisions/2023-y-siguientes/revision.toml`
  with a minimal revision entry and `status = "stub"` or equivalent
  registry sentinel.
- Ensure the CLI surfaces a clear `"Modelo 721 is not yet fully supported;
  registry stub only"` refusal rather than a silent crash or misleading
  empty result — same pattern as `reserved` providers in `aeat config auth`.

This closes the SHOW-STOPPER (CLI no longer crashes or silently accepts
M721 input it cannot handle) without requiring the full casilla inventory.
Full casilla authoring can be a follow-on step (MEDIUM, ~2 days).

## Comparison with M720

M720 manifest exists with `tax_domain = "informative"`, `cadence = "annual"`,
period_selector `year_from = 2012`. M721 can mirror this structure exactly
with different legal_refs. M720's single revision `2013-y-siguientes` is
the structural template.

## Size estimate

**SMALL** for stub: manifest + revision shell + CLI refusal guard (1 day).
**MEDIUM** for full casilla inventory: ~30-40 casillas × section structure
(2-3 days, no formula work required).

## Recommended next step

Author S-series step: "M721 registry stub — manifest + revision shell +
CLI refusal guard". Coder authoring the TOML needs the Orden HFP/887/2023
form PDF for casilla labels/numbers. No formula engine involvement.
