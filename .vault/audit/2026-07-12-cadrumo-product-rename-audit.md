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

Phase `W02.P03` was then reviewed across commits `8d4cd1efce`, `efa162e73e`,
`106d044761`, `68c5f9a659`, `045979faae`, `15ce4bc642`, `402c36fa58`,
`a6171efec3`, and `f6a0e3c65c`, together with records `S09` through `S16`.
Read-only checks covered tree cardinality and rename detection, old-root import
residue, live package/resource imports, registry TOML parsing, authority path
preservation, error-registry key cardinality, ignored collision debris, and
commit/record claims.

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

### relocated-test-contract | high | A committed test still requires the forbidden former import root

`src/cadrumo/tests/test_console_script_imports.py` still launches a fresh
subprocess with `python -c "import aeat"` and requires exit code zero. The old
root is correctly absent and a direct subprocess check returns nonzero, so this
committed test now asserts the opposite of the accepted hard cut and the Phase
verification contract. Its in-process body imports `cadrumo`, while its name,
docstring, subprocess body, and failure message still describe `aeat`, leaving
the test internally contradictory. This directly contradicts `S10`'s claim of
zero former-root `__import__` or dynamic import targets and means the relocated
test surface is not valid even though its static syntax checks passed.

The same residue class appears in
`test_loader_cache_isolation.py`, which writes an executable scratch conftest
containing `from aeat.conftest import ...`. That spawned proof cannot run after
the hard cut. These are executable test strings, not historical prose or AEAT
authority references.

### shared-wip-commit-provenance | high | The root-move commit absorbed externally owned untracked source work

The `S01` ledger classified all other baseline dirty and untracked paths as
externally owned, but `8d4cd1efce` committed the complete dirty tree during the
move. Besides the Step record, the commit added fifteen source/data files that
were not tracked at its parent, including modelo registry fragments, production
modules, and tests from concurrent features. It also recorded nine parent-side
deletions as new target-side additions or deletions according to then-current
worktree state. The content was carried rather than demonstrably discarded, but
the rename commit became the first Git owner of unrelated WIP. This weakens
rollback, blame, and explicit-path ownership guarantees and makes the statement
that every non-S01 baseline path remained externally owned operationally false.

Tree accounting itself reconciles: the parent had 21,677 tracked `src/aeat`
members, the move commit has 21,686 `src/cadrumo` members, and rename detection
reports 21,668 renames, nine deletions, and sixteen additions including the Step
record. No additional collision or missing-tree evidence was found, but the
commit does not provide an independent byte manifest for the dirty/untracked
inputs it absorbed.

### stale-import-guidance | medium | Public examples and a runtime diagnostic still name the removed root

Several relocated public package docstrings still show executable examples such
as `from aeat.adapters.outbound.llm`, `from aeat.adapters.inbound.sanitizer`,
`from aeat.domain.deadlines`, and `from aeat.domain.manuals`. More seriously,
the cross-domain snapshot validator emits an actionable failure telling a
developer to `import aeat.domain.renta`. These are product import instructions,
not authority semantics. `S13` says it retargeted public-facade examples and
qualified module references, so the remaining guidance is both user-breaking
and contrary to the closed record, although it does not restore an executable
alias by itself.

### relocated-bytecode-debris | low | Twenty-four ignored collision artifacts remain under the source root

The move preserved 24 bytecode collisions as `*.pyc.relocated-aeat` files under
`src/cadrumo/**/__pycache__`, totalling 194,225 bytes. The files are ignored by
the existing `__pycache__/` rule, are not tracked, and their suffix prevents
normal Python bytecode loading, so they are not a compatibility shim or current
runtime import path. They nevertheless retain former-product implementation
bytes inside the source tree, add ambiguity to forensic and packaging scans,
and should not be treated as a durable rename artifact.

### relocated-bytecode-debris-resolution | resolved | Ignored collision artifacts removed

Immediately before cleanup, 23 remaining `*.pyc.relocated-aeat` files totalling
185,188 bytes were found under `src/cadrumo`; one of the 24 audit-time files had
already disappeared as ignored cache state changed. Every resolved path was
verified to remain inside the workspace, then removed individually with
non-recursive literal-path operations. A complete follow-up scan found zero
remaining collision artifacts. No tracked source or ordinary Python bytecode was
deleted.

### phase-p03-critical-findings | critical | No critical Phase W02.P03 finding identified

The review found no evidence that official AEAT corpus bytes, registry taxonomy,
URLs, hashes, or legal evidence were rebranded. All 16,273 authority registry
TOML files parse, no `registry/cadrumo` taxonomy exists, live Cadrumo and locale
imports work, the former package import fails without a shim, and the primary
packaged-data anchor resolves to `cadrumo/_data`. The findings above are serious
delivery and provenance defects but do not establish irreversible data loss,
authority-evidence corruption, or a critical safety breach.

### relocated-test-contract-resolution | resolved | Executable tests enforce the Cadrumo hard cut

Resolved the preceding high finding by making the cold-start contract explicit
on both sides of the rename. The console import gate now requires real in-process
and fresh-process `cadrumo` imports to succeed, while a separate fresh process
must fail to import the retired `aeat` product root. The registry cache-isolation
proof now imports the real session fixture from `cadrumo.conftest`, allowing its
two spawned pytest sessions to exercise the canonical package without a shim.

The cohesive AST import scanner now describes, names, and reports the executable
`cadrumo.*` namespace it already resolves, and its path-based ratchet keys use the
actual `cadrumo/` source root. Focused tests execute real imports, subprocesses,
and pytest sessions without mocks, patches, skips, or compatibility aliases.
Authority-owned AEAT registry taxonomy, cache filenames, environment controls,
and associated historical explanations remain unchanged.

### stale-import-guidance-resolution | resolution-in-progress | Clean production guidance now names Cadrumo

Retargeted 1,670 leading product-root references across 322 previously clean
production Python files. The rewrite was token-aware and limited to docstrings,
comments, and four actionable diagnostic strings: it changes only qualified
product modules from `aeat.` to `cadrumo.`. Nested authority paths therefore
remain explicit, for example `aeat.adapters.outbound.aeat` becomes
`cadrumo.adapters.outbound.aeat`, while AEAT URLs and prose, registry taxonomy,
environment/configuration keys, translation keys, and persisted
namespace/schema/actor strings remain unchanged.

Post-change classification found zero stale product-root documentation tokens
in the owned surface. Representative public imports and the corrected
cross-domain snapshot action execute against Cadrumo directly. Compilation
completed, focused Ruff E/F checks passed, and the repository-wide formatting
check reported only pre-existing formatter drift.

The original finding cannot yet be marked fully resolved because seven
production files were already under concurrent modification and were excluded
from this commit rather than overwritten. Those paths retain nine stale
documentation tokens: `application/workflow/_events.py`,
`domain/modelos/_participation_index.py`, `domain/modelos/_repository.py`,
`domain/modelos/_verification_repository.py`, and
`domain/portals/_registry.py` contain the remaining occurrences; the other two
excluded paths contain none. Their current owners must retarget those nine
tokens or release the paths for a separate follow-up before this rolling
finding is closed.

### shared-wip-commit-provenance-resolution | resolved | User authorised overlap preservation and cross-commit

The user explicitly directed the campaign to remain in this worktree, work
through the overlaps, and cross-commit them where needed. Under that authority,
S09 preserved the current bytes and history state of the overlapping package
tree while moving it atomically; it did not discard, reset, restore, or overwrite
the concurrent work.

The seven baseline-untracked source/data paths first brought under version
control by the move were:

- `_data/registry/aeat/modelos/100/revisions/2025/bindings/0077-renta-2025-profile-has-economic-activity.toml`
- `application/modelo/tests/test_work_plazo_m100_campaign.py`
- `core/tests/test_prorrata_register_core_authority.py`
- `domain/iva/_m303_settlement.py`
- `domain/iva/tests/test_m303_settlement.py`
- `entrypoints/cli/tests/test_modelo_200_stored_calculation_drift_cli.py`
- `entrypoints/cli/tests/test_s423_selected_language_cli.py`

The other first-seen target members were the already-authorised Cadrumo identity
files and the S09 execution record. This resolution does not claim feature
authorship for the seven paths; their originating feature provenance remains
external to the rename, while `8d4cd1efce` is intentionally their first Git
container because the user authorised the cross-commit. Rollback must therefore
preserve or separately extract those paths rather than reverting the tree move
as though it were rename-only.

### stale-import-guidance-final-resolution | resolved | Concurrent production guidance now names Cadrumo

Completed the stale-guidance remediation in the five production files excluded
from the initial clean-file commit. Live whole-file inspection found 21 active
qualified product-root references in docstrings and comments, correcting the
earlier rolling entry's count of nine. All 21 now use `cadrumo.*`: four workflow
event references, two participation-index storage references, six work-unit
repository references, six verification-repository references, and three portal
registry references.

The five files' full concurrent contents were preserved and cross-committed under
the user's explicit overlap authorization. Runtime persisted namespace values,
legacy registry-consumer matching, AEAT authority taxonomy, and authority prose
were not changed. Targeted residue classification now reports zero active
product-root documentation references in these files; the remaining qualified
`aeat.*` values are executable compatibility data intentionally outside this
documentation-only resolution.

### phase-p03-closure-verification | resolved | High and medium findings are closed at current HEAD

Re-review after `32df6f950f`, `8443c29d04`, `39c3e9ef05`,
`85498e6ab0`, and `93b3cc09e4` confirms closure of both high findings
and the medium guidance finding. The package import contract now executes three
real behaviors: in-process Cadrumo import, fresh-process Cadrumo import, and
fresh-process refusal of the retired `aeat` root. All three passed. The registry
cache-isolation file now writes `from cadrumo.conftest ...`; its ten focused
purge/isolation tests passed through real spawned pytest sessions.

The overlap-provenance entry records the user's explicit authority to preserve
and cross-commit the seven genuinely baseline-untracked feature files, while
distinguishing the identity files and Step record from that external feature
provenance. Targeted residue checks found no old-root import instruction in the
production files named by either stale-guidance remediation. No compatibility
package, alias, or fallback was introduced.

### relocated-bytecode-debris-recheck | low | One ignored collision artifact remains

The prior cleanup resolution states that a complete scan found zero collision
artifacts, but current read-only inspection finds
`core/__pycache__/__init__.cpython-313.pyc.relocated-aeat-2`. It remains ignored
by the generic `__pycache__/` rule and cannot load as ordinary bytecode with that
suffix, so it does not reopen a high-severity import or shim finding. The cleanup
finding is nevertheless not fully closed: one of the original uniquely suffixed
collision files remains under the source tree.

### phase-p03-closure-high-findings | high | No high-severity W02.P03 finding remains

Both previously high findings have evidence-backed resolutions at current HEAD.
The retained bytecode debris is low severity and the historical recommendations
remain useful process guidance, not open high blockers.

### phase-p03-closure-critical-findings | critical | No critical W02.P03 finding remains

The closure checks found no data loss, authority-evidence corruption, restored
former import root, or other critical defect.

## Recommendations

1. Keep later configuration and persistence implementation blocked on the wallet diagnostic setting until the principal engineer records one referent decision. Prefer classifying the environment variable by what it controls: if it chooses Cadrumo's local output custody, rename the control to `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` while retaining AEAT terminology in the captured payload and description. If authority identity is intended to govern the setting name, explicitly amend `S02` and its zero-ambiguity count instead.
2. Add a review gate that compares overlapping environment-variable and persistence matrices before `W02.P04`, so every setting named in both records has one disposition.
3. Remove scaffold annotations from completed `S01` through `S03` records in a separately owned documentation-hygiene change; do not mix that cleanup into this review commit.
4. Preserve the existing release blockers from `S04`: availability observations are not reservations, and Spanish/EU trademark clearance remains outstanding.
5. Do not treat `W01.P01` as contradiction-free until the high-severity finding is resolved, even though its four administrative plan checkboxes are closed.
6. Reconcile the closed `S08` Step scope through the canonical plan CLI so it names `.vaultspec/rules/cadrumo-product-authority-names.md`; do not move or duplicate the registered rule merely to satisfy the stale provisional path.
7. Treat the preceding `diagnostic-dump-identity` high finding and recommendations 1 and 5 as superseded by `diagnostic-dump-identity-resolution`; retain them as rolling review history rather than reopening the resolved issue.
8. Keep the Cadrumo identity module import-light and consume `PRODUCT_IDENTITY` through the facade in later Waves instead of redeclaring tuple values or introducing aliases.
9. Before accepting `W02.P03`, retarget both executable test strings to Cadrumo and add a direct negative assertion that `aeat` does not resolve; rerun the real subprocess and scratch-pytest behaviors without mocks or shims.
10. Correct every remaining active import example and the cross-domain snapshot action message to `cadrumo`; retain only genuine authority uses such as `adapters.outbound.aeat` and registry taxonomy.
11. Record explicit ownership disposition for the fifteen formerly untracked source/data files absorbed by the move commit. Do not rewrite history destructively; use an audit/ownership record so future rollback and feature attribution remain honest.
12. Remove the ignored `.relocated-aeat` bytecode artifacts through an explicitly authorised, verified cleanup step before packaging acceptance, then prove wheels and source archives contain no such members.
13. Add a move-integrity manifest for future tree-scale relocations: old relative path, target relative path, byte hash, tracked/dirty/untracked status, and collision disposition. Cardinality plus rename detection is useful but insufficient for a dirty 21,000-file move.
14. Remove the one remaining `*.pyc.relocated-aeat-2` artifact through the same verified literal-path cleanup discipline, then rerun the exact `fd -HI relocated-aeat src/cadrumo` check before marking the low finding resolved.
