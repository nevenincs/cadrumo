---
tags:
  - '#reference'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:585d46b3d3523c148fb9ca0702ea69b75ad7ca0be65a6f107dca3df7eaefbc39'
related:
  - "[[2026-08-03-canonical-storage-management-adr]]"
---

# `canonical-storage-management` reference: `enforcement gate specifications`

Build specification for the five gates mandated by the campaign's rulings R4,
R5, R9, and R16. These are the difference between the mandate being enforced
and merely asserted, and they can be built against the declared taxonomy
interface before that interface merges.

Every gate below states four things, because a gate specified without all four
is not buildable: the **defect** it catches, the **mechanism**, a **mutation**
that must turn it red, and its **positive control** — what it must *not* flag.
The fourth is the one usually skipped and the one that matters most: a gate that
reddens on everything is as useless as one that never reddens, and in a prior
campaign here three of thirteen verdicts would have been wrong in *both*
directions without positive controls.

Each gate also states why it cannot be satisfied by a tautology. A gate that can
pass by asserting the accessor equals itself is not a gate.

## Summary

### Gate 1 — Provenance

**Defect:** a module inventing a storage location instead of resolving one —
the class that produced the corpus-search directory, the MCP telemetry
directory, and the inline bucket-database path.

**Mechanism.** Parse every production module to an AST. Flag any
`ast.Attribute` node whose `attr` is `cadrumo_local_storage_root`, and any
`getattr` call whose second argument is that name as a string constant. The
permitted readers are a declared set of `(module, function, reason)` entries —
the taxonomy resolver, the settings derivation validator, and the tree
materialiser. The gate additionally asserts every permitted entry still resolves
to a real function, so a stale exemption reds rather than silently widening the
permission.

**Why AST rather than text.** Both known traps dissolve structurally rather than
by allowlist:

- *Name-counting false positives.* Verified: `core/auth_session_keys.py` names
  `Settings.cadrumo_token_dir` inside its **module docstring**, precisely to
  document that the key is deliberately independent of it. A docstring is an
  `ast.Constant`, never an `ast.Attribute`, so an AST attribute walk cannot see
  it. A text scanner must special-case it; this gate cannot produce the error at
  all.
- *Join-built paths.* `settings.cadrumo_local_storage_root / _INDEX_SUBDIR` is a
  `BinOp` whose **left operand is the attribute access**. The gate matches the
  attribute node regardless of what is joined onto it, which is exactly why
  provenance reaches the class a literal-scanner structurally misses.

**Mutation → RED:** add `settings.cadrumo_local_storage_root / "scratch"` to any
production module.

**Positive controls — must stay GREEN:**

1. `auth_session_keys.py`'s docstring mention (proves no name-counting).
2. A module reading a *category* attribute such as `settings.cadrumo_runs_dir`
   (proves the gate targets the root, not every settings path read — without
   this control the gate would flag roughly 100–300 legitimate single-field
   consumers).
3. The declared resolver itself.

**Non-tautological because** the assertion is a negative quantified over every
module *except* the resolver. It cannot be satisfied by the resolver referring
to itself.

### Gate 2 — Binding

**Defect:** a `Path`-typed settings field that is neither a taxonomy member nor
a declared escape — a location with no declared home.

**Mechanism.** Enumerate `Settings.model_fields` and select **by annotation**:
any field whose annotation contains `Path`, including inside a union. For each,
assert membership in either the taxonomy binding map or the `ExternalPathRole`
escape map, and assert the two are disjoint. Also assert no binding or escape
names a field that no longer exists, so the maps cannot rot.

**Annotation, never name suffix — verified in both directions.** Measured
against the live model: suffix-and-Path selects 35 fields, annotation alone
selects 36. The delta is `cadrumo_libreoffice_executable`, which ends in none of
`_dir`/`_path`/`_root` and hid from classification by being named
inconveniently. Separately, a *name-only* selector would over-select
`aeat_sede_expedientes_path` and `aeat_status_notificaciones_path`, both
confirmed `str` — AEAT URL segments, not filesystem paths.

**Report shape.** A failure must name the field and both remedies, rendering
R5's two-question test as an action rather than a refusal:

> `cadrumo_foo` is unbound. Enroll it as a storage category if the application
> chooses this location and writes data there; otherwise declare an
> `ExternalPathRole` (bundled resource, operator input, third-party cache,
> external executable, operator-directed output) with a reason.

**Mutation → RED:** add any new `Path`-typed field to `Settings` without binding
it. The failure must name that field.

**Positive controls — must stay GREEN:**

1. `cadrumo_libreoffice_executable` **is selected** by the selector. This is a
   control on the selector itself, and it is the specific regression the
   widening exists for — without it, a future narrowing back to suffix matching
   passes silently.
2. The two `_path`-named `str` fields above are **not** selected, proving the
   selector reads annotations rather than names.
3. A non-path field such as the output-language setting is not selected.

**Non-tautological because** the field set is enumerated from
`Settings.model_fields` — a source independent of the taxonomy. Deriving it from
the taxonomy would let the taxonomy define its own completeness.

### Gate 3 — Materialisation parity

**Defect:** a declared member the tree materialiser never creates, or a
file-valued member whose leaf is created as a directory — which puts a
directory exactly where a document must be written and fails much later, at the
write, far from the cause.

**Mechanism.** Run `ensure_storage_tree` against a temporary root. Derive the
expected set **from the taxonomy declaration**: a directory member contributes
itself, a file member contributes its parent and explicitly not its leaf.
Compare against **observed filesystem state**.

**Mutation → RED:**

1. Add a member to the taxonomy and exclude it from materialisation.
2. Flip the file-valued member's node kind to directory — the leaf then exists
   as a directory. `cadrumo_usage_ratios_path` is the live case; assert its
   parent exists **and** that the leaf is not a directory.

**Positive controls — must stay GREEN:**

1. A second call preserves a sentinel file planted after the first — idempotence
   and non-destructiveness, which a naive "clean state" implementation would
   break.
2. A member whose settings field is `None` (an opt-in escape such as the wallet
   diagnostic dump) is not required to exist.

**Non-tautological because** the oracle is the filesystem, not the materialiser.
Building expectations by calling the same iteration the materialiser uses would
assert nothing; the gate compares a declaration-derived expectation against
observed disk state.

### Gate 4 — Liveness

**Defect:** a declared member with no writer — the failure that put three
writer-less categories in the taxonomy and that a typed member set would
otherwise inherit from the dict.

**Mechanism — declare, then verify.** Each member declares either a `consumer`
(the module that writes it) or `dormant` with a reason. The gate verifies the
declaration by AST: the named module must contain a real `ast.Attribute` load of
the member's bound field. A dormant declaration must carry a non-empty reason.

**Why not whole-program write-reachability.** Full static reachability from
attribute to filesystem write produces false negatives on every indirection and
would be quietly disabled the first time it blocked a legitimate change.
Declaration-plus-verification is weaker in theory and far stronger in practice:
it cannot be satisfied by a name appearing somewhere, and adding a member forces
an explicit claim about who writes it.

**This gate must not degenerate into the method that already failed.** Four
independent passes agreed the three dormant fields were dead, but all four used
name-based searching; the confirming evidence came from attribute-consumption
tracing plus tracing the named feature. The AST requirement is what encodes that
lesson — a mention is not a consumption.

**Mutation → RED:**

1. Delete the consuming attribute load from the declared consumer module. This
   is the strong mutation: it is exactly the event "this field became dead", and
   it is the event no existing check catches.
2. Add a member with neither a consumer nor a dormant declaration.

**Positive controls — must stay GREEN, and one must stay RED:**

1. A module whose only mention of the field is in a **docstring** must **not**
   satisfy a consumer declaration — it must red. This is the
   `auth_session_keys.py` trap encoded directly into the gate that four prior
   passes failed on, and it is the single most important assertion here.
2. A member consumed anywhere within its declared module — not necessarily at
   module top level — stays green.
3. A legitimately dormant member with a stated reason stays green.

**Non-tautological because** the declaration alone never satisfies the gate; the
AST verification is an independent check of it. "Has a writer because it says it
has a writer" is precisely the shape this rejects.

### Gate 5 — Fingerprint participation

**Defect:** a change to what the drift fingerprint covers, made silently. Both
directions are invisible in the suite: excluding too much walks the digest
toward the empty-tree constant, which is the documented historical defect that
defeated drift detection for every installed operator; excluding too little
turns the digest into noise that churns on every cache write.

**Mechanism, two halves — both required.**

*Set equality, by field name in both directions.* The exclusion set derived from
the taxonomy's participation field must equal an oracle of field names carrying
per-entry exclusion reasons (self-reference, regenerable with no taxpayer state,
non-canonical duplicate). Both inclusions are asserted: an oracle entry absent
from the taxonomy reds, and a taxonomy exclusion absent from the oracle reds.

**Compare names, never resolved-path cardinality.** Two settings fields may
legitimately resolve to the same directory, which collapses a resolved-path
frozenset from 8 to 7 while 8 fields are still consulted. A cardinality
assertion reds on a legitimate collision and passes on a real omission — wrong
in both directions.

*Behavioural, with the control built in.* Against a temporary root: writing
beneath a **non-participating** category must leave the digest unchanged, and
writing beneath a **participating** category must change it.

**Mutation → RED:** flip any member's participation flag; the set-equality half
reds against the oracle.

**Positive control — the second behavioural assertion is the control.** Without
"writing beneath a participating category changes the digest", the gate passes
against a fingerprint function that has degraded to the empty-tree constant —
the exact historical defect. A one-sided gate here is worse than none, because
it certifies the failure it exists to catch.

**Coupling, and the rule that governs it.** The oracle drops from 8 names to 7
when `cadrumo_storage_backup_dir` is deleted, so this gate and that deletion are
coupled and land together. **A red here must never be resolved by editing the
oracle.** The two-directional equality is what makes that discipline
enforceable rather than advisory: silently dropping a name from the oracle reds
the opposite inclusion, so the oracle cannot be bent to match a change without
the change also being made in the taxonomy.

Note the declared set intentionally differs from today's shipped eight by adding
the registry disk cache, which is fingerprinted today and should not be. An
implementer seeing digests move must not restore parity with the old set.

### Build order and independence

Gates 1, 2, and 5 can be drafted against the declared taxonomy interface before
it merges. Gate 3 needs the materialiser's new signature. Gate 4 needs the
member declarations to carry consumer or dormant fields, so it lands with the
taxonomy itself.

Gate 5's oracle is coupled to the dormant-category deletion; the two land in one
commit. Gate 4 is what makes that deletion safe to make at all, because it is
the check that would have caught the dormancy in the first place.

### The requirement that governs all five

A gate must fail for the right reason **and** pass for the right reason. Each
specification above names its positive control explicitly, and a gate shipped
without its control is incomplete regardless of whether it reddens on the defect
it targets. Where a control is itself a red assertion — Gate 4's
docstring-mention case — that assertion is the gate's proof that it did not
degenerate into the weaker method.
