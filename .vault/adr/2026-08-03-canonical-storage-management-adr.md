---
tags:
  - '#adr'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:363cb0df726bbd3aa0e84704f094e2e9c360074d376439c4bf39d97b7e83392d'
related:
  - "[[2026-08-03-canonical-storage-management-research]]"
  - "[[2026-07-13-data-output-standardization-adr]]"
---

# `canonical-storage-management` adr: `canonical storage management API and config storage surface` | (**status:** `accepted`)

## Problem Statement

Where a byte lands on disk is decided today by four mutually unaware
authorities, and the gate written to prevent a fifth cannot see any of them.
`2026-08-03-canonical-storage-management-research` finding F1 establishes the
inventory: a 28-entry `dict[str, str]` in core config keyed by settings-field
name; a set of bare string constants in the persistence namespace registry that
owns the two most security-load-bearing directories in the tree; module-local
constants in three application and entrypoint modules; and three unpinned
inline copies of the registry's own names. Finding F2 establishes that the
anti-literal gate matches only slashed literals inside a `Path(...)` call and
skips test trees entirely, so every one of those sites is built by an operator
join it structurally cannot observe.

Finding F11 sharpens this from untidiness into a structural defect: the three
duplicate copies live in `core/` while the constants they duplicate live in
`adapters/`, so importing them would invert the hexagonal direction. The
duplication is a symptom of the names living in the wrong layer, and no
burndown can tidy it without a layering decision.

The consequences are already visible. Two declared categories have no
production writer at all (F7). The file-versus-directory distinction rides a
field-name suffix rather than a type (F4). The classification governing whether
a directory may ever be pruned lives in frozensets inside a test module (F3),
and that gate is red at committed HEAD (F13). Production code nests ad-hoc
subdirectories beneath enrolled categories that the taxonomy cannot see (F14).
An operator has no way to ask where data lives or what may safely be reclaimed
(F9). The test surface — 201 files calling `override_settings`, 24 conftests —
carries its own drift, including a fixture pinning a category to a path that
disagrees with the taxonomy (F16).

A decision is needed now because the operator's standing goal is a canonical
storage management API plugged into a `config storage` surface, with every code
site and API migrated, and an explicit mandate that every test, fixture, and
ad-hoc redeclaration migrates too. That work cannot be scoped, and its burndown
cannot be mechanically checked, until the authority's shape, its layer, its
membership test, and its enforcing property are fixed.

## Considerations

- The closed-value-set mandate in `aeat-architecture-boundaries` binds twice
  over: a closed set must be a `StrEnum` in `core/`, production code and CLI
  handlers must emit members rather than strings, and a Typer argument over a
  closed enum must declare that enum. The same rule forbids core depending on
  adapters, which is what makes F11's layering wall load-bearing on the
  representation choice rather than a separate concern.
- `2026-07-13-data-output-standardization-adr` is accepted, rules on locations
  and lifecycle, and is silent on Python-level representation (research F8). Its
  Option O2 is what a typed authority formalizes; its Option O3, a
  platformdirs-style multi-root split, was explicitly rejected and is not
  reopened.
- `cadrumo.core.COMPATIBILITY_REGIME` is `PRE_RELEASE`, so
  `no-legacy-compatibility` governs in full. Permitted is not obligatory: the
  blast radius of moving directories greatly exceeds that of typing their
  declaration.
- `sensitive-financial-data-secure-storage-only` governs what lives inside the
  encrypted substrate; this decision governs where on disk everything lives.
  Naming the directory the substrate occupies is not exposing its contents. The
  two senses of "storage" must not be conflated.
- The bucket and keystore layout is deliberately not operator-overridable: an
  operator must not be able to relocate a keystore out from under the bucket it
  unlocks (research F1). Any unification must preserve that, and must not
  achieve it merely by leaving those names in a different module.
- Three of the data-safety corrections this campaign would otherwise commission
  are already being fixed in-flight by peers (research F15), and the file
  carrying the lifecycle fix is peer-owned mid-flight (F13).
- A gate whose pass condition is a hardcoded count rots on the next ordinary
  change; a gate that counts name occurrences inherits the docstring
  false-positive class research F2 records. The enforcing property must be
  structural.

## Considered options

- **O1 — Type the settings dict only.** Cheapest, but research F1 shows it
  governs roughly half the tree while leaving `buckets/` and `keystore/`
  untyped, F2 shows the gate would still be blind to the sites left out, and
  F11 shows the duplicate literals stay unfixable. Rejected: it produces a typed
  authority that is not the authority.

- **O2 — Federate: two typed layers, root-category in `core/` and bucket-layout
  left in `adapters/`, sharing one accessor contract.** Models the genuine
  difference in override policy, and is the smaller change. But it leaves the
  bucket names in the layer that cannot be imported from `core/`, so the three
  duplicate copies stay — pinnable by a parity gate at best, never deletable —
  and the layering violation is unresolved. Rejected on F11.

- **O3 — Unify the names in `core/`, federate the policy on the member.** One
  typed authority in `cadrumo.core` declaring every application-chosen name,
  carrying scope and override-policy as fields; the namespace registry becomes a
  consumer of core rather than an independent authority. **Chosen.**

- **O4 — O3 plus a uniform structural path prefix.** Permitted under the
  pre-release regime, but research F5 shows the `cache/` asymmetry is deliberate
  and documented, and this would move every non-cache directory on disk for a
  cosmetic gain. Rejected.

- **O5 — Multi-root split per category.** Already rejected by the prior ADR;
  restated only to record that this decision does not reopen it.

- **O6 — Runtime registry populated by decorator at import time.** Declaration
  sits beside use, but the inventory becomes import-order dependent, invisible
  to a static gate, and unenumerable before the application runs — which defeats
  the operator question the CRUD surface exists to answer. Rejected.

## Constraints

- Research F17 records twelve migration invariants with dependent sites and
  concrete failure modes. The sharpest bind directly: relative overrides anchor
  to the platform user-data root one level *above* the storage root; absolute
  overrides pass through unchanged; an explicit override wins via
  `model_fields_set`, never a sentinel comparison; `override_settings` must keep
  popping derived fields when the root changes, or every isolation fixture leaks
  stale paths while still appearing to pass; `ensure_storage_tree` stays
  idempotent and keeps its "occupied by a file" diagnosis; the pointer-file
  import inside the database-URL validator stays deferred and
  submodule-qualified. Root permission hardening has no test asserting the mode
  bits, so a refactor could drop it silently — this campaign adds that test.
- **`src/cadrumo/core/tests/test_settings_lifecycle_gate.py` is peer-owned
  mid-flight and no implementation lane may edit it** (research F13). It is red
  at committed HEAD for three unclassified fields, and the peer's uncommitted
  edit is the active fix.
- The three data-safety corrections in research F15 are ratified, not
  commissioned: their owning files are peer-modified in the working tree and no
  lane may edit over them. The download correction has since been superseded and
  landed at HEAD — see R12, whose earlier ratification research F20 disproved by
  measurement; the review-package pair remains uncommitted peer WIP.
- The two-tier root-redirection chain is the canonical isolation mechanism and
  survives verbatim; see R15.
- Settings construction is cached because path resolution is expensive on
  Windows. No filesystem probe may enter settings construction or validation.
- Relative-path overrides anchor to the platform user-data root, never the
  checkout. Research F10 recorded two tests asserting the retired
  repository-root anchoring as red; a peer commit landing during this record's
  authoring re-anchored both, and they were re-run green at HEAD. This campaign
  inherits no red test on that axis, but any change it makes to anchoring must
  update those tests deliberately.
- Every new operator-facing string needs locale keys in all four catalogues via
  the locales CLI; the CLI reference is regenerated, never hand-edited.

## Implementation

**R1 — The typed representation.** A `StorageCategory` `StrEnum` in
`cadrumo.core` names every application-chosen location, and a frozen, strict
pydantic `StorageLocation` model carries the axes a bare member cannot: the
literal POSIX relative subpath, the node kind, the scope, the override policy,
the lifecycle class, and the fingerprint-exclusion flag. One `STORAGE_TAXONOMY`
mapping keyed by the enum is the single declaration. Both halves are required:
the enum because the CLI boundary mandate needs a closed type to render the
accepted set and production code must pass members rather than strings; the
model because a member cannot carry six axes without becoming a string that
encodes them.

**R2 — File versus directory is an explicit typed field.** `StorageNodeKind` is
a `StrEnum` of `DIRECTORY` and `FILE`. The `field_name.endswith("_path")`
inference in the tree materialiser is deleted, not retained as a fallback.
Inference cannot reach the six per-bucket file names no suffix convention
governs, and would silently create a directory over a file. The existing
assertion that the file-valued entry gets its parent created, not its leaf,
keeps passing.

**R3 — The `cache/` prefix asymmetry is preserved, and no path moves.** Each
member declares its literal relative subpath verbatim as it exists today. The
conceptual grouping is a separate declared field with no effect on the resolved
path. This decision changes representation, layer, and enforcement; it changes
no on-disk location. The pre-release regime would permit stranding local data
and this decision declines to use that permission.

**R4 — Three orthogonal axes, and the lifecycle gate keeps the larger set.**
Lifecycle class and fingerprint-exclusion become fields on `StorageLocation`,
but research F12 measured that a single folded axis is not faithful. The
lifecycle gate classifies 35 `Path`-typed settings fields, a strictly larger set
than the 28 categories, and `data_root_cache_exclusions` is a genuinely
independent third axis matching no union of the others. Therefore: the gate
**continues to enumerate `Path`-typed `Settings` fields, not taxonomy members**,
and the taxonomy widens to carry the non-category fields under a `kind`
discriminator (derived-output, opt-in override, bundled resource, exempt input)
so all 35 have a declared home. A fold that narrowed the gate's enumeration from
35 to 28 would still pass, silently dropping seven fields from coverage; that
outcome is a failed migration. The domain rationale currently in test-module
comments moves onto the declarations.

**R5 — The enrollment contract, binding production and tests alike.** One
accessor, `storage_path(category)`, returns the resolved absolute path; a scoped
variant takes the bucket identifier for per-bucket members. `ensure_storage_tree`
materialises the member set derived from the taxonomy, with no second list.

A site is enrolled when the location it uses is produced by that accessor. A
site is **not** enrolled when it does any of the following — the mechanical test
a burndown agent applies to get a yes or no without judgement:

- reads `cadrumo_local_storage_root` and joins anything onto it;
- names a child of the root, at any depth, by string literal or module-local
  constant;
- calls `Path.home()`, `expanduser`, or a platform-directory lookup to *derive*
  a location rather than to normalise a path it already holds;
- creates a directory whose name came from anywhere but a taxonomy member;
- pins a category to a literal in a test fixture or override instead of
  deriving it from the taxonomy.

**Nested paths are governed.** Research F14 found production code writing one
and two levels beneath enrolled categories. A path nested below a category is
enrolled only if that nested location is itself a declared member; the taxonomy
governs every application-chosen segment, not only the top of each category. A
typed top level with an ungoverned free-for-all one directory down is the same
defect at a different depth.

**The test surface is bound identically.** Per the operator mandate there is no
tests-are-different carve-out: every fixture, every conftest, every
`override_settings` call, and every re-typed literal migrates to the canonical
API. This is a first-class part of the contract, not an afterthought.

**R6 — Escapes are declared, not merely absent.** A path-valued setting stays
outside the taxonomy only when it fails one of two questions: does the
application *choose* this location, and does the application *write data* there?
Both yes means it enrolls. Bundled read-only package resources and
operator-supplied credential paths fail the write test; third-party-owned caches
(the Playwright browser binaries) and external executables (LibreOffice) fail the
choose test. Each escape is declared through an `ExternalPathRole` on the field,
so an escape is a positive statement carrying its reason rather than an absence
from a frozenset. `cadrumo_libreoffice_executable`, classified nowhere today and
invisible to the gate's own selector because of its name, is declared an
external executable; the selector widens from name-suffix to `Path`-typed
annotation so no field can hide by being named inconveniently.

Three root-anchored fields currently reading as oversights get explicit
categories rather than silence: `cadrumo_registry_disk_cache_dir` (an opt-in
override whose production branch derives under the cache namespace),
`cadrumo_wallet_diagnostic_dump_dir` (an opt-in diagnostic capture, off by
default), and the MCP session-telemetry directory (a full member — it is
application-chosen and application-written, so it fails no escape test).

**R7 — The CRUD surface.** `config storage` registers as a
`LIFECYCLE_OPERATIONS_ONLY` noun-group: an operator cannot create or destroy a
storage category, the same reasoning the apoderado and inventory groups use. The
verbs:

- `list` — every category with resolved path, node kind, grouping, lifecycle,
  scope, override binding, and whether it exists and holds anything. The
  populated-versus-empty column closes research F7's dormancy question by making
  it visible rather than audit-discoverable.
- `show CATEGORY` — one category in full, the argument typed as the enum so the
  accepted set renders at the boundary.
- `check` — verifies the tree against the taxonomy: missing directories, a file
  where a directory belongs and the reverse, permission drift on the root.
  Read-only; reports, never repairs.
- `init` — materialises the declared tree, idempotent, preserving existing
  content. It may never remove-and-recreate for a "clean state".
- `reclaim CATEGORY` — deletes regenerable content, refusing on any category
  whose lifecycle is unbounded-by-design or exempt, naming the class and the
  reason. Because research F14 shows arbitrary nesting beneath a category,
  reclaim operates on the category subtree and must not assume the taxonomy sees
  everything within it.

No verb moves existing data, and **relocating the root is refuse-and-instruct**.
Asked to relocate, the surface reports the current root, the environment
variable that sets it, and that the operator must move the tree and re-point it.
The tree holds encrypted taxpayer records, the key material that opens them, and
the audit trail over both; a partially-completed cross-filesystem copy, or one
that succeeds while the keystore does not, is unrecoverable.
`sensitive-financial-data-secure-storage-only` makes the substrate's custody
non-negotiable, and relocation is precisely a path that would move it outside
the guarantees the substrate's own primitives provide. Research F16's
sibling-secret-store divergence independently refutes the assumption a relocate
verb would need — that every category is literally `<root>/<subpath>`.

No verb name collides with reserved vocabulary: `pull` names an AEAT fetch and
`--file` a single local input file, and neither concept appears here.

Every result is a registered strict `OutputSchema` on the envelope spine with no
bespoke advisory, next, or suggestion field; diagnostics ride the typed notice
channel.

**R8 — Relationship to prior decisions.** This decision **extends**
`2026-07-13-data-output-standardization-adr` and supersedes nothing. Research F8
records that the four other accepted ADRs whose stems contain "storage" govern
the encrypted substrate's internals rather than the location taxonomy, so no
accepted ADR conflicts. The operator's standing goal anticipates superseding
conflicting decisions; the finding is that there are none, recorded explicitly
so a future reader does not hunt a phantom conflict.

**R9 — The enforcing gate.** The property is provenance, not census: **the
storage root has exactly one reader.** A structural AST test asserts the
`cadrumo_local_storage_root` attribute is accessed only inside the taxonomy
resolver. Every ad-hoc site research F1 found begins with exactly that access, so
a gate on the root's readership reaches the join-built paths a literal-matching
gate structurally cannot. It has no count, no vocabulary list, and no per-file
allowlist to drift.

**The gate covers tests.** A test that hardcodes a taxonomy-governed directory or
file name fails CI exactly as production code does;
`test_storage_route_classification.py`, which restates the same two names in five
assertions, is the worked example it must catch. The gate is AST-structural, not
a name census, because research F2 records a docstring that mentions a field
precisely to say it is not used — a counting gate inherits that false-positive
class.

Three gates support it. A materialisation-parity gate asserts the tree
materaliser's target set derives from the taxonomy rather than a parallel list.
A binding gate asserts every `Path`-typed settings field is bound to a member or
declared an escape with a role — enumerating all 35 fields per R4. A liveness
gate asserts every member has a production consumer or is explicitly declared
dormant with a reason, turning research F7's two writer-less categories into a
decision someone must take.

**R10 — Unify the names in core; federate the policy on the member.** The
bucket-layout and keystore names move into the core taxonomy, and
`_namespace_registry.py` becomes a consumer of core rather than an independent
authority — adapters depending on core is the legal direction, so no
`core → adapters` import is introduced anywhere. This is what makes the three
duplicate copies **deletable rather than merely pinnable**: once the names live
in core, `core/config.py`'s database-URL fallback, `_config_storage_route.py`'s
classifier, and the five test assertions all read the taxonomy directly.

The genuine difference federation was reaching for — that bucket layout must not
be operator-relocatable — is preserved as an explicit `override_policy` field
(`OPERATOR_OVERRIDABLE` versus `FIXED`) rather than as an accident of which
module a constant sits in. Encoding the guarantee as data makes it enforceable
and readable; encoding it as module placement is why the layering wall produced
the duplication in the first place. The SQL secure-object namespace definitions
are a different concern — logical database keys, not filesystem paths — and stay
where they are.

**R11 — Review-package staging must be `dir=`-pinned; the in-flight fix is
ratified.** Plaintext filing artefacts staged before archiving must be staged
under a taxonomy-governed location or the destination's own parent, never the OS
temp directory. The existing reviewed-writes allowlist entry covers the *design*
(stage briefly, then zip) but not the *destination*, and destination choice is
this campaign's subject matter. Research F15 records that both sites are already
corrected in a peer's working tree with exactly this shape; this ruling ratifies
that fix as the standing rule and does not re-commission the work. No lane may
edit those files.

**R12 — Browser-mediated downloads of taxpayer bytes are refused at the context
boundary; cancel-then-refetch is the second layer, not the control.** Letting a
browser automation layer materialise submitted-declaration bytes to its own
unconfigured temp location is a
`sensitive-financial-data-secure-storage-only` breach.

**This ruling previously ratified cancel-then-refetch as the fix. Measurement
disproved that, and the earlier wording is withdrawn** — a reader who derived
the weaker shape from it would ship the breach believing it closed. Research F20
records the experiment: with a real headless Chromium against a local harness, a
`.crdownload` file holding 250,000 bytes existed on disk 0.107s after a download
began, and the server confirmed 500,000 bytes had crossed the network before
`cancel()` aborted the connection. `cancel()` itself took 3ms, so this is not a
slow-cancel artefact. Cancelling removes the application's *dependence* on the
artefact; it does not prevent the artefact.

The required property is **`accept_downloads=False` at the browser context**,
set on the single context-construction path the adapter uses. Measured: the
download event still fires and `download.url` is still populated — the only
thing the flow needs — while `download.path()` raises and no file is ever
created. It is behaviour-neutral (the download-consuming site is the only one in
the codebase, and nothing listens for a download event), and a refuse-by-default
posture is strictly safer than a silent accept-to-an-unread-temp-file default
for any download a future change might trigger.

Two layers, each proving a different property and each pointing at the other:

1. **The context refuses the write** — the disk-write-side control, proven
   behaviourally by a test asserting `download.path()` raises on the real
   production context.
2. **The function never reads via a path anyway** — defence in depth, proven
   structurally: the URL is read, the transfer best-effort cancelled, and the
   same URL re-fetched in memory through the authenticated request context, the
   shape the sibling justificante capture already used.

**The generalisable rule for any future browser-mediated fetch of sensitive
bytes: refuse the write at the boundary; never rely on cancelling after it has
started.** The distinction generalises past browsers — a fix that removes our
dependence on an artefact is not a fix that prevents the artefact, and the two
are easy to conflate precisely because the code stops mentioning the file.

**R13 — Scope, not name, disambiguates the duplicated directory names.** `blobs`
and `audit` each name both a top-level category and a per-bucket subdirectory at
a different depth. Both are correct today. A flat name-keyed enum would conflate
them, so `StorageScope` (`ROOT`, `BUCKET_RELATIVE`, `KEYSTORE_RELATIVE`) is a
required field and members are identified by scope and name together. The
collision is not ruled acceptable-and-ignored: it is ruled expressible.

**R14 — Pinning tests migrate by re-expression, and a tautology is a failed
migration.** Test literals divide into incidental (someone needed a directory)
and pins-by-design (the test exists to assert that on-disk name). Both migrate;
only the style differs. An incidental literal is mechanically re-pointed to the
accessor. A pins-by-design literal is re-expressed so it still defends its
original property — asserting against the taxonomy's resolved value, with the
name's stability defended at the taxonomy declaration rather than restated in
the test.

A migration that turns a pinning test into an assertion that the accessor equals
itself has deleted the test's reason for existing while leaving it green. That
is a failed migration and must be treated as such in review. This is the single
most likely way the mandate is satisfied on paper and gutted in substance.

**R15 — The two-tier root-redirection chain is the canonical target, not a
refactor target.** It survives verbatim. It exists so collection-time imports
never resolve the real platform root and trip the retired-product cold-start
guard, and it must run before anything can resolve settings — which is why its
first tier is deliberately pure-stdlib with no application imports. Tests
migrate *to* it and to the shared isolation fixtures built on it. What does
migrate is fixture-level drift on top of the chain: per-field overrides that
duplicate the taxonomy at a call site, including the fixture research F16 found
pinning a category to a path disagreeing with the taxonomy's own subpath.

**R16 — Fingerprint participation is a third independent typed field, never
derived.** `StorageLocation` carries `fingerprint_participation` as its own
declared axis, orthogonal to `StorageLifecycle` and to the grouping.
`data_root_cache_exclusions` is rewritten to derive its set from that field
rather than from a hardcoded tuple of eight settings reads.

The derivation option is refuted by enumeration, not by preference. Research
F18 records all four candidates measured against the shipped set: retention
united with TTL (7 members), the `cache/` grouping (4), their union (9), and
retention alone (6). Every one differs from the shipped 8, and three differ in
**both** directions — missing members that are excluded while adding members
that are not. No lifecycle-or-grouping expression reproduces it, so any
implementer reaching for "exclude everything TTL" or "exclude everything under
`cache/`" would silently change what the replay-refusal mechanism treats as real
state drift. The failure is invisible: excluding too much walks the digest
toward the empty-tree constant, which is the exact historical defect the
fingerprint module's own docstring records as having defeated drift detection
for every installed operator; excluding too little turns the digest into noise
that churns on every cache write. Neither moves a test.

**The declared set deliberately differs from today's shipped set.** Research
F18 proves by measurement, with a positive control, that `cache/registry` — the
production location of the compiled registry pickle — is fingerprinted today: a
write into an excluded directory left the digest unchanged while a write into
`cache/registry` moved it. That is a regenerable cache rewritten on every
recompile, so it churns the digest and produces spurious replay refusals. The
omission is explained by the field's `None` default, which the exclusion
function could not resolve. Declaring participation per member fixes it as a
side effect. This is a deliberate correction, and an implementer must not
"restore parity" with the old eight-field set on seeing the digest change.

The gate for this axis asserts a property, with the positive control built in:
for a category declared non-participating, writing beneath it must leave the
digest unchanged; for a declared participating category, writing beneath it must
change it. A gate asserting only the first half would pass against a fingerprint
function that had degraded to the empty-tree constant — which is precisely the
historical defect. Both halves are required.

**R17 — The two opt-in retention fields are not alike, and R6's role set gains a
fifth member.** Re-checking them against R6's own two questions, as the escape
test demands, splits them (research F19):

- `cadrumo_registry_disk_cache_dir` **enrolls**. When unset the application
  itself picks `<root>/cache/registry` and writes the compiled pickle there, so
  it chooses and writes and passes both questions. Its `None` default is an
  override affordance, not the absence of an application-chosen location. It
  enrolls under R4's opt-in-override discriminator: the **name** is
  taxonomy-governed, which deletes the hand-written literal in the loader cache,
  while the **field** is deliberately not auto-derived by the settings
  validator, because the three-branch resolver depends on the field being `None`
  to select its pytest branch. Governing the name and auto-deriving the field are
  separate decisions and this member takes only the first.
- `cadrumo_wallet_diagnostic_dump_dir` **escapes**, but none of R6's four roles
  fits: unset, the feature is off and there is no application-chosen location;
  set, the operator names the destination. `ExternalPathRole` therefore gains
  `OPERATOR_DIRECTED_OUTPUT` — a destination the operator names for output the
  application writes on request. R6's original four-role list was incomplete,
  and this is the correction that re-checking surfaced.

This supersedes the sentence in R6 that grouped both fields as opt-in overrides
reading as oversights. The general lesson holds and is the reason the escape
test is written as a test rather than a list: applying it to a real field
changed the answer.

**R18 — Sequencing around the peer-held lifecycle fix.** R4 deletes the five
frozensets in `src/cadrumo/core/tests/test_settings_lifecycle_gate.py`, but that
file is red at committed HEAD and a peer holds the active uncommitted fix
(research F13). The order is fixed and not negotiable by an implementer: the
peer's fix lands first, the gate goes green at HEAD, and only then does the gate
rewrite begin. No lane may edit that file before the peer's commit lands, and no
lane may "helpfully" add the three missing classifications itself — that is the
peer's in-flight change and duplicating it produces a collision on the most
load-bearing gate in this campaign.

## Rationale

The knockout criterion for the representation is research F11. Every option that
leaves the bucket-layout names in `adapters/` leaves the three duplicate copies
in `core/` unfixable, because closing them would require an upward import the
architecture forbids — so the best such an option can achieve is a parity gate
pinning a duplication it cannot remove. Once the names must move core-ward to be
deduplicated, and the closed-value-set mandate independently requires the enum
to live in `core/`, unification is forced rather than chosen. What federation was
protecting — the non-overridability of bucket layout — survives as a declared
field, and is strictly better expressed that way: a guarantee that holds because
a constant sits in a module nobody can import is not a guarantee anyone can read
or enforce.

The gate ruling follows the same measurement. F2 shows a literal census matches
only a syntax the offenders do not use and skips tests entirely, while F1 shows
every offending site begins by reading the root. Provenance is therefore not one
reasonable gate design among several; it is the only shape that reaches the
actual defect class, and it extends to tests without modification.

R4 is the ruling most likely to be got wrong by an implementer optimising for
tidiness, which is why F12's measurement outranks the argument that would
otherwise win. Folding the frozensets into the enum reads as obvious cleanup and
leaves a green suite while quietly dropping seven fields from the gate's
coverage and deriving the fingerprint-exclusion set from an axis that does not
predict it. The three-axis model is less elegant and is what the data supports.

O3 wins over O4 on blast-radius honesty rather than taste. Both are permitted
under the pre-release regime; O4 spends a full migration of every non-cache
directory to buy symmetry that F5 shows was deliberately declined once already.
Separating representation from layout also keeps this campaign's own risk
legible: if the enrollment burndown goes wrong, nothing on any operator's disk
has moved.

The refuse-and-instruct ruling on relocation is the one place this decision
offers the operator less than it could. The trade is asymmetric: the gain is
convenience on a rare operation, the loss on failure is encrypted taxpayer
records separated from the key material that opens them.

## Consequences

The operator gains a truthful answer to where data lives, enumerable before
anything is written, and a reclaim path that cannot delete evidence a filing is
defended with. Path provenance becomes one readable fact rather than a property
distributed across four modules and three duplicate literals, and a new location
cannot enter the tree — from production or from a test — without failing a gate
on the line that introduces it.

The costs are real and larger than the original framing implied. Moving the
bucket and keystore names into core touches the most security-sensitive code in
the product, and while no behaviour changes, the diff is broad. The scope axis
is genuine added complexity a top-level-only authority would not carry; research
F1's name collision at differing depths is why it is not optional. The test
migration is the larger half of the work — 201 files call `override_settings`,
with an untriaged tail — and R14's re-expression requirement means it cannot be
done mechanically without review judgement on every pinning test. Deleting the
lifecycle frozensets moves a hand-curated classification into production
declarations, where a mistake is a mistake in code.

Coordination cost is unusually high. Four files central to this campaign are
peer-owned in the working tree right now, and the lifecycle gate is red at
committed HEAD with its fix in flight. The campaign ratifies three corrections
rather than authoring them, which is cheaper but demands the plan sequence
around work it does not control.

Two items are inherited rather than created: research F7's two writer-less
categories become a wire-or-delete decision once the liveness gate makes them
loud, and the missing root-permission-bits test is added here because a refactor
could otherwise drop the hardening silently.

This opens a path deliberately not taken: once every location is a typed member
with a declared override policy, per-category overrides for members that lack
one, and a genuinely safe relocation built on the substrate's own atomic
primitives, both become tractable. Both are later decisions with their own
accounting.

One visible behaviour change ships with R16: `db_sha256` will differ from its
pre-campaign value on any machine holding a compiled registry cache, because
that cache stops participating in the digest. Recorded run traces stamped before
the change will therefore refuse replay once, which is the drift-refusal
mechanism working as designed rather than a regression. The alternative —
leaving a regenerable cache in the digest — is a permanent low-grade churn that
makes every replay refusal untrustworthy. This is called out because the
symptom (digests moved) looks exactly like the failure the same mechanism exists
to catch, and an implementer seeing it must not reach for parity with the old
eight-field set.
