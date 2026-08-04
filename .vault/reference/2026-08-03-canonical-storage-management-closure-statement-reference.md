---
tags:
  - '#reference'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:dd9175765733e9fa90a96ab728cedc7a1c27123c56e6ca01121781ca91a8214c'
related: []
---

# `canonical-storage-management` reference: `canonical storage management closure statement skeleton`

## Summary

Drafted as a skeleton against known-shaped evidence while measurement was still
in flight, so the statement could be assembled rather than composed under time
pressure. Every section states what the evidence will be, which artefact carries
it, and — the part a closure document usually omits — what would have to be true
for the answer to that section to be "no". A skeleton with a shape only for "yes"
will find one; this was written to be equally capable of concluding either way.

**The criterion element is now resolved, and it did not resolve to a number.**
The operator's criterion — *"if we can satisfy that all file producing sites are
enrolled we're done"* — turns out not to be decidable over the set it names,
because nearly half of all write sites are handed their path by a caller and so
have no enrollment answer of their own. Restated over path-*choosing* sites it is
decidable, and it holds. Element 5 carries the measurement, element 5a the two
instruments and their blind spots, and the verdict states the one sentence that
can be defended in place of the one that cannot.

**Read the verdict as governing the criterion element only.** The remaining
elements keep their own statuses, and the conjunction rule below still governs
the whole.

## How to use this document when the evidence lands

For each element below, replace `STATUS: pending` with `STATUS: satisfied`
or `STATUS: not satisfied`, cite the artefact that proves it (a commit, a
test file, an exec record — never a chat message or a scratchpad file alone),
and answer the "what would make this no" question explicitly rather than
silently dropping it once the answer turns out to be "yes". The final verdict
is the conjunction of every element's status — one "not satisfied" makes the
whole statement "no", regardless of how many other elements are clean.

## The prominent blocker — read this section first

**STATUS: closed.** This section previously blocked the whole document; it
no longer does, and is kept first and this detailed so a reader can verify
the closure rather than take it on trust.

Both of this campaign's own gates — `test_storage_liveness_gate.py::test_every_consumer_claim_is_backed_by_a_real_reference`
and `test_settings_lifecycle_gate.py::test_no_production_module_names_an_operator_data_location_by_literal`
— traced to one unlanded change: five `var/cadrumo/...` literals in
`_app_live.py`/`_overview_evidence.py`. **The change landed** ("fix(cli):
enrol the live-read and filed-declaration roots in the taxonomy") —
**adopted rather than authored**: found complete and unattributed in the
working tree, predating this session, landed on operator directive rather
than committed unilaterally by the coordinator who had flagged it as stuck.

**Provenance**: measured by the plan/vault agent directly, and measured
the way this document's own carry-forward section prescribes after
catching itself failing to. `PINNED=$(git rev-parse HEAD)` resolved to
`c16bb9a0ae`; the working tree's `_storage_taxonomy.py` carries substantial
uncommitted peer WIP for the still-open Family 1/2 declarations, so an
in-place run would have risked exactly the dirty-tree contamination
mechanism 1 describes. `git archive "$PINNED"` extracted to a clean
scratch directory instead; both gates run from that archive: **2 passed**.

**What would have made this "no", preserved for the record**: the fix
never lands, or lands but a fresh serial single-SHA gate run — SHA
resolved into a variable before archiving — still shows either test red.
Neither happened. **No other evidence in this document could have
outweighed a "no" here** — that asymmetry is why this section stays first
even now that it is closed, rather than being folded into the numbered
list below.

## What "enrolled" means — see ADR `R5`, which now rules it

**The decision lives in the ADR, not here.** `R5` carries an explicit amendment
clause: a read of a `Path`-typed `Settings` field bound to a taxonomy member
**is** enrolled, and only re-typing a segment escapes. This section is a pointer
and a summary; where the two differ, `R5` governs.

It was written here first, as a lead's ruling inscribed in a closure statement,
which was the wrong home — a closure document reporting compliance with a
decision should cite the decision, not contain it. Worse, the ruling was made
without reading `R5`, whose affirmative sentence says *produced by that accessor*
and whose five disqualifiers do not mention a field read. The gap was real; the
ruling was defensible on `R6`'s enrollment-unit logic and contradicted `R5` as
written. It is now an amendment to `R5` rather than a paragraph citing a message.

Summarised, because a reader of this document should not have to leave it to know
what "done" means — the two available readings **change what "done" means by
roughly a factor of two**, and the criterion's original wording did not
distinguish them.

```
storage_path(StorageCategory.X)   ENROLLED
settings.cadrumo_x_dir            ENROLLED
storage_root / "llm-cache"        NOT enrolled  -- this is what S78 burns down
```

**The intent reading governs, and it is enforced rather than asserted.** A
settings-field read is taxonomy-governed because two gates make it so, both green
at HEAD:

**`test_storage_binding_gate.py`** — every `Path`-typed `Settings` field is a
taxonomy member, a declared escape, or the storage root: **total and disjoint**.
Its discovery is anchored to `Settings.model_fields`, deliberately *independent*
of the taxonomy, and the gate's own docstring says why: were the field set
sourced from the taxonomy instead, both sides would move together and an empty
discovery would compare empty against empty and pass. That property is what makes
this a chain a reader can check rather than a conclusion to trust.

**`test_storage_default_parity.py`** — each field's placeholder default states the
same subpath the taxonomy declares.

So a field read is a **gate-guaranteed member with a parity-pinned default**, not
a second authority. **Accessor versus field is a style difference, not an
enrollment difference**; only re-typing the segment escapes the taxonomy.

**Two consequences worth stating plainly.** Accessor adoption is **hygiene, not
correctness**, and if this document's language overstates adoption the language
narrows rather than modules migrating for zero enrollment gain. Re-measured at
`83627b8830`, as three numbers rather than a ratio:

```
modules calling storage_path(          8
modules reading a bound path field    18
in both                                1    master_key/_master_key.py
```

**Deliberately not expressed as "8 of N".** An earlier version of this line said
"5 of 26"; both figures were wrong — the 5 came from a grep pattern that missed a
name at end-of-line with no trailing comma, and the 26 was the sum of two
overlapping samples presented as a population. The real denominator is however
many production modules resolve a storage location at all, which nobody has
measured, so a reader should form their own view from the three counts.

**The field-reader count narrowed again, for a third reason.** A prior pass at
`5da2b328f9` reported 24 by counting any file matching a bound-field pattern
without checking whether the match was a genuine attribute read or a docstring
cross-link. Three of those 24 — `blob_store/_blob_store.py`,
`core/auth_session_keys.py`, `core/observability/_store.py` — carry exactly one
match each, and every one is prose: a Sphinx `:attr:` role in a module docstring,
not a line of code. `auth_session_keys.py`'s docstring in fact says the opposite
of what the grep implied, that its key derivation is "deliberately independent
of `Settings.cadrumo_token_dir`." `observability/_store.py`'s is the same shape,
and explains why: `S53` re-pointed its real read onto `storage_path()`, and the
docstring narrating that migration ("rather than by reading `cadrumo_runs_dir`")
is what a substring-blind count mistook for a live second door. That also moves
the **overlap** citation: `core/observability/_store.py` is accessor-only now,
not a dual-door module, and the one real overlap is
`master_key/_master_key.py` — it reads `settings.cadrumo_secret_store_dir`
directly for the secret-store root (`SECRETS` is operator-overridable, so the
module cannot resolve it through `storage_path()` without silently disagreeing
with an override) while separately calling `bucket_scoped_storage_path()` for
the bucket-scoped keystore DEK, a genuinely different location. Prose-mention
false positives are the same failure mode a raw-substring literal count produces
elsewhere in this campaign; a field-reader count needs the same content check
before it can be cited as a code fact.

And the parity gate makes the duplicate **safe, not single**: a subpath is still
spelled in two places, it simply cannot drift. That residual is `S114`'s, not the
criterion's.

## Criterion elements

Each element states the plan Step(s) that carry it, the artefact that will
prove it, and the falsifying condition.

### 1. The cheapest refutations — `S51`, `S52`, `S53`, `S24`

**STATUS: partial.** `S24` closed ("fix(core): enroll active-profile
pointer path through the storage taxonomy") — `pointer_path()` now calls
`storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()`;
no exception was needed, since the taxonomy module has no runtime import
path back to `config.py` and the pre-existing deferred, submodule-qualified
import was sufficient on its own. **This is the third instance in this
campaign where a checked Step did not match landed code** (`S42`, `S54`
unaccountable-checkbox flips that turned out genuinely done; `S24` checked,
found genuinely not done, unchecked, now genuinely done) — the only one of
the three where the checkbox itself was wrong rather than merely
unaccountable. `S51`, `S52`, `S53` remain open — their cited file:lines
still read `load_settings()` directly, not re-verified again since the last
pass.

**Provenance**: `S24` verified directly against committed HEAD
(`git show HEAD:src/cadrumo/core/_bucket_pointer_io.py`) by the plan/vault
agent. `S51`–`S53` still carry the earlier caveat: measured via `git show
HEAD:<path>` reads with no SHA captured — re-verify before citing as
settled.

**Evidence**: each remaining site re-pointed onto `storage_path`/the
accessor, verified by reading the changed file at a pinned SHA, not by
trusting the Step checkbox.

**What would make this "no"**: any of `S51`–`S53` still reads the location
directly at closure time, or a Step is checked without the corresponding
code change present at the cited SHA.

### 2. NESTED-UNGOVERNED families — `S86`–`S92`, `S107`

**STATUS: partial — named explicitly rather than left as a fraction.** Four
items closed, three of the four via the same distinction (already declared
under a different name), the fourth (`S89`) via real declaration work.

- **`S86`, `S87`, `S88`** — closed via the `StoragePathDefinition` grammar
  mechanism, a discovery about the record, not progress against the work.
- **`S89` — the secret store's five file leaves — closed for real.**
  ("feat(storage): declare the secret store's five file leaves and gate
  directory-grammar drift.") Five new `FIXED`, no-`settings_field`
  taxonomy members, each cross-referencing only the bare filename its
  producer already resolves via the settings field it reads — composing
  root + subpath through `storage_path()` was rejected deliberately, since
  `SECRETS` is operator-overridable and that composition would silently
  disagree with a real override. A new directory-grammar agreement gate
  landed alongside, with two positive controls, and it found a genuine
  separate gap named as `S108` below rather than fixed inline.

**Still open, named individually:**

- **`S90`** — the `audit`/`live` intermediate segment plus `live/iva-wallet`,
  `live/iva-remote-state`, `filed-history`, `wallet`. **Uncommitted peer WIP
  exists for this in the working tree** (`_storage_taxonomy.py` carries
  `AUDIT_LIVE*` members not yet committed as of this reconciliation) — real
  progress, but not yet landed; do not mark closed on the strength of the
  working tree.
- **`S91`** — `submissions/amendments`, `submissions/amendment-results`,
  `financial/attachments/manifests`. **Same uncommitted-WIP caveat as
  `S90`.**
- **`S107`** — five filename-template patterns. Mechanism confirmed
  applicable (no ruling needed); grammars not yet declared.

**Provenance**: `S86`–`S89` verified by the plan/vault agent directly
against committed HEAD `c16bb9a0ae`. The `S90`/`S91` uncommitted-WIP
observation is from a `git status --short` read at the same session,
timestamp not separately captured — re-check status before citing whether
it has since landed.

**Evidence**: each remaining family declared with its own conformance test,
or explicitly re-classified as an OPERATOR-DIRECTED escape with a stated
reason.

**What would make this "no"**: any of the three remaining items undeclared
at closure time, or declared with a grammar/member that a real-write
conformance test doesn't actually exercise.

### 3. Settings-defaults contradicting the taxonomy — `S105`

**STATUS: pending.** Five settings-field defaults (`cadrumo_registry_parity_store_dir`
plus four `var/`-prefixed fields) disagree with their declared taxonomy
subpath. Dead at runtime (the derived-output validator overrides from the
taxonomy), but a second, drifted declaration nothing compares.

**Provenance**: measured by the honesty reviewer, in-process comparison of
every bound field's default against its member's `relative_path()` (20
agree, 2 opt-in with no default, 5 disagree). **Not independently
re-verified by the plan/vault agent** — taken from the audit document as
reported, not re-read against code directly. Re-verify before treating as
settled.

**Evidence**: the five defaults corrected, and — the part that makes this
not recur — a gate asserting every bound field's default equals its
member's `relative_path()`, per the audit's own recommendation.

**What would make this "no"**: the five values corrected but no comparison
gate added, since that leaves the exact defect class (a dead but drifted
second declaration) able to recur silently on the next new field.

### 4. The containment-proof blind spot — `S106`

**STATUS: pending.** `reclaim`'s containment proof quantifies over declared
taxonomy members, so it cannot see undeclared nesting beneath an accepted
category — safe today only because every known undeclared site sits under
an `unbounded_by_design` parent, not because the proof asserts anything
about it.

**Provenance**: measured by the honesty reviewer, reading the proof's
implementation and its own docstring. **Not independently re-verified by
the plan/vault agent.**

**Evidence**: either the proof extended to catch undeclared nesting (hard,
since by definition it doesn't know what it doesn't know), or an explicit
statement in the ADR that this is an accepted residual risk with the reason
stated, so a future member declared `RETENTION` with undeclared nesting
beneath it is a decision someone took rather than a gap nobody noticed.

**What would make this "no"**: the gap is neither closed nor acknowledged
— i.e. this document ships silent on it, which is the exact failure mode
the closure-criterion reference exists to prevent.

### 5. The criterion is not decidable as worded, and the write-site census is why

**STATUS: satisfied, with the criterion restated.** This element asked for a
manual review of the ~99 write sites. The review was performed by census
rather than by hand, and it returned something stronger than a classification:
**the criterion cannot be evaluated over the set it names.**

**Provenance**: `dev/write_site_census.py`, landed with its test at commit
`30f2493ee1`, quantifying over write primitives in the AST rather than over the
taxonomy — the direction that matters, since a census iterating declared
members cannot see an *un*enrolled site. Recomputable at any revision by
`python -m dev.write_site_census <revision>`; the figure is deliberately not
restated here as a bare number, because a count in prose has no maintainer and
this corpus has already lost two to that.

**Evidence**: classified by where the written path comes from. Measured at
revision `a5889c3199`, **98 matched sites of which 43 are pass-through**; of the
9 sites on duck-typed method names, reading each cleared 6 as non-filesystem,
giving **92 file-producing sites as an upper bound**. Every figure here belongs
to that revision and is reproduced by re-running the tool, not by reading it back
out of this paragraph.

**The figure held at four independent revisions** — `611df3a67e`, `9e96c02bab`,
`800767930f` and `a5889c3199` — byte-identical distributions across the taxonomy
restructure that moved the declarations into their own module, the tracked corpus
growing by a third, the `BUCKET_DATABASE_FILE` prefix fix, and the scanner's own
test-scope extension. Stability under change is stronger evidence than agreement
at a single point: four readings of one unchanged tree would prove only that the
tool is deterministic.

**The instrument's own limits, stated here rather than only in its audit**, so a
reader who follows this citation meets the number and the limit together:

- **43 of 98 sites are `pass_through`** — the path arrives from a caller, so
  `_trace()` bottoms out at `self` or a parameter. That is the tool reporting the
  boundary correctly, not failing to resolve; the site genuinely has no
  enrollment answer of its own.
- **9 of 98 are `unresolved`** — a 9% rate the tool now self-reports with the
  instruction *"read these, do not trust them"*.
- **Duck-typed method names cannot be separated from their filesystem namesakes
  without type inference**, which is why the 9 ambiguous sites are enumerated for
  a human read rather than silently counted either way.

A primitive doing
`path.parent.mkdir()` on a path it was handed **has no enrollment answer of its
own**; its answer is "wherever the caller said". Asking whether such a site is
enrolled is not a question with a truth value, and nearly half the domain is in
that state. This element's earlier estimate of "roughly fifteen" pass-through
primitives was low by a factor of three, and the difference changes the
conclusion rather than refining it: at fifteen it is an edge case, at
forty-four it is the dominant shape.

**The criterion becomes well-formed over path-*choosing* sites** — the places
that decide a location rather than the places that write to one. That set is
strictly smaller and, unlike the write set, decidable: choosing a path means
composing it from a root or a declared field, which is a syntactic act.

**What would make this "no"**: a closure statement that quotes a site count as
if it settled the question, without recording that nearly half the sites have
no answer to give.

### 5a. The two-instrument union, with each blind spot named beside it

**STATUS: satisfied.** Restated over path-choosing sites, the criterion is
carried by **two instruments, neither sufficient alone**, and a reader who finds
only one will reasonably conclude the coverage is complete.

**Instrument one — the provenance gate.** Walks every packaged module,
production and test, and requires any site composing a path from the storage
root to be a declared producer. Green, with `PENDING_ENROLLMENT` reduced to the
empty tuple in a table declared to only ever shrink. **Blind spot:** it keys on
the *root*. A site joining a literal onto a *category* field never touches the
root symbol and is invisible to it.

**Instrument two — the taint-based family census.** Covers exactly that
category-composed class, and its four families are declared. **Blind spot:**
incomplete by construction for the four classes it names — cross-module
composition, library-named files, container-mediated flow, and fully dynamic
expressions.

**Blind to both:** writes through a retained handle, where one syntactic site
performs unbounded real writes, and duck-typed method names that no static pass
can separate from their filesystem namesakes without type inference.

**And one of the two instruments accepts a coincidence** — see element 5b. The
liveness gate's evidence test matches a bare attribute name without qualifying
its owner, so a claim can pass on a reference to an unrelated enum. That does
not weaken the "by either instrument" qualifier in the verdict; it is what makes
that qualifier load-bearing.

**What would make this "no"**: recording the union as though it were a proof.
It is two partial covers whose overlap is unmeasured; that is materially better
than either alone and materially weaker than completeness.

### 5b. The liveness gate passes on a name collision — now closed at both levels

**STATUS: closed.** This element previously read "instance closed, class open",
which is **no longer true and is corrected here rather than left standing.**
`consumption_evidence` now requires the matched name to resolve to an attribute
bound to `StorageCategory`, and the gate's own docstring names the
`SensitivityClass.AUDIT` case as the defect it exists to prevent. Verified at
`19154e664e` by reading the matcher, not from the commit subject.

**The re-run returned a null, and the null is the informative part.** 13 pass,
**no newly-failing member** — no currently-declared `consumer_module` claim was
ever satisfied *only* by the collision. The `AUDIT` instance was the sole
exploitation of the hole and had already been re-pointed before the mechanism
was closed.

That matters for element 5e rather than for this one: it means every claim the
gate can see is honestly backed, so **the gate will not surface the
declared-location-with-SQL-persistence class**, because a member can be
genuinely referenced while nothing ever writes a file there. The gate is not
weak; it answers a different question, correctly.

The original finding follows unedited, because the mechanism it describes is why
the fix was needed.

### 5b-original. The collision as first found — instance fixed, mechanism unchanged

`StorageCategory.AUDIT`'s consumer
claim was satisfied by **14 references to `SensitivityClass.AUDIT`** — an
unrelated encryption-sensitivity enum — and **zero** references to the storage
category. The category is genuinely live, so the claim was **true,
mis-attributed, and passing for the wrong reason**: the most expensive shape a
gate can have, because nothing about it looks wrong.

**Verified at HEAD**, not taken on report. The `AUDIT` member's claim is
re-pointed and carries an inline note recording the collision. But
`consumption_evidence` still matches
`isinstance(node, ast.Attribute) and node.attr in names` with **no qualification
of the attribute's owner**, and `_claim_names` still reduces a member to the bare
tokens `{category.name, settings_field}`. So the specific claim is corrected and
**the mechanism that admitted it is not**: any member whose name collides with an
attribute of an unrelated type in its claimed module would pass the same way.

**What would close the class**: require the owner, not just the token — evidence
must be `StorageCategory.<NAME>` or the bound settings field, never a bare
`<NAME>`. Until then the residual is every member whose name is a plausible
attribute elsewhere, and that set has not been enumerated.

**Why it belongs in a closure statement**: this is the same defect as the
`blobs`/`blobs` anchor collision — two spellings agreeing because they share a
name rather than because they name the same thing — now found in a *gate* rather
than in a declaration. A campaign closing on "two instruments agree" must record
that one of them can agree by coincidence.

### 5c. The canonical authority re-typed its own declaration

**STATUS: closed**, commit `b7334e6ee2`, audit entry `9782459683`.

`BUCKET_DATABASE_FILE` hardcoded the `db/` prefix that `BUCKET_DATABASE.subpath`
already owned, so renaming the directory would have silently orphaned the file
member nested inside it. Mutation-proven — 13 errors before the fix, both members
moving together after. Verified at HEAD: the member now composes
`f"{_BUCKET_DATABASE_DIRNAME}/{_PRODUCT_DATABASE_FILENAME}"` from a name declared
once.

Worth stating plainly rather than filing as one more fix: **this is the
campaign's defining defect — a name re-typed instead of read from its
declaration — found inside the canonical authority the campaign built to end
it.** A closure statement that omits it would imply the authority was exempt from
the problem it solves.

### 5d. A third literal category: the test-side pass-through

**STATUS: open, treatment known.** `S78`'s migrate-or-pin split does not cover a
third shape. A test writing
`FileFallbackMasterKeyProvider(store_dir=tmp_path / "secrets")` **supplies the
path itself**; the string `"secrets"` is arbitrary scratch naming that collides
with taxonomy vocabulary by coincidence. It is neither a literal to migrate onto
the taxonomy nor one to pin against it.

**This is the test-side `pass_through`** — the same "no enrollment answer of its
own" that element 5 establishes for roughly half of production write sites,
rediscovered independently in the test corpus by a lane that had not read that
measurement. Independent rediscovery in a different corpus is what makes it a
property of the shape rather than an artefact of production code, and it
strengthens element 5's central claim rather than complicating it: **the
pass-through class recurs wherever a caller supplies the path.**

**Treatment**: rename to a word outside the vocabulary, precedented by `S55`'s
`probe-cert-store`. The path is the test's own scratch space, so any name works
and a non-colliding one stops it reading as an ungoverned literal forever.

**`S78`'s scope was also 2.5× its plan row** — measured by AST over the test
corpus against a vocabulary derived live from `STORAGE_TAXONOMY`: **257 files and
777 sites**, against the row's ~108 files and ~350 sites. Both figures belong in
the record with their method beside them, because the row's number was an
estimate and the measurement is reproducible.

**Provisional: a fourth category may deflate that measurement substantially.**
Of 94 `justificantes` hits, **69 are rooted at `FIXTURES_DIR`** — the repo's own
test-corpus tree, declared as `_FIXTURES_ROOT / "justificantes"` in
`adapters/inbound/justificante/tests/test_parser.py` and again in
`test_corpus_sidecar_roundtrip.py`, verified at HEAD — and 25 more are synthetic
`source_pdf_path` metadata values. That folder shares a word with the taxonomy
category and nothing else.

The mechanism is worth naming because it is the same one that produced the
`blobs`/`blobs` anchor collision and the liveness gate's `SensitivityClass`
collision in element 5b: **the scanner matches vocabulary against `/` operands
without knowing which tree the root belongs to.** Three findings, one root cause —
a name compared without its namespace.

So beyond pin, migrate, and injected there is a fourth disposition: **different
namespace, not in scope at all.** If that fraction generalises, 777 is an upper
bound over a substantially non-storage corpus and the plan row's ~350 was closer
to right than the measurement that appeared to overturn it — for a reason nobody
had identified at the time.

**Held as provisional deliberately.** One literal, and `secrets` behaved
completely differently, so the fraction is not known to generalise. `rootpath` is
testing it; a root-origin discriminator on the scanner would settle it. Until
then 777 must not be carried as a scope figure — which is the same discipline as
the census figures above, applied to a number that arrived from another lane.

### 6. Runtime census cross-check

**STATUS: pending.** The audit's own stated method for the tightest
defensible bound: intersect the ~99 static sites against the frames the
instrumented runtime census (`S103`) actually observed, to make the
residual ("sites that both compose cross-module and are never exercised")
a named, finite list rather than an open question.

**Provenance**: not yet computed. When it lands, cite the two input
artefacts by their pinned measurement (the static site list's SHA, the
runtime census's suite-run identity) rather than by name alone — an
intersection of two unpinned measurements inherits both their staleness
risks.

**Evidence**: the intersection computed and persisted, with the residual
list named explicitly — even if the residual is non-empty, naming it is
what this element requires, not eliminating it.

**What would make this "no"**: the intersection is never computed, so the
residual stays an unmeasured "probably fine" rather than a bounded list.

### 7. Test hygiene — `S84`, `S85` — explicitly not a closure gate

**STATUS: N/A to the verdict, tracked separately.** Per the operator's
second re-scope, test cleanup is a different standard (nothing a test
creates should survive the test) with its own empirical evidence
(snapshot-diff before/after a suite run), and does not gate this criterion
even if its own findings (e.g. the `cadrumo-settings-*` leak already found)
remain open at closure time. **State this plainly in the final document
rather than silently omitting test hygiene** — an omission reads as an
oversight, a stated exclusion reads as a decision.

**Provenance**: no measurement performed yet; `S84`'s snapshot-diff census
is authored but not run. Not required for the verdict, so its absence does
not block closure — but if it runs before closure, cite it the same way as
the other elements (who, method, pinned-or-not) rather than as prose.

### 8. Test-migration and W02.P07/P08 — explicitly out of scope

**STATUS: N/A to the verdict.** `S76`–`S78` (bulk test-literal migration)
and `S93`–`S100` (effective-storage-root and optional-root-resolver
convergence) are real drift reduction, re-scoped out of the closure path
by the operator's own criterion. State their open count in the final
document so a reader doesn't mistake plan-completion-percentage for
closure-percentage, but do not let their open count affect the verdict.

**Provenance**: plan Step counts (`S76`–`S78` open; `S93`–`S100` open),
read directly from `vaultspec-core status` at time of writing — the plan
tool's own state, not an independent measurement, and it moves as Steps
land. Re-read at closure time rather than citing this document's number.

### 9. Two findings from this wave, not yet fixed — `S108`, `S109`

**STATUS: pending, both.** Real, verified, newly discovered while
reconciling this wave rather than commissioned in advance.

**`S108`** — the new directory-grammar agreement gate (landed with `S89`)
found `application/_config_reset_repository.py` carrying its own duplicate
`CONFIG_RESET_JOURNAL_DIRNAME = "reset-operations"` constant, joined onto
the raw storage root, bypassing `storage_path()` entirely — even though
`_storage_path_definitions.py` already declares this exact shape
(`config_reset_journal`). Named as an exemption in the gate rather than
fixed or laundered; this Step tracks closing it. **Provenance**: verified
directly by the plan/vault agent against committed HEAD `c16bb9a0ae`
(`git show HEAD:src/cadrumo/application/_config_reset_repository.py`).

**`S109`** — `src/cadrumo/tests/test_compatibility_lifecycle_gate.py::test_the_enrollment_predicate_names_every_uncovered_durable_format`
is red at HEAD, campaign-caused: this campaign's own persisted-format
declarations added `bucket_database_file` and `secret_index`, and the
gate's hand-written expected tuples were never updated to include them.
Routed (open, not yet fixed). Consider deriving the expectation from the
declared formats rather than restating it by hand — a hardcoded census of
uncovered formats is the gate shape this project forbids elsewhere.
**Provenance**: run directly by the plan/vault agent, working tree (not a
clean archive — this test file itself has no uncommitted changes, but the
run was not pinned): `pytest src/cadrumo/tests/test_compatibility_lifecycle_gate.py::test_the_enrollment_predicate_names_every_uncovered_durable_format`,
**3 failed** (all three parametrised cases), confirming the same cause the
coordinator named.

**What would make either "no" if closure were declared today**: both are
open, unambiguously — `S109` in particular is a currently-red test, the
same class of evidence that gated the prominent blocker above, just in a
different gate.

## Carried forward unchanged — three things a reader most needs

**Step state is a claim, not evidence.** Three times in this campaign a
checked plan Step has not corresponded to landed code (`S42`, `S54`, `S24`
— the first two unaccountable-checkbox flips later verified genuinely
done, the third checked and found genuinely not done). Every element above
must be verified against the cited artefact directly; a checked Step is a
starting point for verification, never a substitute for it.

**The five measurement-mechanism failures this campaign catalogued, all of
which survived their own verification because something real was measured
and the wrong name attached to it:**

1. A gate run in a dirty working tree, reported as a HEAD fact — twice.
2. A peer's uncommitted-lane observation relayed as a fact about HEAD,
   unchecked.
3. `git archive HEAD` run, then `git log -1` run *afterwards* to label it
   — a commit landed in between, so the parent was measured and the
   child's SHA reported.
4. A 62-minute full-tree run against a tree receiving commits throughout,
   measuring no single state — 2 of 21 reported failures were already
   fixed by the time the run finished.
5. The inverse of the first four: the object was right, but the
   instrument's selector was broader than the concept it was named for —
   a "production filesystem-mutating call sites" census matched every
   `.replace(...)` attribute call, so `str.replace` scored as `Path.replace`;
   267 reported, 166 false positives, ~99 real.

**A sixth instance, and it is this document, not a source it cites.** The
first draft of the prominent-blocker section above stated "3 unbacked
consumer claims became 13" and read the campaign's enforcement as
regressing — mechanism 3, reproduced inside the very document warning
against it: the measurement behind that sentence came from `git archive
HEAD` run, then `git log -1` run afterwards to label it, with a commit
landing in the gap. Found by re-reading the source the sentence cited
rather than trusting an earlier citation of it, and corrected to the true
arc, 3 → 13 → 3, in the section above. **The catch is better evidence that
this discipline works than the list of five ever could be** — a document
that states a rule and then is shown violating and self-correcting under
that same rule demonstrates the rule bites its own authors, not just the
measurements it was written to critique. A reader trusting these six
mechanisms should expect them to catch the next person too, including
whoever finalises this statement.

The discipline this closure statement must follow, stated once so every
section above can rely on it without restating it: **resolve to an
immutable object first, measure that object, report that object — never
report the name.** `PINNED=$(git rev-parse HEAD)`, then measure against
`$PINNED`, then report `$PINNED`. When two measurements disagree, the
difference is almost always in the setup, not in which one is wrong.

**The named limits — state these explicitly in the final document even if
they remain open, because a closure statement silent on a known limit
reads as though the limit was never found:**

- `cadrumo_database_url` is `str`-typed and invisible to the `Path`-typed
  binding machinery — confirmed real, not yet resolved.
- The runtime write census is blind to directory creation (a companion
  `dir_census.py` pass is written but not yet run) and, by construction,
  to any code path the instrumented suite run never exercises.
- The POSIX root-permission-drift assertion and the mode-bit test
  (`S81`) have never executed on a real POSIX host — guarded-inline makes
  them non-vacuous where they run, which is not the same as verified.
- A named transport-primitive class whose enrollment question relocates to
  its call sites rather than resolving at the primitive itself. **Source,
  per the coordinator: the manual read of the ~99 sites (element 5), not
  the coordinator's own measurement** — roughly fifteen are pass-through
  primitives doing `path.parent.mkdir(...)` on a path they were handed, so
  their static answer is definitionally "wherever the caller said," pushing
  the enrollment question to each call site rather than the primitive.
  Carried forward as stated; whoever finalises this document
  should re-verify and cite the specific primitive and call sites before
  the statement ships, since this skeleton does not yet have independent
  verification of that claim.

**What the self-duplication audit (`021c3bae46`) found clean, recorded because
it is load-bearing for closure and a reader should not have to take it on
faith:** layering verified with no upward `core → adapters` import; the
storage-management service composes existing primitives rather than
re-implementing them; no two of the seven gates detect the same condition
(read against each other individually); nothing the campaign added is an
unconsumed public symbol; all three deliberate separations this campaign
decided against merging (the independent-oracle test, the five no-`settings_field`
secret-store members, the SQL secure-object namespace split) are re-verified
on evidence, not merely re-asserted; and 129 tests across eleven gate
modules pass. Four new findings from the same audit are tracked as `S111`–`S114`
and as the `R16` correction, above and in the closure-criterion reference's
fragile-spots section — the clean result does not cover them, and citing the
clean parts should not be read as covering the open ones.

### 5e. A dead declaration passes the criterion for free

**STATUS: open, population unmeasured.** Three members now declare a filesystem
location whose records actually live in the encrypted SQL `secure_objects`
table — the blob-store attachments entry, the `AttachmentStore` filesystem
assumption, and `cadrumo_justificantes_dir`. Persistence migrated; the
declaration did not.

**Why this is a criterion element and not a tidiness note.** A declared location
that nothing writes to satisfies *"all file-producing sites are enrolled"*
**vacuously** — there is no site to enrol, so the member passes for free. A
criterion a dead declaration cannot fail is one more place silence reads as
coverage, which is the failure this campaign exists to surface. It is a hole in
the completion criterion itself, not a footnote to it.

**The population is not known, and two attempts to bound it failed.** A
module-level probe ("does a referencing module contain a write primitive")
missed `JUSTIFICANTES`, because `_rotation.py` genuinely writes — elsewhere. A
per-read probe keyed on the settings field returned `NO-READ` for `LOGS`, `RUNS`
and `TOKENS`, which are demonstrably written, because production reaches
locations through `storage_path(StorageCategory.X)` — the accessor this campaign
built and mandated. **The taxonomy's own success removed the syntactic handle the
second measurement needed.** Two instruments, two different positive-control
failures; no count is carried forward from either.

**Severity is reachability, not declaration.** A bare unwritten declaration is
dead weight — a wrong mental model for a reader, an always-empty row in
`config storage list`. It becomes a defect when something acts on it. For
`cadrumo_justificantes_dir` that path is live: its only non-declaration
production consumer is a `RotationPlanEntry` describing a `.envelope.json` shape
nothing writes, so the sole thing reaching the location is a plan to act on
records that are not there.

**What would settle it** is a filesystem observation rather than a source one:
exercise each feature and check whether the declared directory receives bytes.
That work is in flight. Its honest ceiling belongs here in advance — **absence of
bytes in an observed window is not proof that nothing ever writes there.** A
location on an error path or behind a filing action stays empty and looks
identical to a dead one, so the achievable result is *"N observed receiving
bytes, M not, under this named workload"*, and M is not a dormancy finding on its
own.

**What would make this "no"**: closing on a criterion that a dead declaration
passes, without recording that the class exists and its size is unknown.

### 5f. Encryption-at-rest assertions read a file the data is not in

**STATUS: closed, landed and verified at `44e7f0d957` (8 files).** The finding
below stood, and the fix resolved it while this element still read "open".

**The distinction the fix established, which matters more than the closure.**
Every converted assertion still passes under the real combined read — zero
regressions, no green-to-red flip. So:

> **The encryption guarantee held in every case checked. What was broken was the
> check, not the guarantee.**

Both halves are load-bearing and a reader should take neither alone. The defect
was real — roughly fifteen assertions were vacuous and would have passed against
a build with encryption disabled — *and* it was not masking a leak. Reporting
only the first overstates; reporting only the second excuses a class of test
that could not fail.

**Verified independently before the fix, not taken on report.** The owner
reproduced the measurement itself — instrumented an iva-wallet decision save,
main file 4,096 bytes and zero rows, combined 173,048 bytes containing the
marker — rather than trusting the coordinator's numbers.

**Six bare main-file scans remain, deliberately**, each classified with reasoning
in the commit: the two that demonstrate the gap, the two that run after
`dispose_engine()`'s own checkpoint, the refused-write byte comparisons, and the
helper's own implementation. A residual that is enumerated and reasoned is a
different object from one that is merely left.

The original finding follows, because the mechanism is why the conversion was
needed and a closed element that deletes its own evidence teaches nothing.

**STATUS as first found: open, highest severity on the board.**

Roughly 14–18 assertions across ~10 modules assert
`b"<marker>" not in database_file.read_bytes()` to prove secure-object content is
encrypted at rest. **SQLite in WAL mode does not put it there.** Mutation-proven:
after a real secure-object write the main `.db` is **4096 bytes with delta zero**
while the WAL holds **169 KB**, and the positive control settles it — the
namespace, a plaintext lookup column certainly on disk, is **present in the WAL
and absent from main**.

So the assertion passes while that exact string sits in cleartext on disk. These
are **not weak checks; they are not checks.** They would pass against a build
with encryption disabled entirely.

This is the day's fourth instance of a protection whose failure is
indistinguishable from its success, and the most consequential, because the
property it fails to check is the product's load-bearing confidentiality claim.

**What would make this "no"**: converting the assertions and accepting a green
result without confirming the conversion can fail — the owner's instruction is to
escalate rather than weaken if a converted assertion goes red.

### 5g. A sixth classification outcome: injected-but-constrained

**STATUS: open. Mechanical detection was attempted, measured against pre-stated
oracles, and rejected as a finding generator — see the detection subsection.**

`S78`'s dispositions were pin / migrate / injected / different-namespace /
accessor-is-the-subject. A sixth exists: **the test supplies the path, so it reads
as freely chosen, but a sibling fixture derives it from the real accessor or a
child process recomputes it** — so the literal is load-bearing after all and
renaming it breaks the handoff.

**The verdict is `pin`, and the discriminator is that a rename breaks the test.**
That is the operational definition: not "does this site look injected", but "does
anything else reach the same path by another route". `write_site_census.py:673`
states it in the tool's own output — *classification is pin, a rename would break
it*.

Found the hard way: two independent reviewers classified the same three `secrets`
sites as free, and only an attempted rename revealed the constraint. Three
renames were reverted at `dee79c3a3b`.

**Why it belongs in a closure statement**: every other disposition is decidable
by reading one site. This one is not — it is a property of the *relationship*
between a site and a fixture or subprocess elsewhere, so a site-by-site review
cannot see it by construction, and two careful readers already proved that.

**The detection rule for a human reader**: for any apparently-injected path, ask
whether anything else in that test derives the same path independently — a
sibling fixture, a subprocess, a CLI invocation wrapper. If yes, the literal is
constrained and the disposition is `pin`.

**The same rule catches a test that was born vacuous.**
`test_save_does_not_create_requested_plaintext_file`
(`domain/usage_ratios/tests/test_service.py:58`) asserts `not target.exists()`
for `target = tmp_path / "a" / "b" / "ratios.json"` — a path never passed to
`save_usage_ratios`, which takes only `profile` and `bucket_id`. It passes
identically whether or not the real location is written, and always did. This is
the constrained question run backwards: there, a path looks freely chosen but is
secretly load-bearing; here, a path looks load-bearing but is connected to
nothing. **Ask the same question — what else reaches this path? — and the answer
"nothing, including the code under test" is the tell.** Its sibling
`test_save_persists_only_to_the_secure_database_object` is the non-vacuous form.
Accessor routing prevents a test drifting to vacuous; it does not prevent one
arriving that way.

#### Mechanical detection was tried and does not work — do not rebuild it

Recorded so the next person does not build the same tool without knowing it was
built and measured. `WriteSite.constrained` exists in `dev/write_site_census.py`
and its `--scope tests` sweep was checked against three oracles stated before the
run (`f101eb9427`, audit
`2026-08-04-...-constrained-detector-sweep-diagnosis-audit`):

- **over-fires roughly 30x** — 114 flags at `64c9fe6d6e` against at best 3 real
  candidates, independently reproduced at a second pin (`53f80f0830`, 110 flags)
- **misses two of the three known `secrets` positives** — the very sites that
  established the category
- **three distinct over-firing mechanisms**, all rooted in `CONSTRAINT_RISK_SIGNALS`
  reusing `TAXONOMY_MARKERS` — designed for narrow root-of-expression tracing — as
  a blanket identifier-presence check with no regard for binding context
- the two misses have **different** causes, and the diagnosable one
  (`invoke_cached_cli` absent from the risk-signal set) **would not rescue the
  tool**, since over-firing is the dominant failure mode

It was diagnosed rather than tuned to the oracles, which is why the conclusion is
trustworthy in the negative direction. The code, its tests, and its self-reported
unresolved rate are kept and remain valid; what is rejected is treating its output
as a finding list.

**The strongest form of the rejection is not the over-firing rate.** An earlier
gloss held that the tool prints more sites than a hand classification would read;
that was wrong by roughly 6.4x — measured by `honesty`, against a real denominator
of **702 coinciding tails across 187 files**, 110 flags is a **16% cut**, not an
increase. (Reported here as `honesty`'s measurement; not independently reproduced
by this author.) The verdict survives on better ground:

> **519 of the 702 carry no risk signal and are never printed — and two of the
> three oracles live in that discarded set.**

A filter whose discard pile provably contains true positives does not merely have
poor recall. It silently converts *"I have not read these"* into *"these have been
checked"*, which is this campaign's governing failure mode wearing the clothes of
a labour saving. That is the reason not to ship it, and it holds independently of
how favourable the reading-volume arithmetic turns out to be.

### 5h. `S78` is not done, and the tree cannot tell you whether it is

**STATUS: open, and deliberately left so. See the closure decision at the end of
this document — the campaign closes on its criterion without this Step.**

**This element inherited the very failure it diagnoses, and the correction
belongs at its top.** It previously read *"the campaign's only open Step"* — true
— and every reader, including its author and the coordinator, took that to mean
*the campaign's last obstacle*. It is not. `S78` sits in plan phase `W03.P16`,
and the plan says phases `W03.P14` through `P16` *"remain real drift-reduction
work but are not on the closure path."* That paragraph went unread for the whole
campaign while the phrase "one Step from closure" was repeated.

> **Elsewhere a clean report was mistaken for a checked surface. Here a single
> open checkbox was mistaken for an incomplete campaign — the same instrument
> failure with its sign flipped.**

A progress count is an instrument too, and *114 of 115* measures Steps, not
closure. **The document diagnosing scoreboard failure was itself keeping score
wrong**, which is the most exact instance of this element's own thesis that the
campaign produced.

**The sizing instrument had to be replaced before the remainder could be seen.**
Raw substring counting was wrong: the `live` band's 65 and the `runs` band's 60
were roughly **90% CLI argv tokens** — `invoke_cached_cli(["app", "live",
"filed", ...])` — not paths at all. The correct instrument is an AST scan
counting only string constants that are a `/` operand or a `joinpath`/`glob`
argument. Measured that way at `5da2b328f9`:

```
path-composition hits in files WITHOUT a pin declaration   442
path-composition hits in files WITH one                    101
```

with a **17-segment tail carrying no sweep record** — `master.recovery.key`,
`cache`, `drafts`, `logs`, and a thirteen-segment remainder.

**And the harder half, which bears on how anyone judges completeness:**

> **`different-namespace` and `never examined` are byte-identical in the tree.**

The disposition table is the whole argument, and the distinction it turns on is
**visible in the diff that made the change** versus **readable in the tree
afterwards**:

| disposition | what it does to the site | readable afterwards |
|---|---|---|
| `migrate` | removes the literal | no — the site is gone, identical to one that never existed |
| `injected` | renames it to a non-taxonomy token | no — nothing marks the rename as a classification |
| `different-namespace` | leaves it untouched | no |
| `accessor-is-the-subject` | leaves it untouched | no |
| `pin` | declares it in `PINNED_TAXONOMY_LITERALS` | **yes** |
| `injected-but-constrained` (`5g`) | resolves to `pin` — the literal was load-bearing after all | **yes**, via the pin it produces |

All six were visible in the diff at the time. Only the last two are visible to
somebody arriving later with a grep, and the second of those is the first wearing
a different hat. **Four of the six leave nothing a later reader can find.**

**A correction to this element, which is the same failure the element describes.**
A prior revision replaced "four of six" with "four of five", on the grounds that
the sixth outcome was "named nowhere in the vault". It is named **eighteen lines
above this table**, as the heading of element `5g`, in the file that was open at
the time. The original count was right; only the visible-versus-readable
confusion was wrong, and the fix for a contradiction between prose and table was
never to delete a row. This is the `master.recovery.key` shape for the third
time — an absence asserted without reading the file — committed inside the clause
that exists to document it, by the reader who had just written that you must read
the whole file before reporting something missing.

The consequence is that **the tree is not the record**: no scan of the codebase
can answer whether `S78` is complete, because completeness is a fact about which
sites were *classified*, and classification is unreadable for four of the six
outcomes. The durable record is an explicit **swept-literals ledger** — per
segment, whether it was swept now or already swept and confirmed — which the band
reports have been accumulating without anyone having named it as the artefact.

**Every band this campaign closed sits under this table.** `cadrumo.db`,
`secrets`, `iva-wallet`, `invoices`, the LLM trio, `live`, `financial`, the
thirteen-segment small-band tail — for each of them the only closure evidence
still readable in the tree is its `pin` declarations. That is not a further
measurement; it follows from the table, which is exactly why the table is
sufficient on its own.

**This is element 5e's shape one level up.** There, a dead declaration satisfies
the criterion vacuously because there is no site to enrol. Here, an unexamined
literal is indistinguishable from a correctly-excluded one because neither leaves
a mark. **Both are places where silence reads as coverage**, which is the failure
this campaign exists to surface — and finding it in the campaign's own
completeness accounting is the sharpest instance of it.

**This element carries no worked example, deliberately. Two were tried and both
were wrong.**

An incident was offered as the illustration: a `master.recovery.key` sweep
reported complete at "all 20 sites" while a review counted 21 and named the
seventh file as missed.

- **First explanation** — the file set had been enumerated from the files being
  edited, so a site was missed. **Wrong**: no site was missed. It had been
  correctly declared hours earlier under the `secrets` band.
- **Second explanation** — the ledger is keyed by literal, so a file swept under
  band A is invisible to a review of band B. **Also wrong**: the declaration was
  at line 38 of the very file the review read, twenty-two lines above the tuple
  it quoted at line 60, its rationale naming the exact function the review then
  analysed. Not history, not another file. The top of the open buffer.

Each explanation was structurally sound, independently evidenced elsewhere, and
**not what happened here.** The lesson that survives is the one the two failures
teach:

> **A structural explanation that fits the shape of an error is not evidence that
> it produced that one.**

Both were reached for because they fitted, and each was believed a little faster
than the last — the second precisely because the first had just been corrected,
which felt like diligence. **A pattern you have just been burned by is the one
you will over-apply next.**

**The falsifier rests on the disposition table and on nothing else.** Four of the
six dispositions leave nothing a later reader can grep, so a clean scan is
consistent with every literal having been examined *and* with none of them having
been. That argument needs no incident to support it — it is a property of the
classification scheme, demonstrated by every band the campaign closed.

**One argument was offered as support and has been withdrawn from that role.**
The ledger is keyed by literal, so a file swept under band A can present as
unswept to a review of band B. That is true by construction, and it was proposed
as the explanation for the `master.recovery.key` incident — whereupon its only
candidate instance was refuted, the declaration having been in the file the
review read. It is kept here as **structural but unobserved**: zero demonstrated
cases, so it supports nothing and must not be cited as though it did.

**Two secondary points survive as claims in their own right**, both independently
evidenced and neither resting on the retracted incident: a completeness claim
needs its domain stated (*"N sites in the M files I examined"*, never a bare
"all"), and a reviewer who finds extra sites has found a **scope mismatch** until
history or the file itself says otherwise.

**Three accounts, three corrections, one clause.** Two worked examples and then a
supporting argument whose sole instance was refuted — each of them the most
comfortable available explanation, and each accepted a little faster than the one
before. The clause's own lesson describes its own revision history, and that is
the only illustration it is going to get: a third specimen is not wanted here,
and the honest record is that the element is real while every attempt to picture
it was not.

**What would make this "no"**: declaring `S78` complete on a clean scan. A clean
scan is consistent with every remaining literal having been examined *and* with
none of them having been. Equally, a complete ledger whose entries were each
enumerated from the files already being edited.

## This document was itself untracked until hours before closure

Recorded as a finding rather than quietly fixed, because it is the exact class
of gap the campaign exists to surface and a reader who sees only the polished
version would never know.

**This file had never been committed.** `git log --all` on its path returned
nothing; it existed only in one working tree. It was not alone: **104 exec
records existed on disk and 68 were tracked**, so 36 — a third of the evidence
every Step's completion rests on — had no git object behind them. Found by this
campaign's own corpus audit, hours before closure was to be declared, and
committed at `7d09fb29f0` after each was checked complete and confirmed to be a
new-file add carrying no peer working-tree content.

Three things make it worth keeping rather than erasing:

**The campaign nearly closed a third short of its own evidence.** A closure
statement citing exec records that a fresh clone does not contain cites nothing
durable, and `plan-closure-requires-exec-records` makes those records the whole
basis of a Step's completion.

**Every corpus figure quoted before `7d09fb29f0` measured 68 records while 104
existed.** Not wrong about what it examined — wrong about what it was examining.
That is the untracked-file trap in its most expensive form, and it is the same
shape as measuring a working tree and calling it HEAD, inverted: there the name
resolved to the wrong object, here the object was a third of the corpus.

**Untracked is worse than uncommitted.** A modified tracked file has a git
object behind it and is recoverable. An untracked file has none — it is
invisible to `git grep`, to every HEAD-anchored audit, and to recovery.

**That distinction was then tested for real, on live code rather than on
documents.** A revert loop matched every modified file under `entrypoints/cli/`
instead of the twelve it intended, and overwrote peer work with HEAD content.
**Six of eight files were recovered from dangling blobs via
`git fsck --lost-found`; two were unrecoverable**, because their content had
never reached the object store at all.

That is the same hazard as the 36 untracked exec records, and it decided both
outcomes by exactly the same rule: **reaching the object store at all is what
made six recoveries possible and two impossible — and nothing in the workflow
guarantees it.** A file that has been added, committed, or even staged once has
a blob; one that has only ever existed in a working tree has nothing to recover
from. The corpus survived by luck rather than by design, and so did six of those
eight files.

## A protection that was registered but never ran

Recorded because the campaign's own coordinator held the wrong conclusion and
measurement overturned it, which is the shape worth preserving rather than the
outcome.

**The claim** — accumulating isolated storage roots were designed 24-hour
retention rather than leakage, and two lanes were told not to report them.
**Measurement overturned it.** Every root was failing its own `atexit` cleanup on
every run.

**The mechanism, spelled out so the next reader does not rediscover it:**
`atexit` handlers run **last-in-first-out**, and `logging.shutdown` is registered
at `atexit` too. It therefore runs *after* the module's `rmtree`. The log handler
still holds the file open, Windows refuses the unlink, and `ignore_errors=True`
swallows the failure completely. Now fixed and verified by measurement rather
than by inspection: **2207 roots before a fresh run, 2207 after — delta 0**,
where every prior run leaked one.

**Registration is not execution.** The hooks genuinely were registered, and
verifying that is what made the wrong conclusion reasonable. Nobody checked
whether the directories had actually disappeared, which is the only question that
separates the two.

This is the fourth protection in this campaign whose failure is indistinguishable
from its success, and it is a **different mechanism from the other three** —
not a measurement against the wrong object, not a selector broader than its
concept, not a retained handle hiding a write from an instrument, but **a correct
registration standing in for an uncompleted action.** The other three are errors
of measurement; this one is an error of inference from a true observation, which
is why checking harder in the same direction would never have caught it.

## Verdict

**The criterion as worded is not decidable. Restated over path-choosing sites it
is decidable, and it holds at the pinned revision.**

What can be defended, and what should be written rather than a percentage:

> No unenrolled path-choosing site is detectable by either instrument at the
> pinned revision, and the residual is bounded by three named classes rather
> than by an assertion.

What must **not** be written is *"all file-producing sites are enrolled"*. Nearly
half of them have no enrollment answer to give, so the sentence is not true, not
false, and not checkable — and a campaign that exists to stop a silence being
read as coverage must not close by doing exactly that.

**The plan's completion percentage neither establishes nor refutes this.** The
plan counts Steps; Steps are a proxy. A reader arriving at this document will
reach for that percentage first precisely because it is the one number that looks
like an answer, which is why it is named here and set aside.

**Remaining elements** keep their own statuses above. This verdict resolves the
criterion element only; the conjunction rule stated at the top of this document
still governs the whole, and one "not satisfied" elsewhere still makes the
overall statement "no".

## Closure decision

**The campaign is closed on its criterion. `S78` remains open, recorded as
drift-reduction work, with its residual named below.**

**The conjunction rule does not block this, and the reason is a correction to
this document.** The rule governs whether *every element* of this statement is
satisfied — a stricter and broader question than the campaign's closure
criterion. `S78` sits in plan phase `W03.P16`, and the plan states that phases
`W03.P14` through `P16` *"remain real drift-reduction work but are not on the
closure path under the operator's sharpened definition."* So element `5h` being
open makes this **statement** incomplete without making the **campaign**
unclosed. Those were being read as one thing, including here.

**`S78` is deliberately not checked.** A visibly open Step with its limits
written down is a better artefact than a checked box carrying a caveat: after
`S114` it is established that a narrowed close is indistinguishable from
abandonment to any reader who does not find the exec record.

### What `S78` reached, and what it did not

**Measured movement, two instruments, same direction** — the strongest positive
evidence available, and evidence of progress rather than completion:

```
AST path-composition scan (tests)   442 -> 353 undeclared,  pins 101 -> 147
coinciding-tail population           702 -> 307   (independent instrument)
```

**Method substitution.** The Step specifies a per-package walk gated by the
provenance gate scoped to each package plus that package's own suite. Execution
was per-literal-band, verified by `ruff` and `pytest` over the specific files
edited. An independent read confirmed no band ran the specified gate and no
package walk is recorded anywhere in the feature.

**Scope ambiguity, unresolved.** The Step's scope field names
`src/cadrumo/tests/` (171 modules, 28 undeclared hits); its own "roughly 350
sites" denominator matches the whole test tree (353). The two readings differ by
an order of magnitude and the text does not say which is meant.

**Most of the work never reached the vault.** The durable ledger is a single exec
record covering a ten-file batch, which describes its own inputs as
"pre-identified" — so even there the enumeration method is unstated. The rest
exists in the relay chain. This is element `5h`'s finding one level out: the tree
cannot say whether `S78` is complete, and neither can the record.

**An open question, not a count.** A sample of unclassified sites was measured at
roughly 23% rename-sensitive. Two things about it are unresolved and each changes
its meaning entirely: whether the sample drew from `src/cadrumo/tests/` or the
whole tree, and whether *rename-sensitive* means *not enrolled* or merely *would
need editing* — a rename-sensitive site that is a correctly-declared pin is
resolved work. It is recorded here as an open question and must not be cited as a
residual count until both are answered.

### The claim this closure makes

> Every literal in the enumerated bands was classified under one of six
> dispositions; the path-composition population fell 442 → 353 in tests and
> 702 → 307 by an independent instrument; 28 undeclared hits remain inside the
> Step's declared scope and 353 across the whole test tree; **no claim is made
> that the enumerated bands exhaust the corpus**, because four of six
> dispositions leave no readable trace and no scan can establish exhaustion.

The final clause is the load-bearing one. A future reader who takes anything from
this section should take that.

### What the campaign learned about its own reasoning

On the last technical question it asked — whether a two-member anchor enum still
earns its place — the campaign produced **four justifications in one thread,
across three agents, on one subsystem. Every one was refuted by measurement.**
The original was false rather than merely dated, invalidated by the campaign's
own bug fix. Three replacements followed, each structurally sound, each reached
for because it fitted, and each accepted a little faster than the last.

> **Four expired justifications in one thread, three agents, one subsystem — and
> what survived is *"we do not know."* That is the correct resting place and it
> cost all four to reach.**

That sentence is in this document because a reader who understands why it took
four attempts will read the rest of it correctly. The mechanism, stated once:

**Soundness kept substituting for instantiation.** Each account was checked for
whether it *could* be true and never for whether it *was what happened*. The
cheapest check of the four — *"has this ever been observed?"* — went unasked the
longest, because a claim that costs nothing to state invites nothing to test it.
And the three agents who supplied the failed accounts had each spent that same
thread correcting someone else's expired reasoning: **practising the check on
others manufactures the feeling of having already applied it.**

The resting place is not a gap in the record. An open question with its refuted
answers written down is a stronger artefact than a confident answer nobody
measured — which is the same judgement this document makes about leaving `S78`
visibly open.
