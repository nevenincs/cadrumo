---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:f962abbb790997e1818b42ba719b59bd9d450e96f7fdc65d720f7cbe759c44a6'
related:
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-08-03-canonical-storage-management-plan]]'
  - '[[2026-08-03-canonical-storage-management-closure-criterion-reference]]'
  - '[[2026-08-03-canonical-storage-management-closure-statement-reference]]'
  - '[[2026-08-03-canonical-storage-management-honesty-review-audit]]'
  - '[[2026-08-03-canonical-storage-management-self-duplication-review-audit]]'
---

# `canonical-storage-management` audit: `closure criterion census`

## Scope

The operator's criterion, verbatim: *"if we can satisfy that all file producing
sites are enrolled we're done."* Everything measured so far — Steps, gates,
families, residuals — is a proxy for it. This measures the criterion itself.

Everything is pinned to `611df3a67e`, read out of `git show`, never the working
tree. The taxonomy module was refactored again during this pass; nothing below
comes from the tree as it stood at any moment.

## Findings

### the-instrument-and-what-it-cannot-reach | none | An AST census over write primitives, quantifying over code rather than over the declaration

A declaration-quantified census cannot see an unenrolled site — the site's
absence from the declaration is exactly what is being asked about. So the
instrument here walks 1,451 production modules and matches **file-producing
primitives** in the AST: `Path.write_text` / `write_bytes` / `mkdir` / `touch` /
`open` in a writing mode, `os.makedirs`, the `shutil` copy and move family,
`tempfile` factories, and arity-discriminated `Path.replace` / `rename`. Each
match's path expression is then traced back through local assignments, class
attributes and module constants to its originating symbol.

Three things it cannot reach, stated rather than assumed away:

**Duck-typed method names.** `save`, `touch`, `rename` and `replace` are not
uniquely filesystem operations, and without type inference the census cannot
distinguish `Path.touch()` from `Session.touch()`. This is not hypothetical: a
first pass that also treated `.save` as a primitive returned 138 of 235 matches,
and spot-reading showed almost all were `repository.save(...)` — encrypted SQL
secure-object writes with no filesystem involvement at all.

**Writes through a retained handle or a library that opens its own file.** A
handler that binds a stream once and writes through it forever presents one
syntactic site and unbounded real writes.

**Cross-module composition and dynamic dispatch**, which the honesty review
already enumerated as structurally unenumerable.

### the-count-and-its-false-positive-floor | CORRECTED | The site total stands; the derived "92" came from a truncated capture and is withdrawn

**Correction, recorded in place.** The figure below was computed from a scratch
capture written with `... 2>&1 > file`, which is the wrong redirection order and
wrote only **55 of the 99** site lines to disk. The total of 99 came off the
terminal and is sound. The *ambiguous* enumeration — "8 sites, 7 cleared by
reading, therefore 92" — was read off the truncated file and undercounts: the
packaged scanner reports **11** ambiguous. **The derived figure 92 is withdrawn.**

Nothing downstream moves. The total, the 44 pass-through sites, and the
provenance classification all came from the untruncated terminal output, and the
audit's conclusion rests on those. Only the subtraction was wrong.

The durable fix is the one this audit itself recommended, now applied to its own
number: the census ships as `dev/write_site_census.py` (commit `30f2493ee1`) with
a test pinning both selector discriminations, and the count is obtained by
running `python -m dev.write_site_census <revision>` rather than by reading a
figure out of prose. A count in prose has no maintainer; that is what produced
this correction, `R16`'s three amendments, and the burndown's `28`.

This is also the second published number today whose defect was in the
*capture*, not the reasoning — the first being a working-tree read reported as
HEAD. Both were caught by building a better instrument rather than by re-reading
the old output, which is the argument for the tool existing.

The original finding follows unedited.

### the-original-count-claim | superseded | 92 file-producing sites, and an independent reproduction of the corrected ~99

The corrected selector finds **99 matching sites**. Of those, 8 use the
duck-typed names above; reading each one's traced receiver clears **7** as
non-filesystem — two `BytesIO` buffers, a `StringIO`, a `BucketSession`, a
`ProfileRepository`, a `BucketMaintenanceService`, and an active-bucket session.
One is real: an `openpyxl` workbook saved to a `Path` in the registry workbook
parity module. So the defensible figure is **92 file-producing sites, as an
upper bound** — upper, because the unambiguous primitives are reliable but the
duck-typed class can only be cleared by reading, and only these 8 were reachable
to read.

That figure independently reproduces the campaign's own corrected `~99` by a
different mechanism, which is worth recording because that number was itself a
correction: an earlier census counted 267 by matching every attribute call named
`replace`, so every `str.replace(' ', '')` scored as a `Path.replace` rename.
Two instruments, built independently, landing in the same place is the strongest
corroboration available here.

### the-criterion-is-not-well-formed-over-the-set-it-names | high | 44 of 99 sites have no enrollment answer of their own, because the path was chosen by their caller

This is the substantive result, and it is why no one has been able to measure
the criterion directly.

Classified by where the written path comes from: **44 pass-through** (the path
arrives as a caller argument, or as a `self` attribute set by a constructor),
**30 local** (resolved to a named helper or an in-place `Path(...)`
construction), **12 taxonomy** (traced to a storage accessor or a settings
field), **9 unresolved**, **4 literal**.

The pass-through class is the problem. A primitive doing `path.parent.mkdir()`
on a path it was handed **has no enrollment answer of its own** — its answer is
"wherever the caller said". Asking whether that site is enrolled is not a
question with a truth value; the question relocates to whoever chose the path.
Nearly half the sites are in that state, so *"all file-producing sites are
enrolled"* cannot be evaluated site-by-site over file-producing sites. The
closure statement had already glimpsed this and estimated "roughly fifteen"
pass-through primitives; measured over the full set it is 44.

The criterion becomes well-formed when restated over **path-choosing sites** —
the places that decide a location rather than the places that write to one. That
is a strictly smaller set, and unlike the write set it is decidable, because
choosing a path means composing it from a root or a declared field, which is a
syntactic act the AST can see.

### restated-over-choosing-sites-the-criterion-currently-holds | none | The project already built this instrument, and it is green with an empty debt table

The provenance gate is precisely a census of path-choosing sites: it walks every
packaged module, production and test alike, finds each place the storage root
has something joined onto it, and requires the site to be a declared producer.
At the pinned commit it passes — 27 tests — with only **4 permitted producers**
and, notably, `PENDING_ENROLLMENT` reduced to the empty tuple. That table is
declared to only ever shrink, so an empty one is a real statement rather than an
unfilled scaffold.

So the criterion's decidable content — no site composes a storage location
outside a declared producer — **holds at `611df3a67e`**.

### the-choosing-census-has-its-own-blind-spot-and-it-is-covered-elsewhere | medium | The provenance gate watches the root, so a literal joined onto a category field is invisible to it

The gate keys on joins onto the storage **root**. A site that chooses a path by
joining a literal onto a *category* field — `cadrumo_audit_dir / "live"` — never
touches the root symbol and is invisible to it. That is exactly the
nested-ungoverned class, and it is the reason the criterion cannot rest on the
provenance gate alone.

It is covered, but by a different instrument: the taint-based family census, whose
four families are all now declared. Worth stating plainly that the criterion's
coverage is therefore the **union of two instruments with different blind spots**,
neither sufficient alone — and that the union is still not a proof, because the
family census is itself incomplete by construction for the four classes it names.

## Recommendations

Restate the closure criterion over path-choosing sites rather than
file-producing sites, and say why: nearly half the write sites are pass-through
primitives whose enrollment answer lives at their call sites, so the criterion as
worded cannot be evaluated even in principle. This is a wording change that makes
an unanswerable question answerable, not a lowering of the bar.

Record the two-instrument union explicitly in the closure statement — provenance
gate for root-composed paths, family census for category-composed paths — with
each instrument's blind spot named beside it. A reader who finds only one will
otherwise reasonably conclude the coverage is complete.

Do not quote 92 as a settled figure. Quote it as an upper bound at a named commit
with the duck-typed class stated, or cite the census script so a reader recomputes.
This is the same discipline the corpus review recommended after the burndown's
`28`, and this number will move the moment anyone adds a `mkdir`.

## Verdict

**The criterion as worded is not decidable, and that is a property of the
wording rather than of the campaign's state.** Nearly half of all file-producing
sites are pass-through primitives with no enrollment answer of their own.

**Restated over path-choosing sites, it is decidable, and it currently holds.**
No site composes a storage location outside a declared producer at
`611df3a67e`: the provenance gate is green with an empty pending table, and the
four nested-literal families are declared.

**What is not established, and cannot be by these instruments:** that the two
censuses' union is complete. Each has a blind spot the other partly covers, and
both are blind to writes through retained handles, cross-module composition, and
libraries that name their own files. The strongest honest statement is therefore
narrower than "done": *no unenrolled path-choosing site is detectable by either
instrument at this commit, and the residual is bounded by three named classes
rather than by an assertion.*

If the campaign wants to declare closure on this criterion, that sentence is what
it can defend. It is a good result — it is simply not the same claim as "all file
producing sites are enrolled", and the difference is worth keeping visible,
because the whole campaign exists to stop a silence being read as coverage.

One disagreement to record: the plan's completion percentage counts Steps. Steps
are not the criterion, and a plan at any percentage neither establishes nor
refutes what is measured here.
