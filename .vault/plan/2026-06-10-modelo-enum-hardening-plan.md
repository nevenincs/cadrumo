---
tags:
  - '#plan'
  - '#modelo-enum-hardening'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-modelo-enum-hardening-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace modelo-enum-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `modelo-enum-hardening` `Modelo enum hardening and centralisation follow-ups` plan

### Phase `P01` - Discovery and decisions

Quantify the value-vs-member inconsistency and investigate modelo:str max_length=8 fields before any change


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Quantify Modelo member vs .value usage and record the decision to prefer the enum member where StrEnum semantics suffice; `src/aeat`.
- [ ] `P01.S02` - Investigate every modelo:str max_length=8 field to determine which carry pure modelo codes versus composite/loose forms; `src/aeat/**/_schema.py, _models.py, payloads`.

### Phase `P02` - Literal rollout

Convert Literal code-string fields to Literal Modelo-member fields

- [ ] `P02.S03` - Convert Literal code-string fields to Literal[Modelo.M<code>] and update the CI gate exclusions; `src/aeat/adapters/inbound/borrador/_schema.py, src/aeat/adapters/outbound/aeat/sede/_schema.py, src/aeat/domain/calculations/registry/_ledger_bindings.py, src/aeat/domain/renta/_ledger_expenses.py, src/aeat/core/tests/test_modelo_string_usage.py`.

### Phase `P03` - Value vs member standardisation

Adopt one convention: enum member where StrEnum suffices, .value only where a plain str is contractually required

- [ ] `P03.S04` - Standardise to the enum member in comparison/membership/dict-key/str-field positions; `reserve .value for genuine plain-str contracts; `src/aeat (files touched in the modelo-enum sweep)`.

### Phase `P04` - Registry-resolver rollout for rates

Route amortisation 3pct and REBECA 50pct through the registry-backed resolver with legal grounding

- [ ] `P04.S05` - Route AMORTIZACION_INMUEBLE_RATE through a registry parameter and _resolve_ fallback with legal grounding and a grounding test; `src/aeat/domain/fincas/_amortization_ledger.py, src/aeat/_data/registry/aeat/..., legal catalogue`.
- [ ] `P04.S06` - Route REBECA_MARITIME_EXEMPTION_FRACTION through a registry parameter and _resolve_ fallback with legal grounding and a grounding test; `src/aeat/domain/renta/_maritime_exemption.py, src/aeat/_data/registry/aeat/..., legal catalogue`.

### Phase `P05` - Typed modelo fields

Retype confirmed-pure modelo str fields to Modelo where safe; document the rest

- [ ] `P05.S07` - Retype the confirmed-pure modelo:str fields to Modelo where serialization and validation stay sound; `document each field left as str; `src/aeat (modelo:str fields identified in P01.S02)`.

### Phase `P06` - CI gate robustness

Reduce false-positive reliance in the modelo-string gate

- [ ] `P06.S08` - Refactor the period digit-membership false positive so it no longer reads as a modelo code; keep the article-number allowlist with its reason; `src/aeat/application/modelo/_workflow_gate.py, src/aeat/core/tests/test_modelo_string_usage.py`.

## Description

This plan tracks the follow-on hardening from the in-session Modelo-enum and
regulatory-value centralisation campaign (commits `cae8e870a` through
`83b7b4fee` on `chore/eliminate-shims`). That campaign introduced the canonical
`Modelo` StrEnum, swept roughly sixty production identifier sites from bare
code strings to enum members, added the retired `M037` non-registry member, and
committed an AST CI gate (`test_modelo_string_usage.py`). This plan closes the
deferred and newly-discovered items: the Literal-annotation rollout, the
value-versus-member inconsistency the sweep introduced (81 `.value` against 67
bare-member uses), the registry-resolver rollout for the amortisation and REBECA
rate constants, a per-field investigation of `modelo: str` fields declared with
`max_length=8`, and a CI-gate false-positive cleanup. No new domain behaviour is
introduced; every Step is behaviour-preserving or registry-grounded and gated by
tests.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorising documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

P01 (discovery and decisions) runs first and gates P03 and P05, both of which
depend on its findings (the value-versus-member convention and the pure-versus-
composite field classification). P02 (Literal rollout), P04 (registry-resolver
rollout), and P06 (gate robustness) share no hard interdependency and may run in
parallel once P01 has settled. P04.S05 and P04.S06 are independent of each other.
P03.S04 re-touches files already converted in the original sweep, so it must land
after P02.S03 to avoid editing the Literal sites in two passes.

## Verification

The plan is complete when every Step is closed. Mission success criteria:

1. `test_modelo_string_usage.py` stays green with an allowlist that is the same
   size or smaller (P06 should remove the digit-membership false positive).
2. The Literal sites compile and pass strict-pydantic validation as
   `Literal[Modelo.M...]`, and the CI gate's Literal-default exclusion still
   accounts for them.
3. A single documented value-versus-member convention is applied, with no file
   mixing `Modelo.M###` and `Modelo.M###.value` for the same kind of use.
4. The amortisation and REBECA rates resolve from the registry with passing
   grounding tests, and the leaf constants remain as documented fallbacks.
5. `uv run --no-sync pytest --collect-only -q` is clean and the touched test
   surfaces are green, excluding the pre-existing peer-WIP IVA-303 failures.
6. Every `modelo: str` field is either retyped to `Modelo` or carries a one-line
   note explaining why it stays `str`.
