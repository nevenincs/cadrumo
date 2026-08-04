---
tags:
  - '#adr'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:8b3385c7a7b9ed9570d4d184579e12778f6497c500e25bede60fcb3472e87f73'
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
- The two isolation tiers survive verbatim and migrate differently; see R15.
- **No lane anywhere may add a `Path`-typed `Settings` field until the lifecycle
  gate is rewritten.** The gate discovers by walking `Settings.model_fields`, so
  any new path field is unclassified on arrival and reds it — and that file is
  peer-owned and fenced, so the classifying edit cannot be made in the same
  commit. This is a repository-wide sequencing constraint, not a
  campaign-internal one: it blocks the corpus-search enrollment, it blocks
  retiring the derivation dict (the fenced file imports it in five places), and
  it silently blocks any unrelated feature that would introduce a path setting.
  The gate rewrite is therefore on the critical path for more than this campaign,
  and it should be sequenced first rather than treated as cleanup that follows
  the taxonomy.
- **Path fields stay flat-introspectable on `Settings`, and this is a design
  constraint with a stated reason, not an accident.** The lifecycle gate
  discovers its subject structurally, by introspecting `Settings.model_fields`.
  If the typed taxonomy moves path fields off flat attributes, that discovery
  finds fewer fields — or none. The precise hazard is conditional and worth
  stating exactly, because at HEAD it does not exist: today a shrinking field set
  makes the gate's stale-entry assertion (classified names that no longer exist)
  fire, so the gate reds. **After R4 rewrites classification to derive from the
  taxonomy, both sides of that comparison move together**, and a discovery that
  finds nothing compares empty against empty and passes vacuously. The
  independent oracle disappears at exactly the moment the gate stops
  hand-maintaining its own list. Lane A therefore keeps path fields flat and
  introspectable, and Gate 2 carries a non-empty-discovery assertion as its
  positive control so the vacuous pass is impossible regardless.
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

**Amendment — a read of a bound path field satisfies enrollment.** The affirmative
sentence above says *produced by that accessor*, and the five disqualifiers do not
mention reading `settings.cadrumo_X_dir`. A field read therefore fell in a gap: not
the affirmative case, not excluded. It was measured, and the gap is real. At
`2698a73774`, enumerated with the predicates below so the counts are reproducible
rather than quoted:

```
git grep -lE '\.cadrumo_[a-z_]*_dir\b'                       -- 'src/cadrumo/**/*.py' | grep -v tests
git grep -lE '(^|[^_a-zA-Z])(bucket_scoped_)?storage_path\(' -- 'src/cadrumo/**/*.py' | grep -v tests

candidate pool                21
prose-only (a mention, not a use)   3
REAL field readers            18
accessor modules per R5        9   -- storage_path( 8, bucket_scoped_storage_path( 4, either 9
overlap                        1   -- adapters/persistence/storage/master_key/_master_key.py
```

**The accessor set is 9, not 8, because R5 says so**: its own first sentence names
`storage_path(category)` *and* "a scoped variant [that] takes the bucket
identifier for per-bucket members". The scoped call is part of this contract, not
a separate thing.

**The one overlap is a legitimate dual-door module, not adoption failure**, and it
is the more useful fact. `master_key/_master_key.py` reads the field at `:293` and
`:1154` because `SECRETS` is operator-overridable — resolving it through
`storage_path()` would silently disagree with an operator's override — while its
`bucket_scoped_storage_path()` call at `:771` reaches a different location
entirely. **The accessor has a stated limit**, and this module sits on it
deliberately.

Left unruled, the two available readings change what "done" means by roughly a
factor of two.

*The figure took four attempts and the failures are instructive, so the counts
above should be recomputed rather than quoted.* A first pass gave `5` from an
import-form pattern that missed a name at end-of-line with no trailing comma; a
second gave `5 + 21 = 26`, a sum of overlapping samples presented as a
population; a third gave 8 / 24 / 1 overlap by counting **file presence**. The
last was still wrong: three of those 24 mention a field only in a Sphinx
`:attr:` role, and one of the three is `core/observability/_store.py`, whose
docstring records that it resolves through the accessor **rather than** by
reading the field. **A mention is not a use, and the prose asserted the negation
of what matching it implied.**

**A fifth attempt then failed in two new ways at once, and it was the
correction.** It reported 8 / 21 / disjoint. Both errors are worth naming because
neither was carelessness:

- **`21` inherited a superseded base.** `24 − 3` and `21 − 3` remove the same
  three prose-only modules from different starting pools; the pool was `21`, and
  a corrected enumeration had landed minutes earlier. **A correction can be
  arithmetically sound and still wrong, by being applied to a stale operand.**
- **"disjoint" removed a false overlap without looking for a real one.**
  Discovering `_store.py` was not the overlap is not the same as establishing
  there is none — and there is one. The accessor set had been drawn as
  `storage_path(` alone, narrower than **this ruling's own first sentence**
  defines it, so the module that calls only the scoped variant fell outside it.

**Eight attempts, each smaller than the last.** The list is here so a reader does
not quote the figure: **recompute it.** Its instability is not noise in the
underlying fact — the ruling never depended on the ratio — it is a property of
measuring names in a codebase that reuses them, and it is the same lesson the
`SensitivityClass.AUDIT` collision teaches from the gate side.

**Ruling: a read of a `Path`-typed `Settings` field bound to a taxonomy member is
enrolled.** Not by preference — by two gates that make the field a taxonomy-governed
door rather than a second authority:

- `test_storage_binding_gate.py` proves every `Path`-typed field is a taxonomy
  member, a declared escape, or the storage root — **total and disjoint**. Its
  discovery is anchored to `Settings.model_fields`, deliberately *independent* of
  the taxonomy; the gate's own docstring records why, since a field set sourced
  from the taxonomy would move in lock-step and an empty discovery would compare
  empty against empty and pass.
- `test_storage_default_parity.py` pins each field's placeholder default to the
  taxonomy's declared subpath.

So the accessor and the field are two doors onto one declaration, and **only
re-typing a segment escapes** — which is what the five disqualifiers already
describe and what `S78` burns down. This clause states explicitly what R6's
enrollment-unit logic implied and R5's first sentence did not admit.

**Consequence, so the clause is not read as more than it is.** Accessor adoption
is a **style** question, not an enrollment one; the ratio above is hygiene and
must not be reported as outstanding enrollment work. And the parity gate makes the
duplicate **safe, not single** — a subpath is still spelled in two places, it
simply cannot drift. That residual belongs to `S114`, not to this contract.

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
- `check` — verifies the tree against the taxonomy. Read-only; reports, never
  repairs. **Its reach is narrower from the command line than this ruling
  originally implied, and the narrowing is correct.** The CLI materialises the
  declared tree during bootstrap, before any verb runs, so two of its four
  findings cannot arise through the CLI: a *missing* directory is created by
  bootstrap, and an *occupied* path makes bootstrap refuse first, naming the
  path. What survives to `check` through the CLI is a directory sitting where a
  file-valued member's leaf belongs — which passes precisely because the
  materialiser creates that member's parent and not its leaf. All four findings
  remain reachable in-process and are covered at the service layer.
  This is a condition *resolved*, not a finding suppressed: self-healing beats
  reporting where the remedy is safe and automatic, and an occupied path already
  produces an operator-facing refusal, so reporting it again would make `check` a
  second voice for one condition. `check` is therefore not the general drift
  detector for the tree; it is the reporter for the drift bootstrap does not
  already resolve or refuse.
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

**R9 — The enforcing gate.** The property is provenance, not census — but it
shipped narrower than this ruling's first wording claimed, and the narrowing is
correct rather than a shortfall. The originally-stated property, **the storage
root has exactly one reader**, is a post-burndown property: it cannot hold
until every ad-hoc site is enrolled, and a gate red at HEAD by dozens of
legitimate reads gets allowlisted into meaninglessness or deleted. What shipped
instead is **location production**: a structural AST test asserting that the
storage root is *joined onto* — via `/`, `joinpath`, `glob`, `rglob`, `iterdir`,
or a `Path(...)` wrapper, following the root through a function-local rebind —
only inside a declared producer. Reading the root as the root (handing it to a
disk-usage walker, reporting it, scanning beneath it) produces no location and
is not a finding; at time of writing 68 such reads exist and every one is
legitimate. Every ad-hoc site research F1 found begins with exactly the join
access, so a gate on join-production reaches the paths a literal-matching gate
structurally cannot, with no count, no vocabulary list, and no per-file
allowlist to drift over the property it actually asserts. The narrower property
is recorded in the gate's own module docstring, not only here, because a gate
that quietly covers less than its ruling implies is how a campaign believes
itself finished before it is.

A second, different property is deliberately **not** covered by this gate at
all: that a test must not hardcode a taxonomy-governed directory or file name.
That is literal vocabulary, not join provenance, and it lives in the
settings-lifecycle gate, which scans production modules only — extending it
across the test corpus is its own burndown (see R14, R15). Neither gate
subsumes the other: a literal scan cannot see a path built by joining, and the
provenance gate cannot see a name spelled out in full.

**The gate covers tests.** A test that hardcodes a taxonomy-governed directory or
file name fails CI exactly as production code does;
`test_storage_route_classification.py`, which restates the same two names in five
assertions, is the worked example it must catch. The gate is AST-structural, not
a name census, because research F2 records a docstring that mentions a field
precisely to say it is not used — a counting gate inherits that false-positive
class.

Three gates support it. A materialisation-parity gate asserts the tree
materialiser's target set derives from the taxonomy rather than a parallel list.
A binding gate asserts every `Path`-typed settings field is bound to a member or
declared an escape with a role — enumerating all 35 fields per R4. A liveness
gate asserts every member has a production consumer or is explicitly declared
dormant with a reason, turning research F7's two writer-less categories — which
measurement later widened to four (audit found `status-cache`, `storage-backup`,
`inbox`, and `inbox-pdf`) — into a decision someone must take.

**The liveness gate's evidence shape was extended beyond this ruling's original
spec, on measurement, and the extension is the most consequential
implementation finding of this campaign.** A claim is satisfied by an
`ast.Attribute` load of the bound settings field, an `ast.Attribute` load of
the category member, **or the field name as a non-docstring string
constant** — a third shape this ruling did not anticipate. Without it, two live
categories holding regulated AEAT filing evidence (the IVA read-evidence roots)
would have reported writer-less: both reach their settings through
`_resolve_live_output_root(output_root, "cadrumo_iva_read_evidence_dir")`, the
field named as a string and resolved dynamically, invisible to an
attribute-only walk. Acting on that false report deletes a live category
holding regulated filing evidence. Admitting the third shape must not re-admit
the trap the docstring exclusion already closes: `core/auth_session_keys.py`
names a settings field inside its own module docstring precisely to record
independence from it, and a docstring is also an `ast.Constant` — the two are
distinguished structurally, every docstring node collected and excluded by
identity, not by an allowlist entry.

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

**A gap in "enforceable" was found on review, and is not yet closed.** The gate
proving this guarantee (`test_bucket_and_keystore_layout_is_fixed_not_operator_overridable`)
asserts only that today's `FIXED` members happen to carry no `settings_field` —
there is no `settings_field` on a fixed member, so nothing on
`Settings`/`override_settings` can reach it, and the assertion is structurally
true by that absence. It does not refuse the combination itself: the pydantic
model permits a `FIXED` member with a `settings_field`, and if one is ever
declared, the operator-override guarantee this ruling exists to state would
quietly stop holding for the member it names while the existing gate kept
passing — it would simply be asserting a fact about a different, still-field-less
set of members. This is currently enforced by absence, not by a guard. A
declaration-time validator refusing `override_policy=FIXED` paired with a
non-null `settings_field`, with a positive control that an `OPERATOR_OVERRIDABLE`
member carrying a field is not flagged, is tracked as a plan Step and not yet
built.

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
them, so `StorageScope` is a required field and members are identified by scope
and name together. The collision is not ruled acceptable-and-ignored: it is
ruled expressible.

**The scope enum shipped with four members, not the three this ruling first
declared, and the addition closed a real defect rather than a cosmetic one.**
`StorageScope` is `ROOT`, `BUCKET_RELATIVE`, `KEYSTORE_RELATIVE`, and
`KEYSTORE_ROOT`. The first cut declared only `KEYSTORE_RELATIVE` for every
keystore-scoped member, including the keystore's own root directory, and the
scoped accessor resolved it as nested beneath the owning bucket
(`buckets/<bucket_id>/keystore/<subpath>`) — contradicting
`validate_keystore_separation`'s own requirement, unchanged since before this
campaign, that a bucket's keystore live at `keystore/<bucket_id>/` as a sibling
of `buckets/`. `KEYSTORE_ROOT` names the keystore directory itself, anchored at
the storage root; `KEYSTORE_RELATIVE` now names only what nests beneath that
anchor. See R23 for the correction record.

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

**Amendment — the executing convention differs from this ruling, and the
convention is ratified.** Six lanes converged on a shape this ruling does not
describe: **keep the pinned literal at the assertion, and declare it deliberate**
via a module-level `PINNED_TAXONOMY_LITERALS` frozenset naming the taxonomy
vocabulary that module pins on purpose. It is in **27 test modules** and appeared
**nowhere in `.vault/`** until this clause — a convention at that spread, absent
from the decision record, is precisely the drift this pipeline exists to prevent.

**The two designs differ on one axis: where the oracle lives.** This ruling puts
it at the declaration — the test asserts against the taxonomy's resolved value,
and a declaration-side gate defends the name. The convention keeps it at the
assertion — the test retains the literal, and the declaration-side gate exists in
addition.

**Ratified in the convention's favour**, on the reasoning this campaign already
accepted elsewhere. `DERIVED_OUTPUT_SUBPATHS` in `test_output_dir_state_root.py`
duplicates the taxonomy's subpaths **deliberately**, because an oracle derived
from the thing it checks is not an oracle; deriving it would make the test assert
the taxonomy against itself. A pinning test carries the identical property, so
re-expressing its literal against `storage_location(...).subpath` would move it
one step toward the tautology this ruling's own second paragraph forbids — the
name half of the assertion would then be the accessor compared with itself, with
only the declaration-side gate left holding the name.

R14's shape is *sound* — the declaration-side gate genuinely exists and is
non-vacuous. But it concentrates the guarantee in one place, and the convention
keeps two independent checks for the cost of one frozenset. **Two oracles is the
stronger design where the property is a literal on-disk name that must not
change.**

**The marker is inert, and this clause says so rather than letting a future
reader assume otherwise.** Measured at `2698a73774`: **32 occurrences, 32 of them
its own declaration, zero consumers.** No gate reads it. It is a comment carrying
a type annotation.

That does not overturn the ratification, but it relocates what is being ratified.
**The literal at the assertion is the defence; the marker records why it is
there.** Anyone citing `PINNED_TAXONOMY_LITERALS` as enforcement would be citing
nothing — the same *declared-versus-defended* confusion this ruling's
anti-tautology paragraph already warns about, in the opposite direction.

*This was nearly ratified as "binding" without checking whether it did anything —
the reasoning was scrutinised and the artefact was not.*

**Binding form.** A pins-by-design literal **may remain at its assertion** when the
module declares it in `PINNED_TAXONOMY_LITERALS` with a docstring stating what the
pin defends. An *incidental* literal still migrates to the accessor, unchanged from
above — the marker is not a general exemption, and using it to avoid a migration is
the failed-migration case this ruling already names. **A pin without the marker is
indistinguishable from an unswept literal**, which is the completeness problem
recorded against `S78`: of the six classification outcomes only `pin` marks itself,
so the marker is the one disposition that leaves the tree self-describing — and
that ledger function is what it provides, in place of enforcement rather than in
addition to it.

**If enforcement is wanted later**, the mechanical form is a gate that reads each
module's `PINNED_TAXONOMY_LITERALS` and asserts every taxonomy-vocabulary literal
in that module is either declared in it or absent. That would make the marker
load-bearing and would close the ledger gap mechanically. It is **not** required by
this clause, and it should not be implied to exist.

**A pin's rationale is per-site and must not be generalised.** A refusal guard —
`assert not (...).exists()` — keeps its literal for a reason unrelated to a
provider or caller choosing the filename: **a wrong path trivially satisfies the
guard**, so the assertion passes while checking nothing. Different mechanism,
different survival condition under refactor, and characterising it with a generic
justification loses the property the pin exists to defend.

**R15 — The two isolation tiers have different dispositions, and conflating them
misdirects the migration.** An earlier wording called the whole chain "the
canonical target". Measurement showed tier one is not a target at all — nothing
migrates to it — and an implementer reading otherwise would try to route call
sites at a layer that has no application imports by design and cannot accept
them.

*Tier one — collection-time bootstrapping. Exempt, untouched, not a target.*
`src/cadrumo/tests/_collection_storage_root.py` and its two conftest callers
point the root environment variable at a process-private temporary directory
**before any import can resolve settings**, so collection never resolves against
a real platform root on a machine still carrying retired-product state. Verified:
the module imports only stdlib (`atexit`, `os`, `shutil`, `time`, `pathlib`,
`tempfile`), sets only the root variable, and names **no taxonomy leaf** — its
single apparent leaf match is the ordinary English word "runs" in prose. It
touches only `cadrumo_local_storage_root`, which the lifecycle gate classifies
as exempt input precisely because it is the container rather than a categorised
child. Its concern — do not resolve settings during collection — is orthogonal
to what lives under the root. It survives verbatim, and nothing migrates onto it.

*Tier two — the shared isolation fixtures. The real migration target, and it
migrates first.* `secure_sql.py`'s `isolated_cli_backend`,
`isolated_profile_storage_root`, `isolated_runtime_profile`, and
`isolated_cli_runtime_profile`, plus `env_scope.py`'s `isolated_aeat_env` and
`settings_without_env_file`, isolate the whole root once per test rather than a
field at a time. That is the right abstraction for call sites to consolidate
onto — **but they currently hand-roll the per-field literals themselves**.
Verified: `isolated_cli_runtime_profile` overrides five fields with bare
literals, one of which (`txs`) disagrees with the taxonomy's own subpath for
that category. So tier two is both the destination and itself a migration
subject, and it goes first: roughly 10 fixture-internal sites, small and
high-leverage, because migrating them is what makes the large sweep coherent
rather than a sweep onto a drifting target.

*Named, and explicitly out of scope.* Beyond those fixtures, roughly 350+ call
sites hand-roll per-field override blocks duplicating what the fixtures already
provide. Mechanically re-pointing each to the accessor satisfies the mandate and
is in scope. Getting them to **use the shared fixtures instead** is better
engineering and is **not** in scope for this campaign — it is a larger design
conversation about fixture ergonomics. The distinction is recorded so the
campaign neither silently expands into that work nor silently pretends the
opportunity does not exist.

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

**Two different counts live under this ruling, and stating only one of them is
what produced three amendments on the same number.** `FINGERPRINT_EXCLUDED_STORAGE_FIELDS`
is keyed by **settings field**, not by taxonomy member — a file-kind leaf
nested under an excluded directory category (a cache's compiled index, a
cache's content file) can itself be a separate excluded *member* while
carrying no `settings_field` of its own, since the field lives on the parent
directory category. **Excluded members** and **excluded fields** are
therefore not the same cardinality by construction, and a ruling that quotes
one number as if it were the other will drift the moment either axis grows
independently of the other.

**Verified at committed HEAD `c16bb9a0ae`: nine excluded members, all nine
carrying a `settings_field`, so both counts currently agree at 9** —
`LLM_USAGE`, `LLM_RUN_TELEMETRY`, `MCP_TELEMETRY`, `RUNS`, `LLM_CACHE`,
`CORPUS_TEXT_CACHE`, `CORPUS_SEARCH_CACHE`, `VALIDATION_VERDICT_CACHE`,
`REGISTRY_DISK_CACHE`. The rise from the original eight to nine is not
drift: two of the nine — `CORPUS_SEARCH_CACHE` and `VALIDATION_VERDICT_CACHE`
— are categories this campaign itself enrolled (R6, R17) that had no
corresponding settings field for the old eight-field tuple to have read in
the first place.

**This agreement is not guaranteed to survive the next declaration, and a
future reader must recompute rather than trust either number here.**
Family 1's file-leaf members (the compiled corpus-search index, the corpus-text
cache file, and comparable file-kind children of an already-excluded
directory category) widen the *member* count without adding a
`settings_field`, so the two counts will diverge again as soon as those land
— correctly, not as drift, for the same structural reason `CORPUS_SEARCH_CACHE`
and `VALIDATION_VERDICT_CACHE` already diverged from the original eight.
**Correction, found on two later honesty reviews**: an earlier version of
this paragraph counted eleven and named `STATUS_CACHE` and `STORAGE_BACKUP`
among them; both were declared dormant and then deleted outright, taxonomy
member and all. A second review then found this ruling stating "nine
members" against a live taxonomy that (in the working tree, mid-declaration)
already carried eleven members against nine fields — the member-versus-field
conflation this paragraph now states explicitly, so a fourth amendment on
the same unstated distinction should not be needed.

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

**R19 — The settings-cache root read is lifted into the pure resolver, not
seamed and not left raw.** `_active_profile_pointer_fingerprint` computes the
cache key for settings construction, so it must answer "which pointer would the
next construction see" *before* any settings exist. It cannot read the root
through `Settings` without circularity, and it currently reads
`os.environ` directly, which no sanctioned technique can pin: the override-seam
singularity gate forbids a second `override_*` seam and the monkeypatch ban
forbids the other route.

**Neither standing rule yields. Both are right, and no amendment is needed** —
the seam gate's own prescription is the answer. It objects to a test double
living in production (a swappable process-global a factory consults) and
explicitly names the alternative: real DI threads the dependency through a
parameter. `StateRootInputs` is already exactly that — a frozen, injectable
record carrying `platform`, `home`, and **`environ`**.

**The fix is to make the unpinnable path stop existing**, by lifting
override-aware root resolution into a pure function over `StateRootInputs` that
applies the precedence the fingerprint currently hand-rolls: the override value
if the environment carries one, otherwise the resolved platform default. The
fingerprint calls it with the live inputs. The raw `os.environ` read disappears,
the path becomes testable by passing synthetic inputs with no seam and no
monkeypatch, and the duplicated environment-variable-name literal that research
F17 flagged as a second independent root-resolution path collapses onto one
owner.

**One correction the implementer must not miss.** Routing the fingerprint
through the *existing* `resolve_state_root` would be a correctness regression,
not a cleanup. Verified: that function resolves only the platform default and
does **not** read the override variable — the override is applied by
pydantic-settings at the `Settings` layer, as its own docstring says. Calling it
from the fingerprint would silently drop the override from the cache key, so a
process with a redirected root would fingerprint the wrong pointer file and
could serve stale settings across a profile switch. That is research F17's
invariant-10 hazard, made worse. The new function must apply the override
precedence itself; it is not a rename of the existing resolver.

The test that becomes possible is the one that matters: construct inputs with
the override set and assert the fingerprint resolves the pointer under the
overridden root, then construct inputs without it and assert the platform
default. Today neither branch is pinned.

**R20 — The retired derivation dict survives as a declared pinning oracle with
a death date.** Production no longer reads `_STATE_ROOT_DERIVED_DIRS`; it is
retained solely so the on-disk-name pinning test keeps an oracle independent of
the taxonomy it checks. Deriving it from the taxonomy would make that test
assert the taxonomy against itself — precisely R14's failed-migration shape,
where a pinning test survives as a tautology.

This is an intentional, temporary duplication and must be labelled as one in
source, naming both its purpose and its retirement point, so a future reader
neither deletes it as redundant nor "converges" it as duplication. It is
explicitly **not** a counter-example to the campaign's own no-duplicate-authority
ruling: an independent oracle for a gate is a different category from a second
production authority, and the distinguishing test is whether production reads
it. Production does not.

Its retirement was blocked by the same coupling that blocks new path fields (see
Constraints), and was ruled to die when the lifecycle gate was rewritten — not
before, and not by deriving it. **That gate has since been rewritten**: the
hand-curated lifecycle frozensets were retired and classification now reads off
the taxonomy, and the rewritten gate no longer imports
`_STATE_ROOT_DERIVED_DIRS` — confirmed at HEAD, zero references to the name
exist anywhere in `src/cadrumo` outside its own declaration. The blocking
coupling is resolved.

**The oracle role itself relocated ahead of the dict's physical deletion — and
the deletion has since happened too.** `test_storage_taxonomy_parity.py`, the
transitional parity test this dict originally backed, is deleted. Its pinning
property relocated into an independently hand-maintained `DERIVED_OUTPUT_SUBPATHS`
dict inside `test_output_dir_state_root.py` — a separate oracle, not
`_STATE_ROOT_DERIVED_DIRS` renamed or re-exported. `_STATE_ROOT_DERIVED_DIRS`
itself is now confirmed gone from `config.py` and from every other file in
`src/cadrumo` — the dict's own death-date sentence is closed, not merely
unblocked. Verified independently at committed HEAD, not taken from a report:
`git show HEAD:src/cadrumo/core/config.py | grep _STATE_ROOT_DERIVED_DIRS`
returns nothing.

**R21 — `config storage` is bootstrap-exempt, so `reclaim` rests on one guard,
and that guard carries a standing condition.** The family sits in the
bootstrap-exempt verb paths, not the profile-bound guarded catalogue. Two
measured reasons, both verified:

- Guarding it would break the surface's own purpose: `init` exists to
  materialise the tree on a machine that has none, and a profile-bound guard
  makes it refuse exactly there — a bootstrap verb failing at its only job.
- The entry would never be read anyway. `inspect_storage_write_policy` returns
  `BOOTSTRAP_EXEMPT` and returns *before* it consults the guarded catalogue, so
  a catalogue entry for a bootstrap-exempt path is unreachable. **A dead
  allowlist entry that reads as protection is worse than no entry**, because a
  later reviewer checking "is `reclaim` guarded?" finds the name and stops.

The consequence must be stated rather than left implicit: **`reclaim` is
protected by its lifecycle refusal alone, not by two independent guards.** That
single guard therefore carries a standing condition — a containment proof that
with no active profile, no category `reclaim` accepts resolves inside a bucket,
keystore, or financial-sensitivity location. The proof must be **derived from
the declared axes rather than listing today's members**, so a future member
declared prunable at bucket scope cannot silently join the accepted set. A
listed set would pass forever while the real risk changed underneath it.

**R22 — When one surface pre-empts another, pin the pre-emption.** R7's `check`
correction exists because a first test asserted a condition the CLI can no
longer reach, and failed with a key error. The discipline that produced the
finding is the part worth generalising: the implementer **traced the failure
instead of adjusting the assertion to match observed output**. Adjusting it
would have produced a green test named for `check` that actually exercised the
bootstrap refusal — a test measuring a different mechanism than its name claims,
and invisible in review precisely because it is green and plausibly named. That
is the same failure family as R14's tautological migration and R16's one-sided
gate: an assertion that passes for a reason other than the one its name asserts.

So the rule: where one surface pre-empts another, **pin the pre-emption
itself**, not only the surviving behaviour. Relocating materialisation out of
bootstrap then reds loudly instead of silently redistributing which surface
answers a condition — a redistribution that would otherwise leave every existing
test green while the operator-facing behaviour changed. This applies well beyond
storage: any self-healing or refuse-early layer in front of a reporting layer
has the same shape.

**R23 — The keystore-scope defect, found on review, was real and is now
closed.** This ruling was added to record a genuine implementation defect:
`StorageScope` shipped with `KEYSTORE_RELATIVE` alone, and the scoped accessor
resolved a bucket's keystore nested beneath it rather than sibling to
`buckets/`, contradicting `validate_keystore_separation`. **The fix has since
landed** — adding `KEYSTORE_ROOT` (R13, amended in the same pass as this
ruling), with an anti-regression guard: the accessor test that once pinned the
wrong nested shape as expected now asserts the sibling shape and carries a
positive control that feeds the still-live separation validator a nested path
to confirm it still refuses. This ruling is retained, superseded, rather than
deleted, so the audit trail shows what R13 as originally written got wrong and
how long it took to close — from this ADR first recording the defect to the fix
landing was within the same execution day. Two plan Steps that depend on this
fix — re-pointing `bucket_paths` and `keystore_path` onto the corrected scoped
accessor — remain open.

## Implementation Amendment Log

This ADR was amended six times during execution before this audit pass, and
twice more by it (once to record the keystore-scope defect as R23, once again
within the hour to record its fix). Several rulings were **overridden by
measurement during implementation, correctly** — the record is worth keeping
because it is where this campaign's best findings live: R9's provenance gate
shipped narrower than its first wording (location production, not universal
readership, with the liveness gate's evidence shape independently extended on
measurement to avoid deleting live regulated evidence); R12's
cancel-then-refetch ratification was withdrawn on measurement that a
`.crdownload` file existed on disk before `cancel()` could act; R13's scope
axis shipped with four members instead of the ruling's original three, closing
a real keystore-nesting defect rather than a cosmetic gap (R23 records the full
arc, including that an earlier version of the accessor's own test had pinned
the wrong nested shape as correct — the clearest evidence in this campaign that
a green suite is not a claim about correctness); R16's fingerprint-participation
axis went through three amendments on one number (eight, then eleven, then
nine) before a second self-duplication review found the actual root cause —
the ruling conflated excluded *members* with excluded *settings fields*,
two different cardinalities by construction — and R16 now states both counts
and why they can diverge again rather than a single number; R17 split two
superficially-similar opt-in fields and added a fifth `ExternalPathRole`; R19
resolved an apparent standing-rule conflict by lifting root resolution into a
pure function rather than amending either rule; R20's retirement blocker
resolved and its retired dict is now confirmed physically deleted, not merely
unblocked; R10's `FIXED`-override guarantee was found, on review, to be
enforced by absence rather than by a guard. Each is stated above at its own
ruling, in place, rather than collected here — this log exists only to name
that the correction discipline itself was followed repeatedly, not once.

**Post-audit addendum**: a fresh-context honesty review found this ADR's own
R16 correction had drifted again — stated as eleven at the point this log was
written, nine after `S74`'s dormancy deletion removed two of the eleven named
members — and that R13's scope-member count in this same log undercounted
(three, not four). Both corrected in place above rather than only here,
consistent with this log's own stated purpose: name that the correction
discipline was followed, not just once.

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
