---
tags:
  - '#research'
  - '#semantic-cluster-hardening'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-19-code-duplication-sweep-research]]"
  - "[[2026-05-31-core-authority-research]]"
---



# `semantic-cluster-hardening` research: `RAG-driven semantic functionality-cluster audit (7th axis)`

This worktree is in a standardisation-and-hardening phase: ~1736 Python
modules under `src/aeat` are being cross-referenced against the accepted
ADRs to guarantee that every module (a) enrols into the same canonical base
definitions, centralised pydantic config, typed-constant enums, and the
central exception hierarchy; (b) is free of shims, re-exports, and
duplication; and (c) — crucially — that domain packages do **not** contain
functionality redefinitions of capability that already lives elsewhere.

The blocker this research addresses: text search (`rg`/grep) cannot surface
*semantically* identical functionality that is *lexically* different.
Two modules that both quantise a `Decimal` to euro cents, or both validate a
tax identifier, will never co-occur in a grep result. The prior duplication
sweep found this class of overlap only through expensive manual reading.
This research designs a **repeatable, semantic-search-driven audit axis**
(a 7th axis bolted onto the existing swarm-audit cadence) so the overlap
surface can be re-discovered on cadence rather than re-read by hand, and
remediated in waves.

## Prior art and current state (this campaign is a continuation)

Two prior efforts cover much of the conceptual ground, but their findings are
**unverified leads, not authority** — every lead is re-confirmed against
today's tree with the tooling; no prior conclusion is inherited as settled:

- The code-duplication-sweep effort (2026-05-19) produced a ~307KB manual
  catalogue of 23 duplicated symbols plus extensive prose on conceptual
  overlaps: `IVA` vs `VAT`, `Renta` vs `Rental`, `Filing`/`Modelo`/
  `Declaración`, `Borrador`/`Draft`/`Snapshot`, `Justificante`/`Invoice`/
  `Receipt`, `Catalogue` proliferation, `Fact`/`Observation`/`Record`/
  `Snapshot`/`Revision` state-entity splitting, and `Verify`/`Validate`/
  `Check`/`Audit` verb overlap. This is the wave-4 (domain-redefinition)
  surface. It must be **re-confirmed against today's tree before any
  action**, and any claimed resolution status proven fresh, never assumed.
- The core-authority effort (2026-05-31) is the master spine. Its resolution
  tracker *claims* the enrollment waves are substantially complete (claims to
  re-verify, not facts to trust):
  `STRICT_FROZEN_CONFIG` migration landed 84 of 87 sites (3 documented
  bespoke exclusions); the `PROMOTE-001` substitutability machinery exists in
  `src/aeat/diagnostics/_identity_placement.py` as `PROMOTE001_PROTECT_LIST`;
  name collisions (`ProfileFactValue` → `UserProfileFactValue`) are resolved;
  and the substitutability pre-filter is already mandated in the
  swarm-audit-cadence rule.

### The baseline is stale — prior correctness cannot be assumed

This is a **re-audit**, not a status reconciliation, for two reasons:

- **Prior research may be wrong.** It was largely manual; the swarm-audit
  cadence itself documents a self-reported ~30% structural-incompleteness
  rate and a recurring ~14-item discovery-per-pass pattern. We re-confirm
  every lead with the tooling; we do not inherit conclusions.
- **The tree has moved enormously since the 2026-05-19 baseline.** As of
  2026-06-01: **408 Python modules added**, **1305 modified**, ~83 currently
  uncommitted under `src/aeat`. The added modules are **entirely unaudited**
  and may bypass the canonical base definitions, pydantic config, typed
  constants, and exception hierarchy. This **added-file delta is the priority
  surface**, ahead of re-checking old findings.

RAG is the central instrument of this re-audit and, being a newly adopted
tool, is itself under evaluation as we exercise it. The genuinely-open value
is the **systematic semantic-cluster method**, a **delta-audit of the 408
added / 1305 modified modules** for canonical-convention enrollment, and
fresh re-confirmation of prior leads — every conclusion proven, not trusted.

## Findings

### F1 — The 7th audit axis: semantic functionality-cluster overlap

Proposed axis definition (to be ratified in the ADR), extending the existing
six axes of the swarm-audit cadence:

> **Axis 7 — Semantic functionality-cluster overlap & canonical-definition
> enrollment.** For a target functional concept, surface every site that
> implements it (via semantic search, not symbol match), then verify whether
> the sites are a true duplication cluster or a constraint-shape-divergent
> set. Where a canonical implementation exists, confirm consumers import it
> rather than re-deriving it. Where none exists but ≥2 substitutable sites
> do, nominate a canonical home.

This axis is **discovery + enrollment**, complementing the six existing axes
which are structural/boundary-oriented. It is a depth axis (Sonnet-class),
not a breadth axis, because each cluster needs substitutability judgement.

### F2 — RAG calibration (method contract)

Live calibration against the resident service (port 8766, freshly rebuilt:
~4061 vault docs, ~109731 code chunks) establishes the method's envelope:

- **Strong** on functional-concept queries: "Decimal money rounding to
  cents" → 0.97, "validation error for boundary input" → 0.97, "load/merge
  TOML registry fragments" → 0.95. Real multi-package clusters land at
  **≥0.50**.
- **Weak** on domain-jargon queries: "normalize NIF/NIE", "parse tax period
  code" return tangential or test hits and miss the authoritative single
  site. RAG is a *clustering* tool, not a symbol locator.
- **Noise**: `locales/{en,es,ca,hu}.yml` and test docstrings crowd ~20% of
  rows and must be filtered post-hoc.
- **Contract**: query by functional concept (not domain token); `--port 8766`
  always; `--max-results 20`; score floor ~0.50; RAG for *discovery*, then
  `rg` for *verification* of the exact sites; treat the same string in four
  locales as one signal. This is the standard procedure every Axis-7 brief
  must embed.

### F3 — Confirmed live defects (open surface)

Verified this session against the current tree:

- **Decimal-to-cents rounding is genuinely triplicated.** Identical
  `value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)` logic in
  `domain/fincas/_rounding.py`, `domain/profile/inventory/__init__.py`, and
  `domain/profile/assets/__init__.py`. Substitutable (same constraint shape).
  Candidate canonical home: a core money/Decimal primitive. (Wave 1.)
- **`DomainError` is defined-and-unused.** `domain/_errors.py` declares
  `DomainError(AeatError, ValueError)` intended as a mid-layer coordination
  base, but all 23 domain subpackages inherit their package error base
  directly from `AeatError`. **DECIDED: delete** as dead code. Safeguard:
  commit surrounding/related work first, then remove `DomainError` in its own
  clearly-messaged commit so any loss is git-traceable. (Wave 3.)
- **Error-module naming drift.** 19 packages use `_errors.py`, 4 use
  `errors.py` (`renta`, `iva`, `normatives`, `manuals`). Trivial
  standardisation. (Wave 3.)
- **`exception-restructure` ADR (2026-05-09) is a blank template.** Wave 3
  needs a real exception-hierarchy decision document; this is a documentation
  gap, not just code drift.
- **`domain` taxonomy conflation (wave 4 framing).** Three disjoint meanings
  share the token: the business-domain package layer (`aeat.domain.*`);
  `tax_domain`, a free-form `str` classifier on `ModeloDefinition` with no
  closed value-set and no canonical registry of valid values; and
  `Subdomain`, a `StrEnum` in `domain/portals` that actually enumerates AEAT
  website hostnames (`SEDE`, `WWW1`, `CLAVE_GOB`) and is mis-named. None is a
  single module that conflates "the set of domains" with "a domain's logic",
  but the vocabulary collision is real and grep-invisible. **DECIDED**:
  `tax_domain` is promoted to a closed typed-constant (core `StrEnum`) with
  registry hydration at the boundary — strong-typing/centralisation mandate,
  enrol to the same convention every other closed axis already follows.

### F4 — Tooling decision: extend, do not build

The swarm-audit cadence is convention-only (documented rule + 70+ manual
audit docs, no dispatch harness). Per the agreed direction, Axis 7 is added
to that documented cadence rather than shipped as a new committed tool. This
respects source-hygiene (no audit machinery inside `src/aeat`) and reuses the
established brief shape, the substitutability pre-filter, and the
`.vault/audit/` output convention.

### F5 — Execution shape (audit AND remediate, in waves)

The user chose audit-and-remediate in the same campaign. A **delta-audit gate
runs first and feeds every wave**: enumerate the 408 added / 1305 modified
modules since 2026-05-19 and run the Axis-7 RAG sweep over that delta as the
priority surface; prior-lead re-confirmation is folded in per wave, never
trusted up front.

1. **Wave 1 — duplication clusters.** RAG-discover functional clusters over
   the delta first, then the wider tree -> substitutability-verify ->
   consolidate to a canonical home -> roundtrip/behaviour test -> atomic
   explicit-path commit. Seed: F3 decimal rounding (re-verified live).
2. **Wave 2 — base-definition & pydantic enrollment.** Re-verify (do NOT
   trust) the claimed `STRICT_FROZEN_CONFIG` / typed-alias / enum enrollment
   completeness against the current tree, with the added modules as the prime
   suspects; close every straggler the delta introduced.
3. **Wave 3 — exception consolidation.** Fill the blank `exception-restructure`
   ADR, **delete** `DomainError` (safeguarded per F3), normalise `errors.py`
   naming, re-verify all 23 bases still root at `AeatError`.
4. **Wave 4 — domain redefinition + taxonomy.** Re-confirm the prior
   duplication-sweep conceptual leads against current state; disambiguate the
   `domain` vocabulary (`Subdomain` rename; `tax_domain` -> closed `StrEnum`
   typed-constant + registry hydration, per the decision in F3).

Each remediation Step is one symbol/cluster = one atomic commit with a clean
`pytest --collect-only` immediately before commit, tagged `relocation:<symbol>`
where a canonical-site move occurs, per the atomic-relocation mandate.

### F6 — Constraints and risks

- **Shared worktree, live concurrent epics.** Every remediation Step must
  `git diff -- <file>` before its first edit and abort on non-authored WIP;
  commits are explicit-path only; no destructive git (no stash/reset/
  checkout/clean/rebase). Audit (read-only) Steps are collision-safe.
- **False-positive risk.** The `PROMOTE-001` pass observed a 96%
  false-positive rate before the substitutability pre-filter; Axis 7 MUST
  apply it — a "duplicate" is actionable only if the canonical site's
  constraint shape is a superset of the candidate's.
- **RAG blind spots.** Domain-jargon concepts evade RAG; pair every semantic
  sweep with a targeted `rg` pass for known canonical symbols so single-site
  authorities are not mistaken for "no cluster".

## Open questions for the ADR

DECIDED (locked by the user, 2026-06-01):

- **`DomainError`**: delete as dead code; safeguard by committing surrounding
  work first, then removing it in its own clearly-messaged commit.
- **`tax_domain`**: promote to a closed `StrEnum` typed-constant in `core`
  with registry hydration at the boundary (TOML stays free-form, loader
  hydrates). Enrol to the same convention every other closed axis follows.

STILL OPEN for the ADR:

1. Canonical home for shared numeric primitives (e.g. cents rounding): a new
   `core` money/Decimal primitive module, or an existing core util?
2. Does Axis 7 become a standing cadence trigger, or a one-off campaign axis
   retired at campaign close?
3. Delta-audit boundary: anchor the "since last audit" delta on the
   2026-05-19 commit, or on the most recent per-area audit doc per subpackage?

## Recommended next step

Proceed to `vaultspec-adr` to ratify Axis 7, the RAG method contract (F2),
the wave structure (F5), and decisions on the four open questions, then plan
and execute wave 1.
