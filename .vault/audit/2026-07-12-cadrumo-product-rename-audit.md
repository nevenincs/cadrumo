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
modified: '2026-07-17'
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

### relocated-bytecode-debris-final-resolution | resolved | Suffixed collision variant removed

The closure review found one ignored
`__init__.cpython-313.pyc.relocated-aeat-2` variant that the first exact suffix
filter did not match. Its resolved path was verified inside the workspace and
removed with a literal-path operation. A wildcard suffix scan for
`*.pyc.relocated-aeat*` now returns zero files.

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

### s19-public-facade-import-regression | high | Resolved missing database-sentinel re-export

`core.config` omitted the public re-export of
`FORMER_PRODUCT_DATABASE_FILENAME`, causing the SQL engine's valid facade
import to fail before engine construction. The facade now re-exports the
constant defined in `core/_config_state_root.py`, without duplicating its
literal, adding fallback behavior, or introducing a private cross-package
import. Direct facade and engine imports plus the focused former-database
refusal tests pass. The four concurrently owned S20 authentication/session
files remain unchanged by this remediation.

### phase-p04-custody-resolver-gap | high | Modelo 145 records cannot satisfy the complete-custody contract

The S22 record discloses, but does not resolve, a failure in
`test_every_carried_namespace_has_a_natural_key_resolver`. Independent targeted
execution at the reviewed HEAD reproduces the failure: the carried namespace
`cadrumo.application.modelo.m145_communication_record` has no natural-key
resolver. This is not merely a rename-spelling assertion. The namespace is a
registered bucket-local financial custody row, so the missing resolver prevents
the complete-custody/export machinery from deriving the stable identity needed
to carry those records. S22 and S23 therefore cannot establish complete
persistence closure while this gate remains red.

The S22 record accurately labels the failure as outside that step's bundle
format edit, and no reviewed rename commit introduced a fake, mock, stub,
patch, monkeypatch, skip, or xfail to conceal it. Nevertheless, provenance does
not make a live custody-integrity failure safe to release. Add the production
resolver through the authoritative resolver registry and prove a real Modelo
145 record survives export/import with the same natural identity before closing
W02.P04.

### phase-p04-namespace-discovery-blind-spot | medium | One registered production namespace is absent from discovery

Independent execution also reproduces the S21 record's broader failure in
`test_every_discovered_production_secure_object_namespace_is_registered`:
`cadrumo.domain.transactions.bucket` is present in
`STORAGE_NAMESPACE_REGISTRY`, but the production-namespace discovery helper
does not discover it. Runtime registry coverage is therefore present, but the
guard intended to detect unregistered persistence literals has a blind spot.
Repair the discovery mechanism or the production declaration shape rather than
weakening the asserted worked example, then rerun the complete registry gate.

### phase-p04-hard-cut-review | resolved | Rename boundaries fail closed without compatibility paths

Review of S17-S23 and commits `523391ab8d`, `a0db621ca1`, `568a4030d7`,
`8b67cc4360`, `7cc976dd66`, `dec439b019`, `a36049dc97`, `34e04e3986`, and
`e7a9ec4753` found no migration, fallback, dual-read, adoption, or compatibility
write path. Product-owned environment controls use Cadrumo identity while AEAT
authority controls and mixed namespace authority segments remain explicit.
Former root, database, session, namespace, and bundle identities are checked
before canonical creation, engine construction, row access, payload read, or
write; refusal tests preserve the old bytes and rows.

The bundle cut requires schema version 3 and `product: cadrumo`, validates the
header before returning payload bytes, and binds the serialized header into the
sealed format rather than accepting the former header as an alias. The focused
rename tests exercise production code directly and add no prohibited test
shortcut. The checkout itself contains a former `aeat.db`; direct `Settings()`
construction refuses it before normal startup. That local failure is expected
hard-cut behavior and corroborates the recorded environment sensitivity, but it
also means broad validation from this checkout is not a clean-state pass. Only
the explicitly isolated clean-state results may be cited as passing evidence.

### phase-p04-review-critical-findings | critical | No critical W02.P04 finding identified

The reviewed cuts preserve former-state bytes, retain AEAT authority identity,
and fail closed before adoption or mutation. No data destruction, cryptographic
downgrade, former-state compatibility reader, or authority-evidence corruption
was identified. The unresolved Modelo 145 custody resolver is high severity and
must remain a release blocker, but current evidence does not establish a
critical-severity defect.

### phase-p04-custody-resolver-gap-resolution | resolved | Modelo 145 custody now derives its production natural key

The custody registry now parses the stored Modelo 145 envelope through
`M145CommunicationRecord`, rejects a payload whose bucket differs from the custody
bucket, and delegates key derivation to the production
`m145_communication_record_object_key` authority. The same correction aligns the
three Modelo 145 service-owner validators with their existing Cadrumo default and
write path. Real-behavior coverage creates a registry-valid Modelo 145 record, carries
it through a sealed bucket export, imports it under a fresh storage root, and reads the
same record identity and content. The exact namespace-completeness gate, sealed
archive round trip, and authoritative persistence test pass together (3 passed).

### phase-p04-namespace-discovery-blind-spot-resolution | resolved | Discovery follows canonical Cadrumo product identity

The production-namespace AST resolver still admitted only string literals beginning
with the retired `aeat.` product prefix. Consequently, the valid production declaration
`TX_BUCKET_NAMESPACE = "cadrumo.domain.transactions.bucket"` was invisible even though
the transaction repository passes that binding through its real secure-object calls and
the namespace registry declares the same value.

The single resolver now derives its accepted leading prefix from
`PRODUCT_IDENTITY.python_package`. This restores discovery for the transaction bucket
and every other directly declared Cadrumo production namespace without adding a
transaction-specific exception, test-only enumeration, compatibility spelling, or
duplicate namespace authority. The exact formerly failing discovery gate passes.

### phase-p04-remediation-closure-verification | resolved | Custody and namespace integrity gates are green at current HEAD

Independent re-review after `f7419fc449` and `6d862a38b5` confirms both W02.P04
findings are closed. The exact natural-key completeness gate, the real sealed
bucket export/import test carrying a registry-valid Modelo 145 communication
record into a fresh storage root, and the exact production namespace discovery
gate pass together (`3 passed`). The round trip reads back the same production
record identity and content; it does not mirror custody logic in the test.

The custody resolver parses the stored envelope as the production
`M145CommunicationRecord`, checks its bucket against the custody bucket, and
delegates key construction to the existing production object-key authority. The
discovery guard derives its accepted prefix from canonical `PRODUCT_IDENTITY`
instead of admitting the retired product prefix or adding a namespace-specific
exception. Diff review found no former-product alias, fallback, migration,
adoption, dual read, duplicate namespace authority, fake, mock, stub, patch,
monkeypatch, skip, or xfail in either remediation.

### phase-p04-remediation-high-findings | high | No high-severity W02.P04 finding remains

The previously high Modelo 145 custody finding now has a production resolver and
real fresh-root export/import evidence. The namespace discovery guard is also
green, and no new high-severity compatibility or persistence defect was found in
the remediation commits.

### phase-p04-remediation-critical-findings | critical | No critical W02.P04 finding remains

The closure review found no data loss, former-state adoption, cryptographic
downgrade, authority-identity corruption, or other critical defect. The reviewed
W02.P04 findings are closed at current HEAD.

### phase-p05-human-executable-contract-inversion | high | Reviewed commits contradict the accepted sole `aeat` executable

The accepted executable ADR and the W03.P05 plan define one human command:
`aeat`, bound directly to the Cadrumo CLI. The reviewed committed state instead
sets `PRODUCT_IDENTITY.cli_executable` to `cadrumo`, declares the `cadrumo`
console script, pins Typer to `cadrumo`, and changes product-owned command
guidance to that spelling. `S24` and `S25` describe this inversion as a newer
instruction, but no accepted replacement decision or reconciled plan records
that change; their own originating Step rows continue to require `aeat`.

This is a release-blocking contract defect, not a harmless rename preference.
It makes the canonical tuple, package entry points, help output, tests, and the
accepted operator interface disagree about which executable exists. Concurrent
uncommitted bytes now expose `aeat` in `pyproject.toml` and pin the CLI main path
to `aeat`, and the currently available local wheel correspondingly contains only `aeat`
and `cadrumo-mcp`; however, `PRODUCT_IDENTITY` still says `cadrumo`, and
uncommitted overlap is not closure evidence. Reconcile the tuple, runtime,
tests, authored command guidance, metadata, and a freshly built installed wheel
to the accepted `aeat` contract, or approve a superseding ADR and plan before
claiming the opposite interface.

### phase-p05-plan-cross-commit-drift | medium | S25 reopened unrelated completed Steps and left S24 unchecked

Commit `58c524f9cd` did not limit its plan mutation to S25. It also reopened the
previously completed identity-authority Steps S05 and S07 and reverted S24 from
complete to incomplete. Consequently the current plan marks S24 unchecked even
though an S24 execution record and commit claim completion, while S25 is checked
against wording its implementation contradicts. The S24 and S25 records do not
disclose this plan-state rollback. Reconcile plan status through the canonical
plan workflow and keep future execution-record commits scoped to their own Step
instead of carrying a stale plan snapshot across concurrent owners.

### phase-p05-record-and-artifact-truthfulness | medium | S24 evidence names the wrong entry-point contract

The S24 record says its wheel exposes a human `cadrumo` entry point and calls
that the requested tuple even though the parent Step and accepted ADR require
`aeat`. The wheel currently available for inspection reports `Name: cadrumo`,
contains 19,181 `cadrumo/` members and no `aeat/` import root, and declares
exactly `aeat` plus `cadrumo-mcp`; therefore it cannot substantiate the record's
claimed entry-point result. Regenerate the wheel only after the executable
decision is reconciled, record its hash/path and exact `entry_points.txt`, and
do not reuse a concurrently rebuilt artifact as evidence for an earlier commit.

### phase-p05-packaging-and-remedy-review | resolved | Distribution, MCP executable, and extras cut cleanly to Cadrumo

Outside the human-command conflict, the reviewed packaging boundary is sound.
The distribution and package root are `cadrumo`; the inspected wheel has no
former import root; `import cadrumo` succeeds and `import aeat` has no spec; and
`cadrumo-mcp` points directly at the Cadrumo MCP entrypoint. S26 changes only
the MCP executable and install-remedy layer: server, tool-prefix, resource URI,
and human-CLI subprocess wire work remain separable for W04.

Every active Python runtime install remedy inspected names a declared Cadrumo
extra. The focused identity/refusal/degradation slice passes (`11 passed, 1
deselected`), and both real-client MCP handshake tests pass when the integration
marker is enabled (`2 passed`). No former distribution alias, Python shim,
fallback installer, fake, mock, stub, patch, monkeypatch, skip, or xfail was
introduced. Retained AEAT names in adapter paths, Sede descriptions, official
corpus concepts, and mixed authority namespaces remain authority terminology.
The Spanish `aeat <comando> --help` sentence is consistent with the accepted
human executable and must not be mechanically regenerated to `cadrumo` unless
that decision is formally superseded.

### phase-p05-review-critical-findings | critical | No critical W03.P05 finding identified

The executable contradiction is high severity because it blocks a truthful
installed interface, but the review found no data destruction, authority
evidence corruption, import compatibility package, credential exposure, or
other critical defect.

### phase-p05-human-executable-contract-resolution | resolved | Cadrumo ADR supersedes former CLI naming

The HIGH finding applied an older CLI naming decision after the accepted
`2026-07-12-cadrumo-product-rename-adr` had explicitly replaced product naming
with the canonical tuple whose human CLI is `cadrumo`. Under the newer
authorising decision, `aeat` is reserved for the Spanish authority and cannot
remain a product executable alias.

Concurrent WIP had changed the live script, Typer name, lazy command key,
invocation detector, and `prog_name` back to `aeat`; those exact lines were
reconciled to `cadrumo` while preserving surrounding peer work. The plan's S24
and S25 actions were restored through the canonical plan CLI, and the
accidentally reopened S05, S07, and S24 rows were reclosed from their existing
committed Step evidence. The current metadata again exposes only `cadrumo` and
`cadrumo-mcp`.

### phase-p05-plan-traceability-resolution | resolved | Completed Step state restored

S05, S07, and S24 have committed implementation records and were reopened only
because a cross-commit carried unrelated plan edits. Their checked state is now
restored, and S24's action again matches its accepted Cadrumo record. No Step was
closed without existing implementation evidence.

### phase-p05-executable-closure-verification | resolved | Committed metadata and wheel implement the accepted Cadrumo CLI

Re-review against the accepted `cadrumo-product-rename` ADR confirms that the
former HIGH executable finding applied the wrong governing decision. At HEAD,
the accepted ADR defines `cadrumo` as the sole human executable; the separately
named `cadrumo-cli-executable` document exists only as untracked concurrent work
and does not supersede committed architecture.

The source tuple is exact: distribution, Python package, human executable, and
canonical CLI identity are `cadrumo`, while the distinct MCP executable is
`cadrumo-mcp`. `pyproject.toml` declares exactly those two console scripts and
both point directly into the Cadrumo package. Typer pins `prog_name` to
`cadrumo`. A fresh isolated wheel build reports `Name: cadrumo`, version `0.1.1`,
contains 19,181 `cadrumo/` members and zero `aeat/` import-root members, and its
`entry_points.txt` declares only `cadrumo` and `cadrumo-mcp`. The stale local
environment executable is not used as acceptance evidence; lock/sync
regeneration remains assigned to S36.

The prior HIGH executable-contract finding and medium artifact-truthfulness
finding are therefore resolved under the accepted Cadrumo authority. No former
console alias, import shim, metadata fallback, or dual executable was found.

### phase-p05-plan-prose-executable-drift | medium | Checked Steps are correct but active plan prose still requires `aeat`

Commit `ceeef06e13` correctly reclosed S05, S07, S24, and S25 and rewrote the
S24/S25 rows for the Cadrumo executable. It did not reconcile three other active
plan statements: the plan description still calls `aeat` the sole human
command, the W03.P05 phase description still says the distribution exposes
`aeat`, and verification item 2 still requires `aeat --version` while calling
`cadrumo` an alias. Those statements contradict both the accepted ADR and the
now-correct checked Steps. Update the active plan through its canonical editing
workflow before using it as closure or residue-gate authority.

### phase-p05-closure-high-findings | high | No high-severity W03.P05 finding remains

The committed product tuple, metadata, CLI program identity, and freshly built
wheel agree on the sole Cadrumo human executable. The remaining plan-prose drift
is a medium governance defect and does not reopen the corrected installed
artifact boundary.

### phase-p05-closure-critical-findings | critical | No critical W03.P05 finding remains

No compatibility package, second console alias, authority-evidence corruption,
or other critical defect was found in the closure review.

### phase-p05-plan-prose-resolution | resolved | Plan prose matches canonical executable

The remaining Description, P05 intent, and Verification prose now name
`cadrumo` as the sole human executable and `cadrumo-mcp` as the distinct MCP
command. The former `aeat` executable and import root are explicitly absent.
This aligns every active plan statement with the accepted Cadrumo ADR, checked
S24/S25 rows, source metadata, and inspected wheel.

### phase-p06-companion-package-review | resolved | Both wheels form one disjoint Cadrumo data namespace

Review of the overtaking `f99ee0c821` change and follow-ups `cb372f0b26`,
`0891bedfd5`, `f40e91cfcc`, and `de9ed47ef8` confirms the two companion projects
implement the accepted split. The former project directories are absent; each
canonical directory carries the same three logical project files; distribution
names, version `0.1.1`, repository URLs, root source mappings, and install
guidance match the root Cadrumo metadata tuple.

Both real Hatch hooks write only beneath `cadrumo_data/_data/corpus` and ship no
namespace initializer. Manuals owns only `manuals`; official owns only
`aeat_official` and `normatives`. The latter spelling and associated AEAT prose
correctly identify Spanish-authority evidence rather than the former product.
Runtime discovery derives the single `cadrumo_data` namespace from
`PRODUCT_IDENTITY` and contains no `aeat_data` alias, fallback, or dual lookup.

The focused real-artifact suite passes (`12 passed`): it builds both wheels,
derives expected members independently from Git-tracked source binaries, proves
each partition exact, their intersection empty, their union exhaustive, both
versions equal to the root, both archives below the 100 MB publication cap, and
byte-exact runtime reads across both PEP 420 portions. The tests introduce no
fake, mock, stub, patch, monkeypatch, skip, or xfail. The overtaken Step records
truthfully distinguish directory reconciliation from the content work already
combined in `f99ee0c821`; later S34/S35 commits exclude unrelated staged work
through explicit path scopes.

### phase-p06-ignored-hook-bytecode | low | Both companion directories again contain ignored build caches

S28 and S31 record verified removal of ignored Hatch bytecode, but current
inspection finds `__pycache__/hatch_build.cpython-313.pyc` beneath both companion
project directories. Real builds/imports can recreate these files, and the
wheel ownership gates prove neither cache is packaged, so this is not a move- or
artifact-integrity defect. The cleanup outcome is nevertheless non-durable.
Keep build caches outside reviewed source directories or perform a final
verified ignored-debris sweep immediately before artifact acceptance.

### phase-p06-review-high-findings | high | No high-severity W03.P06 finding identified

Move integrity, namespace exclusivity, partition completeness, version parity,
and installed resource resolution all have independent evidence. No missing or
duplicated corpus payload, former namespace reader, or publication-size blocker
was found.

### phase-p06-review-critical-findings | critical | No critical W03.P06 finding identified

The review found no official-evidence loss or mutation, namespace collision,
former-product compatibility path, or other critical defect.

### companion-hatch-bytecode-resolution | resolved | Ignored build-hook caches removed

The two ignored companion `__pycache__` directories were resolved inside the
workspace, their files removed individually, and the now-empty directories
removed non-recursively. A follow-up scan across both companion projects found
zero `*.pyc` files. The real-wheel evidence already proved these caches were
never package members.

### phase-p07-incomplete-clean-install-acceptance | high | Three checked smoke Steps lack post-fix completion evidence

S37 and S40 are checked complete even though their real clean-install commands
expired at the 124-second outer budget before producing smoke manifests. S39 is
also checked complete although its only Docker execution failed during profile
creation; the database-route correction was inspected and compiled but the
container lane was not rerun. The records disclose these outcomes honestly, but
checked plan state converts incomplete or failing evidence into apparent Phase
closure.

S41 and S42 strongly establish wheel composition, installation, import refusal,
entry points, partition ownership, bytes, and size. They do not execute the
remaining core smoke workflow, a real joint split-install lifecycle, or the
corrected Docker profile path. Therefore these timeouts do not invalidate the
artifact bytes, but they do block claiming W03.P07 complete. Because the plan
hard-sequences W04 after W03, they also block proceeding under the current plan
as though the artifact Wave were proven. Obtain bounded successful post-fix runs
with manifests, or explicitly amend the acceptance plan; do not reinterpret a
timeout or pre-fix Docker failure as a pass.

### phase-p07-artifact-and-lock-review | resolved | Canonical lock and wheel ownership evidence are internally sound

`uv lock --check` resolves 246 packages and the live lock is byte-identical to
HEAD. It contains exactly one editable `cadrumo` 0.1.1 record and one 0.1.1
record for each companion, with canonical directory sources and no former
distribution or project-directory record. S38's fresh aggregate-extras smoke
completed and wrote its manifest.

The S41 correction extends the split-owned binary authority consistently across
root exclusions, the official Hatch hook, split smoke, and the independent
distribution gate to include `.docx` and `.zip`. S42 then proves both companion
wheels are disjoint and exhaustive over all 193 tracked source binaries, byte
identical, PEP 420 compatible, version aligned, and below the file cap. The root
wheel contains neither those companion binaries nor any `aeat/` or
`cadrumo_data/` import root, and its installed Cadrumo import/version/former-root
refusal evidence is real. Focused smoke-manifest validation passes (`1 passed`)
and Ruff passes on all changed probes and ownership authorities. No mock, fake,
stub, patch, monkeypatch, skip, or xfail substitutes for these checks.

### phase-p07-concurrent-script-drift | medium | Unapproved WIP again replaces the canonical script locally

Committed HEAD and the reviewed stable-archive artifact declare only `cadrumo`
and `cadrumo-mcp`, and the unapproved CLI ADR was correctly excluded from every
P07 commit. The shared working tree nevertheless again changes the root script
key from `cadrumo` to `aeat` and carries that conflicting ADR as untracked work.
This is not a committed alias and does not invalidate S41's captured artifact,
but it proves the one-line restoration is not durable in the live checkout.
Future artifact or lock work must continue to build from a verified committed
tree or obtain explicit ownership of the script line; never stage the local
conflict with rename delivery.

### phase-p07-review-critical-findings | critical | No critical W03.P07 finding identified

The incomplete smoke evidence is high severity because it blocks truthful Wave
closure, but no source-binary loss, companion-byte corruption, namespace alias,
credential exposure, or other critical defect was identified.

### phase-p07-core-smoke-payload-parity-resolution | resolved | Slim payload gate consumes packaging ownership

The first bounded post-fix core run stopped during wheel validation after 14.101
seconds because the smoke gate still expected the `.docx` and `.zip` files that
S41 had correctly moved into the official companion. No manifest was written and
no install, import, CLI, or profile check ran, so this result was classified as a
gate defect rather than clean-install evidence.

The core smoke now derives split-owned suffixes from the root Hatch exclusion
configuration and verifies every excluded tracked corpus file against the real
manuals or official companion hook ownership maps. A focused real-wheel member
test requires every remaining tracked slim-core data file, rejects every
split-owned binary, and specifically covers the two files exposed by the failed
run. This resolves the payload-gate mismatch only; the rolling HIGH remains open
until the bounded full core smoke completes and writes its manifest.

### split-smoke-m036-source-fingerprint | high | Installed authority rejected the normalized official procedure bytes

The post-fix split-install run reached the companion-less installed authority and
failed because `aeat-modelo-036-procedure` still declared the pre-relocation CRLF
fingerprint: 36,079 bytes and SHA-256 `fd5264e1a8c371eb2bad45347a0defa5cc79882051cd6e90d9980a70722f53bd`.
The package-root relocation had already normalized the tracked official HTML blob
to LF without changing its text, yielding 36,022 bytes and SHA-256
`c757f418705b37e33937a69d9f306f1afe4c7371505e5ba4583bb95b40e89df3`.

### split-smoke-m036-source-fingerprint-resolution | resolved | Relocation-normalized evidence bytes restored

Catalogue-wide comparison found 28 text evidence blobs normalized by the relocation,
while their reviewed declarations still matched the pre-relocation official bytes.
Changing those declarations would have legitimized an accidental evidence mutation.
The affected HTML, XSD, and properties files were therefore restored to their declared
CRLF byte representations without refetching or changing textual content. Exact
bundled-authority validation and focused source-integrity tests pass against the
preserved official bytes, resolving the installed-runtime blocker.

### compatibility-absence-s77 | resolved | Hard-cut compatibility absence is pinned by real behavior

Formal review against the committed product-rename ADR found no unresolved
S77 defect. The source layout and fresh-subprocess import proof reject an
`aeat` package root; root metadata exposes exactly `cadrumo` and
`cadrumo-mcp`, both bound directly to Cadrumo entrypoints. Existing real
dotenv, filesystem, encrypted repository, database, session-key, namespace,
and sealed-archive tests prove former product controls and state are ignored or
refused without a shim, alias, fallback, migration, adoption, or mutation.
Authority-owned AEAT adapters, endpoints, credentials, registry taxonomy, and
legal evidence remain correctly outside the compatibility prohibition.

The untracked `cadrumo-cli-executable` ADR is not accepted authority and was
excluded from this review. Its presence contaminated a generated shared index
during exec scaffolding; that index is not part of S77's reviewed or committed
surface.

### s76-developer-audit-tooling | resolved | Developer scanners target the live Cadrumo tree non-vacuously

Formal review of the assigned S76 developer-tooling slice found no unresolved
finding. The complexity, composed health, semantic, evidence-corpus, and
Vulture authorities now name `src/cadrumo` or `cadrumo` product modules. The
complexity baseline preserves its recorded values while mechanically moving
all product-root keys to `src/cadrumo`; five independently present debt
removals were preserved rather than restored. AEAT remains intact inside the
current product root wherever it denotes the outbound authority adapter.

The review verified non-vacuity with live source cardinality, Radon findings,
baseline cardinality, semantic-path classification, and the existing corpus
directory. Ruff, JSON parsing, and nineteen real-tool tests pass without mocks,
patches, skips, or expected failures. `W06.P14.S76` remains open because this
commit closes only the explicitly assigned developer audit/evidence tooling
group, not the full repository residue inventory.

The direct production complexity invocation is now honestly non-green rather
than vacuously clean: it reports 503 allowed baselined hotspots, one resolved
entry, and 26 current new or regressed findings owned by the broader live tree.
Those findings are not accepted into the baseline or hidden by this path
remediation.

### s76-demo-and-hygiene | resolved | README demo and identity acceptance tests follow the hard cut

Formal review found no unresolved finding in the assigned demo-generator and
hygiene slice. Both README demo programs import and bootstrap Cadrumo directly,
display the `cadrumo app quickfile` command, and retain a disposable
`CADRUMO_*` environment. The real preparation run completed successfully.

The core identity test now follows package-local relative-import discipline.
The persistence acceptance test reaches the storage and bucket public facades,
the public domain import error, and the supported settings module instead of
private outbound-auth, runtime-repository, SQL, or sealed-archive modules. The
dedicated auth-package test remains the owner of former session-store refusal;
the cross-boundary acceptance test proves canonical encrypted repository
custody plus former database, namespace, and bundle refusal without duplicating
private implementation access. No import-hygiene baseline or allowlist changed.

The recurring unapproved executable detour rewrote this slice twice during
verification. Work paused for two coordinator-authorized neutralizations; the
final review and tests use the committed `cadrumo` identity. `W06.P14.S76`
remains open because this commit closes only the assigned demo and hygiene
group.

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
15. Add the missing natural-key resolver for `cadrumo.application.modelo.m145_communication_record` through the authoritative production registry and prove a real record's export/import identity round trip before W02.P04 closure.
16. Restore production namespace discovery coverage for `cadrumo.domain.transactions.bucket`; keep the worked-example assertion and fix the scanner/declaration boundary rather than deleting the expectation.
17. Rerun both persistence integrity gates and the S23 acceptance file from a genuinely clean Cadrumo root after the local former database is handled by an operator-authorised process. Do not report the current hard-cut refusal as a broad test pass.
18. Restore the accepted single `aeat` human executable consistently across `PRODUCT_IDENTITY`, Typer `prog_name`, authored command guidance, structural tests, and root metadata; alternatively, approve and propagate a superseding ADR before implementing `cadrumo` as the command.
19. Reconcile S05, S07, S24, and S25 plan status through the canonical plan workflow. Do not let a Step commit carry unrelated checkbox reversions from a stale shared-plan snapshot.
20. Build a fresh wheel from the reconciled committed tree and record the exact console-entrypoint pair, absence of an `aeat` import root, and installed `--help`/`--version` behavior. Keep MCP wire-identity changes assigned to W04.
21. Reconcile the plan description, W03.P05 phase description, and verification item 2 from the former `aeat` executable wording to the accepted sole `cadrumo` command before plan closure.
22. Prevent or sweep the two companion `__pycache__/hatch_build.cpython-313.pyc` files immediately before final artifact inspection; verify by literal companion-directory scans and do not treat their temporary removal as durable across builds.
23. Re-run the corrected core, split-install, and Docker core probes with bounded per-stage diagnostics and enough outer budget to write their manifests. Keep S37, S39, and S40—and therefore W03.P07—open until those post-fix runs complete successfully.
24. Quarantine or resolve the concurrent `aeat` script/ADR work before any further build or lock commit. Verify `git show HEAD:pyproject.toml` and the actual build input both expose only `cadrumo` plus `cadrumo-mcp`.

## 2026-07-12 packaging remediation provenance

The split-install sequencing remediation was committed as
`121ca96c080886a987bf21cf6a8a184cc102cc1e`. During concurrent work, that commit
was created by amending the immediately preceding dev-container commit
`274c6c75208967a71026f66f1eb8346099306fe2`. The resulting commit therefore
couples `.devcontainer/devcontainer.json`, `Dockerfile`,
`dev/packaging/smoke_split_install.py`, and
`dev/packaging/tests/test_smoke_split_install_sequence.py`. Both bodies of work
remain present, and the original dev-container commit object remains available,
but their feature provenance is coupled in the branch history. No reset, rebase,
or further history rewrite was used to disguise or split the collision.

The accepted product-identity ADR and the user-approved plan define `cadrumo` as
the sole human CLI. A concurrent, unapproved ADR proposing `aeat` does not
supersede that decision. The root script metadata was reconciled again after the
overlap; recommendation 18's `aeat` alternative is rejected, while
recommendations 20, 21, and 24 remain governed by the canonical `cadrumo` /
`cadrumo-mcp` pair.

## W03.P07 packaging HIGH resolution

The packaging acceptance blocker is resolved by successful, bounded, real
installed-artifact runs from isolated Git snapshots:

- Core wheel at `f8169402a7ac4f727cc5aa06fd29fa8c13043223`: exit 0 in
  192.201 seconds; manifest `ok: true`, lane `core-wheel`; all eight export,
  payload, metadata, fresh-install, resource, attachment, optional-boundary,
  and CLI profile/config checks passed. The wheel was 41,883,465 bytes.
- Split install at `300426cc75d4265b3ef2bb2040fda976e3ad01b8`: exit 0 in
  426.627 seconds; manifest `ok: true`, lane `split-install`; the slim-only
  production refusal passed, both companion distributions installed into the
  joined namespace, and full byte-exact authority verification passed.
- Docker core at `43777a3f6f4fd97d921c4000fcc50b79a684e621`: exit 0 in
  102.792 seconds; manifest `ok: true`, lane `docker-core`, backend
  `wsl:Ubuntu`, image `python:3.13-slim`; installed resources, profile/config,
  attachment round-trip, and the missing-extra boundary passed.

The remediations were evidence-led: classify Pillow as a legitimate core
transitive dependency, track the imported operator-progress runtime module,
let profile bootstrap derive its bucket database route, and provide an explicit
tax-residence CCAA in the Docker fixture. Recommendation 23 and the P07 HIGH are
closed. The successful runs used only the accepted `cadrumo` and `cadrumo-mcp`
product executables; AEAT remains authority terminology.

## W04.P08 S46 shared-index provenance

Commit `6f2f22ab06` correctly contains the S46 hard cut to `cadrumo_` MCP tool
names and `mcp__plugin_cadrumo_cadrumo__` client prefixes, but it also consumed
67 peer-staged paths already present in the shared index. The mixed commit has
79 paths total and couples broad CLI copy/test changes, MCP prompt/tool edits,
one cross-domain execution record, and a packaging-test deletion with S46. It
also deleted the S45 execution record even though the S45 implementation remains
in history. No amend, reset, rebase, or other history rewrite was used. The S45
record and canonical prompt/server/metadata working bytes were restored by an
explicit follow-up commit, preserving both work bodies and disclosing their
coupled provenance.
