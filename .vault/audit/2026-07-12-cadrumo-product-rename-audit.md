---
tags:
  - "#audit"
  - "#cadrumo-product-rename"
date: '2026-07-12'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-12-cadrumo-product-rename-adr]]"
promoted_to:
  - 'rule:cadrumo-product-authority-names'
modified: '2026-07-12'
---
# `cadrumo-product-rename` audit: `Cadrumo rename rolling formal review`

## Scope

Formal review of Phase `W01.P01` against the accepted Cadrumo research, ADR,
approved L4 plan, audit template, and execution records `S01` through `S04`.
The review tested safety, intent alignment, classification completeness,
evidence quality, cross-record consistency, and plan compliance. It reviewed
classification and execution evidence only; no production implementation was
in scope.

The phase correctly preserved the product-versus-authority distinction, kept
the hard-cut/no-migration policy explicit, treated external availability as a
non-reserving signal, and isolated Step commits in a heavily shared worktree.
All four planned Step records exist and all four Phase checkboxes are closed.

Phase `W01.P02` was subsequently reviewed against the same research, ADR, and
plan, plus records `S05` through `S08`, the live identity module and facade, its
focused contract tests, and the promoted project rule. This review covered
architecture boundaries, tuple completeness, immutability, facade/API quality,
test validity, no-alias/no-shim compliance, rule correctness, and Step evidence.

## Findings

### exec-template-hygiene | low | Completed S01-S03 records retain scaffold annotations

The first three completed Step records still contain the three instructional
HTML comment blocks emitted by the execution template. Their substantive bodies
are complete and the comments do not alter the decisions, but retaining
generator instructions in settled evidence produces avoidable vault-check noise
and makes completed records appear unfinished. `S04` correctly removed the same
annotations.

### diagnostic-dump-identity | high | S02 and S03 assign opposite owners to the wallet diagnostic setting

`S02` classifies `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR` as product-owned and requires
the rename to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`. `S03` classifies the
corresponding `aeat_wallet_diagnostic_dump_dir` setting as authority-owned and
requires retaining the AEAT name because it captures the authority's cartera
surface. These outcomes are mutually exclusive. Both records present themselves
as complete classification authorities, so downstream configuration and
persistence Steps cannot implement the phase deterministically without choosing
one and contradicting the other. The accepted ADR's referent rule does not itself
resolve the conflict: the payload is authority-derived, while the setting controls
product-selected local custody. The phase therefore has one unresolved ambiguous
public setting despite `S02` reporting zero ambiguity.

### critical-findings | critical | No critical finding identified

No evidence shows destructive worktree handling, secret disclosure, external
reservation or publication, legal-corpus mutation, compatibility-shim approval,
or another critical safety or intent failure in `W01.P01`.

### diagnostic-dump-identity-resolution | resolved | Local dump custody is product-owned

Resolved the preceding high finding by applying the referent decision already
recorded in `S02`: `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR` is a product control because
it selects a caller-provided local directory, creates that directory, and writes
Cadrumo-controlled redacted structural summaries into it. It therefore becomes
`CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR`. `S03` now agrees and names the corresponding
field `cadrumo_wallet_diagnostic_dump_dir`. AEAT cartera, Sede, wallet, URL, and
payload terminology remains authority-owned. The correction introduces no old
environment reader, directory migration, or fallback: the former override and
its directory are not read or auto-ingested.

The overlap is now deterministic: `S02` remains 102 product-owned and 49
authority-owned public variables with zero ambiguous, and `S03` has no contrary
wallet-directory classification. The completed `S03` scaffold annotations were
also removed as part of the requested resolution hygiene.

### rule-artifact-scope | medium | S08 closed against an artifact absent from its plan scope

The closed `S08` plan row still scopes delivery to
`.codex/rules/cadrumo-product-identity.md`, while the canonical promotion command
created and the Step record claims
`.vaultspec/rules/cadrumo-product-authority-names.md`. The promoted rule is valid,
registered, readable through `vaultspec-core spec rules show`, and substantively
matches the ADR. The defect is plan-to-evidence traceability: the checked Step
names an artifact that does not exist and omits the artifact that satisfied it.
The Step record explains the authority-driven relocation but does not update the
canonical plan structure, so status consumers cannot discover the delivered rule
from the closed row.

### phase-p02-high-findings | high | No high-severity Phase W01.P02 finding identified

The identity tuple covers every canonical value required by the ADR, depends only
on standard-library primitives, exposes one shared object through the core facade,
and contains no alias, fallback, migration, or former-package dependency. The five
focused tests import production objects directly, exercise actual immutability and
enum refusal, pin facade object identity and the exact public export set, and use no
mocking or test shortcut. Re-execution passed all five tests and the focused Ruff
and formatting gates.

### phase-p02-critical-findings | critical | No critical Phase W01.P02 finding identified

No review evidence shows unsafe state mutation, architecture inversion, secret or
authority-evidence exposure, compatibility machinery, a tautological calculation
test, or another critical failure in the phase.

### rule-artifact-scope-resolution | resolved | Canonical plan now names the promoted rule

Resolved the preceding medium finding through
`vaultspec-core vault plan step edit`. The closed `S08` row now scopes the
delivered `.vaultspec/rules/cadrumo-product-authority-names.md` artifact. The
registered rule was not moved or duplicated.

### s11-missed-i18n-resource-anchors | high | Locale loading retained two former product package anchors

The completed S11 resource-boundary change covered `core.resources`, but
`src/cadrumo/core/i18n/_render.py` independently called
`importlib.resources.files("aeat")` in both the python-i18n load path and direct
YAML catalogue reader. After removal of the former import root, either fallback
translation or direct locale loading could fail despite the primary bundled-data
boundary being correct. These are product package anchors, not references to the
external authority.

### s11-missed-i18n-resource-anchors-resolution | resolved | Locale loading consumes canonical Cadrumo identity

Resolved both anchors through `PRODUCT_IDENTITY.python_package`, imported from
the layer-safe core identity leaf. There is no literal former package name,
fallback, alias, or duplicate product constant. Authority-owned locale content
and AEAT terminology remain unchanged. Focused real-catalogue tests and direct
adapter import smoke cover the corrected loading path.

## Recommendations

1. Keep later configuration and persistence implementation blocked on the wallet diagnostic setting until the principal engineer records one referent decision. Prefer classifying the environment variable by what it controls: if it chooses Cadrumo's local output custody, rename the control to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` while retaining AEAT terminology in the captured payload and description. If authority identity is intended to govern the setting name, explicitly amend `S02` and its zero-ambiguity count instead.
2. Add a review gate that compares overlapping environment-variable and persistence matrices before `W02.P04`, so every setting named in both records has one disposition.
3. Remove scaffold annotations from completed `S01` through `S03` records in a separately owned documentation-hygiene change; do not mix that cleanup into this review commit.
4. Preserve the existing release blockers from `S04`: availability observations are not reservations, and Spanish/EU trademark clearance remains outstanding.
5. Do not treat `W01.P01` as contradiction-free until the high-severity finding is resolved, even though its four administrative plan checkboxes are closed.
6. Reconcile the closed `S08` Step scope through the canonical plan CLI so it names `.vaultspec/rules/cadrumo-product-authority-names.md`; do not move or duplicate the registered rule merely to satisfy the stale provisional path.
7. Treat the preceding `diagnostic-dump-identity` high finding and recommendations 1 and 5 as superseded by `diagnostic-dump-identity-resolution`; retain them as rolling review history rather than reopening the resolved issue.
8. Keep the Cadrumo identity module import-light and consume `PRODUCT_IDENTITY` through the facade in later Waves instead of redeclaring tuple values or introducing aliases.
