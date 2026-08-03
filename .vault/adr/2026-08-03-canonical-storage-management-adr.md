---
tags:
  - '#adr'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:d899c0b2300fe677c109dff95794d17e9013729abc510bab753f14d26583a982'
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
name, a set of bare string constants in the persistence namespace registry that
owns the two most security-load-bearing directories in the tree, module-local
constants in three application and entrypoint modules, and inline literal
duplicates of the registry constants in two core modules that no parity test
pins. Finding F2 establishes that the existing anti-literal gate matches only
slashed literals inside a `Path(...)` call, so every one of those sites is
built by an operator join it structurally cannot observe.

The consequences are already visible rather than hypothetical. Two declared
categories have no production writer at all (F7), repeating a
declare-but-never-wire failure the prior campaign paid to clean up twice. The
file-versus-directory distinction rides a field-name suffix rather than a type
(F4). The lifecycle classification that governs whether a directory may ever be
pruned lives in five hand-maintained frozensets inside a test module, where no
production consumer can read it (F3). An operator has no way to ask the
application where its data lives, what is in each location, or what may safely
be reclaimed (F9).

A decision is needed now because the operator's standing goal is a canonical
storage management API plugged into a `config storage` surface, with every code
site and API migrated. That work cannot be scoped, and its burndown cannot be
mechanically checked, until the authority's shape, its membership test, and its
enforcing property are fixed.

## Considerations

- The closed-value-set mandate in `aeat-architecture-boundaries` binds directly:
  a closed set must be a `StrEnum` in `core/`, production code and CLI handlers
  must accept and emit enum members rather than raw strings, and a Typer
  argument over a closed enum must declare that enum so the accepted set is
  rendered on parse failure.
- `2026-07-13-data-output-standardization-adr` is accepted and rules on
  locations and lifecycle while being silent on Python-level representation
  (research F8). Its Option O2 — one root with a category taxonomy beneath it —
  is what a typed authority formalizes. Its Option O3, a platformdirs-style
  multi-root split, was explicitly rejected and must not be resurrected.
- `cadrumo.core.COMPATIBILITY_REGIME` is `PRE_RELEASE` (research F8), so
  `no-legacy-compatibility` governs in full: the old surface is deleted rather
  than bridged, and an on-disk layout change is permitted. Permitted is not
  obligatory; the blast radius of moving directories is far larger than the
  blast radius of typing their declaration.
- `sensitive-financial-data-secure-storage-only` governs what lives inside the
  encrypted substrate. This decision governs where on disk everything lives,
  encrypted or not. The word "storage" carries both senses in this codebase and
  the two must not be conflated: naming the directory the encrypted substrate
  occupies is not exposing its contents.
- `cli-notices-are-the-only-diagnostic-channel` and the envelope conformance
  gates (research F9) constrain any new verb's result shape before it is
  designed, not after.
- A gate whose pass condition is a hardcoded count rots on the next ordinary
  change. The enforcing property must be structural.

## Considered options

- **O1 — Type the settings dict only.** Replace `dict[str, str]` with a
  `StrEnum` plus a mapping, leave the namespace registry, module constants, and
  inline literals alone. Cheapest and lowest risk, but research F1 shows it
  governs roughly half the tree while leaving `buckets/` and `keystore/`
  untyped, and F2 shows the gate would still be blind to exactly the sites left
  out. Rejected: it produces a typed authority that is not the authority.

- **O2 — One typed category authority over every application-chosen location,
  on-disk layout unchanged.** A `StorageCategory` `StrEnum` in `core/` with a
  frozen per-member declaration carrying subpath, node kind, lifecycle class,
  scope, and optional settings-field binding; every location in research F1
  absorbed as a member; escapes declared rather than merely absent; a resolver
  that is the sole reader of the root. **Chosen.**

- **O3 — O2 plus a uniform structural path prefix.** Give every category a
  `<grouping>/<name>` on-disk shape, making `cache/` no longer exceptional.
  Structurally tidier, and permitted under the pre-release regime, but research
  F5 shows the current asymmetry is deliberate and documented, and this would
  move every non-cache directory on disk for a cosmetic gain while multiplying
  the migration surface across bucket provisioning, keystore resolution, and
  every test-isolation fixture. Rejected.

- **O4 — Multi-root split per category.** Already rejected as Option O3 of
  `2026-07-13-data-output-standardization-adr`; restated here only to record
  that this decision does not reopen it.

- **O5 — Runtime path registry populated by decorator at import time.** Modules
  self-register their locations. Attractive because declaration sits beside
  use, but it makes the inventory depend on import order, unavailable to a
  static gate, and unenumerable before the application is running — which
  defeats the operator question the CRUD surface exists to answer. Rejected.

## Constraints

- The lifecycle gate in core config tests must not be broken or bypassed. Its
  properties — total coverage, pairwise disjointness, and derived-or-opt-in
  defaults — are preserved by construction under this decision rather than
  discarded, and it is rewritten in the same commit as the authority lands.
- The relocation-atomicity rule applies: the canonical-site move, every
  consumer update, and every gate update share one commit, with clean
  collection observed immediately before it, and a `relocation:` commit subject
  tag.
- Two tests in core config tests are red at HEAD independently of this campaign
  (research F10), asserting a repository-root anchor that the relative-path
  anchor deliberately no longer implements. They sit on this axis and will be
  attributed to it. They are in scope: this campaign either corrects them to the
  implemented anchoring or records them as a named known-red with an owner. It
  may not leave them ambiguous.
- The registry disk cache resolves through a three-branch resolver whose pytest
  branch deliberately uses the host-shared OS temp directory for cross-worker
  sharing of an immutable bundled tree (research F5). Its production branch
  enrolls; its pytest branch is a declared exception and must not be
  "corrected" into the taxonomy.
- Settings construction is cached because path resolution is expensive on
  Windows. No filesystem probe may be added to settings construction or
  validation; inspection reads already-resolved paths.
- Every new operator-facing string needs locale keys in all four catalogues
  through the locales CLI, and the CLI reference is regenerated, never
  hand-edited.

## Implementation

**R1 — The typed representation.** A `StorageCategory` `StrEnum` in
`cadrumo.core` names every application-chosen location, and a frozen, strict
pydantic `StorageLocation` model carries the axes a bare member cannot: the
literal POSIX relative subpath, the node kind, the lifecycle class, the scope,
and the settings field that overrides it where one exists. One
`STORAGE_TAXONOMY` mapping keyed by the enum is the single declaration. The
enum is required rather than optional because the CLI boundary mandate needs a
closed type to render the accepted set, and because production code must pass
members rather than strings; the sidecar model is required because a `StrEnum`
member cannot carry five axes without becoming a string that encodes them.
Neither half alone satisfies both mandates, which is why the answer is both and
not one.

Membership spans every location in research F1, not the settings dict alone.
Categories that are per-bucket or per-keystore rather than top-level carry a
`StorageScope` distinguishing them, because research F1 records that `blobs`
and `audit` each name both a top-level directory and a per-bucket subdirectory
at different depths; a flat name-keyed structure would collide two real
directories onto one member. Members bound to a settings field keep their
environment override exactly as today; members with no settings field — the
bucket and keystore layout, the pointer file, the corpus-search index, the MCP
telemetry directory — gain a typed declaration without gaining an override,
which is a deliberate narrowing left to a later decision rather than an
oversight.

**R2 — File versus directory is an explicit typed field.** `StorageNodeKind`
is a `StrEnum` of `DIRECTORY` and `FILE`, declared per member. The
`field_name.endswith("_path")` inference in the tree materialiser is deleted,
not retained as a fallback. Research F4 records that the suffix convention is
untyped and that the namespace registry holds six file names no suffix governs;
inference cannot reach them and would silently create a directory over a file.

**R3 — The `cache/` prefix asymmetry is preserved, and no path moves.** Each
member declares its literal relative subpath verbatim as it exists today.
The conceptual grouping — state, cache, logs, exports — is a separate declared
field with no effect on the resolved path. This decision changes the Python
representation and the enforcing property; it changes no on-disk location. Any
future layout change is a separate decision with its own blast-radius
accounting. The pre-release regime would permit stranding local data, and this
decision declines to use that permission, because research F5 shows the
asymmetry is deliberate and the gain from uniformity is cosmetic.

**R4 — The lifecycle class folds onto the member.** `StorageLifecycle` becomes
a required field on `StorageLocation`, carrying the five existing classes.
The five hand-maintained frozensets in the gate are deleted; the gate is
rewritten to derive classification from the taxonomy, so total coverage and
pairwise disjointness hold by construction rather than by assertion over
hand-edited sets, and the remaining assertions become the ones that can still
fail: that every path-typed settings field is bound to a member or declared an
escape, and that a non-exempt output derives from the root or is an opt-in
override. The domain rationale currently living in test-module comments — why
live read-evidence must never be pruned, why the corpus-text cache is bounded —
moves onto the declarations, where production code can read it. Folding rather
than leaving it orthogonal is what makes the axis load-bearing at runtime:
R7's reclaim verb refuses on lifecycle class, which is only possible if the
class is data rather than a test fixture.

**R5 — The enrollment contract.** One accessor, `storage_path(category)`,
returns the resolved absolute path for a member; a scoped variant takes the
bucket identifier for per-bucket members. `ensure_storage_tree` materialises
the full member set derived from the taxonomy, with no second list to keep in
step. A site is enrolled when the location it uses is produced by that
accessor. A site is not enrolled when it does any of the following, and these
are the mechanical test a burndown agent applies to get a yes or no without
judgement:

- reads `cadrumo_local_storage_root` and joins anything onto it;
- names a child of the root, at any depth, by string literal or module-local
  constant;
- calls `Path.home()`, `expanduser`, or a platform-directory lookup to derive a
  location rather than to normalise a path it already holds;
- creates a directory whose name came from anywhere but a taxonomy member.

The last clause is what catches the class research F2 shows the current gate
misses, because those sites build paths by join rather than by literal.

**R6 — Escapes are declared, not merely absent.** A path-valued setting stays
outside the taxonomy only when it fails one of two questions, and the pair is
the principled test that keeps the exception list from rotting: does the
application *choose* this location, and does the application *write data*
there? Both yes means it enrolls. Research F6 sorts the current escapes:
bundled read-only package resources and operator-supplied credential paths fail
the write test; third-party-owned caches and external executables fail the
choose test. Each escape is declared through an `ExternalPathRole` enum on the
settings field — bundled resource, operator input, third-party cache, external
executable — so that an escape is a positive statement carrying its reason
rather than an absence from a frozenset. `cadrumo_libreoffice_executable`, which
research F6 records as classified nowhere and invisible to the gate's own field
selector because its name carries no recognised suffix, is declared an external
executable, and the field selector widens from name-suffix matching to
`Path`-typed annotation so no future field can hide from classification by
being named inconveniently.

**R7 — The CRUD surface.** `config storage` registers as a
`LIFECYCLE_OPERATIONS_ONLY` noun-group, because an operator cannot create or
destroy a storage category — the member set is fixed by the taxonomy — which is
the same reasoning the apoderado and inventory groups already use. The verbs:

- `list` — every category with its resolved path, node kind, grouping,
  lifecycle class, scope, override binding, and whether it currently exists and
  holds anything. This is the answer to "where is my data", and its
  populated-versus-empty column closes the dormancy question research F7 raises
  by making it visible to the operator rather than discoverable only by audit.
- `show CATEGORY` — one category in full, the category argument typed as the
  enum so the accepted set renders at the boundary.
- `check` — verifies the tree against the taxonomy: missing directories, a file
  occupying a directory's place, a directory occupying a file's place,
  permission drift on the root. Read-only; reports, never repairs.
- `init` — materialises the declared tree, idempotent, the operator-facing form
  of the existing tree materialiser.
- `reclaim CATEGORY` — deletes regenerable content, and refuses on any category
  whose lifecycle class is unbounded-by-design or exempt. The refusal names the
  class and the reason. This is the verb that makes R4's folding load-bearing.

No verb moves existing data, and relocating the root is refuse-and-instruct.
Asked to relocate, the surface reports the current root, the environment
variable that sets it, and the fact that the operator must move the tree
themselves and re-point it. This is deliberate and is the data-safety ruling of
this decision. The tree holds encrypted taxpayer records, the key material that
opens them, and the audit trail over both; a partially-completed copy across
filesystems, or a copy that succeeds while the keystore does not, is an
unrecoverable outcome that no verb should be able to reach by accident.
`sensitive-financial-data-secure-storage-only` makes the substrate's custody
non-negotiable, and a relocation verb is precisely a path that would move it
outside the guarantees the substrate's own primitives provide. An operator with
a shell has a safe, inspectable, resumable way to do this; the application
offers no faster one.

No verb name collides with the reserved vocabulary: `pull` names an AEAT fetch
and `--file` names a single local input file, and neither concept appears here,
so `aeat-cli-pull-and-file-standard` is honoured by not borrowing its verbs for
an unrelated operation.

Every result is a registered strict `OutputSchema` on the envelope spine, with
no bespoke advisory, next, or suggestion field. Diagnostics — an absent
directory, a category with no production writer, a reclaim that freed nothing —
ride the typed notice channel. Operator strings are authored through the
locales CLI in all four catalogues, and the CLI reference is regenerated in the
same commit.

**R8 — Relationship to prior decisions.** This decision **extends**
`2026-07-13-data-output-standardization-adr` and supersedes nothing. That ADR
rules on locations and lifecycle and is silent on Python-level representation;
its Option O2 is what this formalizes, and its rejected Option O3 stays
rejected — every category resolves under the one root. Research F8 records that
the four other accepted ADRs whose stems contain "storage" govern the encrypted
substrate's internals rather than the location taxonomy, so no accepted ADR
conflicts with this one. The operator's standing goal anticipates superseding
conflicting decisions; the finding is that there are none, recorded here
explicitly so a future reader does not go looking for a phantom conflict.

**R9 — The enforcing gate.** The property is provenance, not census: **the
storage root has exactly one reader.** A structural test walks production
modules and asserts that the `cadrumo_local_storage_root` attribute is accessed
only inside the taxonomy resolver. Every ad-hoc site research F1 found begins
with exactly that access — the corpus-search index directory, the MCP telemetry
directory, the inline bucket-database path, the route classifier, the registry
cache production branch, and every caller that passes the root into the bucket
layout helper — so a gate on the root's readership reaches the join-built paths
that a literal-matching gate structurally cannot (research F2). It has no
count, no vocabulary list, and no per-file allowlist to drift; it names one
symbol and one permitted consumer, and a new module that invents a location
fails it on the line where it reads the root.

Three gates support it. A materialisation-parity gate asserts the tree
materialiser's target set is derived from the taxonomy rather than a parallel
list, so a new member cannot be declared without being created. A binding gate
asserts every `Path`-typed settings field is either bound to a member or
declared an escape with a role, replacing the frozenset coverage assertions of
R4. A liveness gate asserts every member has a production consumer or is
explicitly declared dormant with a reason, which is what turns research F7's
two writer-less categories from a silent condition into a decision someone has
to take — and is the structural answer to the concern that a typed member set
otherwise just relocates the declare-but-never-wire failure from dict keys into
enum members.

## Rationale

The knockout criterion is research F2. Any option that leaves the enforcement
property as a literal census is refuted by direct measurement: the existing
gate matches only slashed literals inside a `Path(...)` call, while every
unenrolled site in the tree builds its path by operator join. Tightening that
regex chases a syntax the offenders do not use. Once the gate must be
provenance-shaped — one symbol, one permitted reader — the authority it
enforces must cover every location that symbol can produce, which is what
eliminates O1: a typed settings dict leaves `buckets/` and `keystore/` outside
the authority while the gate would already be flagging their call sites, and an
authority that cannot answer for what its own gate catches is not the
authority.

O2 wins over O3 on blast-radius honesty rather than on taste. Both are permitted
under the pre-release regime. O3 spends a full migration of every non-cache
directory, every bucket and keystore resolution, and every test-isolation
fixture, to buy structural symmetry that research F5 shows was deliberately
declined once already, with the reasoning recorded in the declaration itself.
Separating representation from layout also keeps this decision's own risk
legible: if the enrollment burndown goes wrong, nothing on any operator's disk
has moved.

Folding lifecycle onto the member (R4) rather than leaving it orthogonal is
justified by R7 rather than by tidiness. A reclaim verb that must refuse to
delete live read-evidence needs the lifecycle class at runtime; while the class
lives in a test module's frozensets, that refusal would have to re-derive the
classification, which is how the two axes drift apart in the first place.
Making the class data makes the refusal readable, and makes the gate's coverage
property hold by construction instead of by hand.

The refuse-and-instruct ruling on relocation (R7) is the one place this decision
deliberately offers the operator less than it could. The trade is asymmetric:
the gain is convenience on a rare operation, and the loss on failure is
encrypted taxpayer records separated from the key material that opens them.

## Consequences

The operator gains a truthful answer to "where does my data live" that is
enumerable before anything has been written, and a reclaim path that cannot
delete evidence a filing is defended with. Path provenance becomes a single
readable fact rather than a property distributed across four modules, and a new
location cannot enter the tree without failing a gate on the line that
introduces it.

The costs are real. The enrollment burndown touches the persistence layer's
bucket and keystore resolution, which is the most security-sensitive code in
the product, and R5's contract will flag sites that are correct today and merely
unenrolled — the discipline is to route them, not to rewrite them. Absorbing
per-bucket members forces the scope axis into the taxonomy, which is genuine
added complexity that a top-level-only authority would not carry; research F1's
`blobs` and `audit` name collision is why that complexity is not optional.
Deleting the five lifecycle frozensets moves a hand-curated classification into
production declarations, and a mistake there is a mistake in code rather than
in a test.

Two items are inherited rather than created. The pair of red tests in research
F10 must be resolved or named, and the campaign will be blamed for them
otherwise. The two writer-less categories in research F7 become a decision
someone must take once the liveness gate makes them loud — wire them or delete
them — which is the intended outcome and also unavoidable new work.

This opens a path that is deliberately not taken here: once every location is a
typed member with a declared override binding, per-category environment
overrides for the members that lack one, and a genuinely safe relocation built
on the substrate's own atomic primitives, both become tractable. Both are later
decisions with their own accounting.
