---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:8ead0ce99a891737d86a6b2f8e0d52ddf1de947bbd9ff202eac38aa322fdd39c'
step_id: 'S204'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Dispatch a fresh Luna xhigh agent swarm over every audited functionality cluster

## Scope

- `src/cadrumo/`

## Description

Discover functionality clusters the ten named ones do not cover, by structural analysis
rather than semantic search, because the semantic instrument is degraded.

Build an AST scanner over the production module set with three independent passes: symbol names
declared in two or more packages, normalised function-body hashes that collide across modules, and
distinctive string literals shared across modules. Self-test the scanner before trusting it. Apply
the substitutability pre-filter to every candidate before calling it actionable.

## Outcome

SATISFIED. Four new actionable clusters and one extraction candidate, none of them among the
ten already covered and none of them visible to the clone runner.

Method substitution, stated plainly. A semantic sweep could not be the discovery method: the index
holds 466 code sections against 3982 tracked files while reporting its generation succeeded, and
all ten of the S205 sweeps missed. A structural scanner was written instead. Its distinguishing
pass renames every local identifier to a positional placeholder and blanks every string before
hashing a function body, so a concept implemented twice under different names, with different
variables and different messages, still collides. That is precisely the duplication the clone
runner's token matcher cannot see, which is why its twelve groups and this scan's findings barely
intersect.

Instrument discrimination, proven before use. The scanner was fed a hand-built twin pair differing
in every identifier, and an unrelated function. It collided the twins and did not collide the
unrelated body. A scanner that failed either half would be blind or pure noise respectively.

Corpus. 1372 production modules, from 3660 tracked Python files under the source tree with the 2276
under a tests directory and the conftest modules excluded. All 1372 parsed; zero unparseable. Pass
A scanned 11996 distinct symbol names. Pass B hashed 8947 function bodies of at least twelve AST
nodes. Pass C scanned 5895 literals.

ACTIONABLE 1, formula-runtime casilla accessor. The registry formula-op module declares a public
`numeric_casilla_value` whose own docstring states it is the generic accessor SHARED BY the M210,
M131 módulos and M303 módulos families. The main formula-runtime module nevertheless carries
`_m100_numeric_casilla_value`, a body-identical private copy with six call sites, while ALREADY
importing from that same ops module in four places and aliasing the very error class the copy
raises. Pre-filter: identical signature, identical body, identical message and translation key,
same error class reached through an alias. The canonical is a strict superset. Promotion is a
no-behaviour-change substitution.

ACTIONABLE 2, evidence-covers-snapshot invariant. The aggregation package publicly exports
`assert_evidence_covers_snapshot` in its `__all__`. The modelo verification module carries
`_assert_evidence_covers_snapshot`: same logic, same computed sets, same message string, but
raising the broader base error where the canonical raises its validation subclass. Pre-filter: the
subclass inherits from the base, so the canonical raises a strictly narrower type that any existing
handler still catches, and it is a superset. Compounding the finding, the AGGREGATION package's own
test imports the MODELO package's private copy across a package boundary to test it, while the
public canonical sits in the package that test lives in. That import is one of the test-only
private-import debts the hygiene ratchet counts.

ACTIONABLE 3, full-text search OR-group builder. `_fts_or_group` is byte-identical in the command
search index and the corpus search lexical index: same signature, same dedupe-preserving-order
body, same quoted OR join. Both are application packages, so neither may reach into the other's
private module; this needs a shared leaf, not a promotion.

ACTIONABLE 4, export field-overlap predicate. `_export_fields_overlap` is byte-identical in the
application filing export module and the domain registry export module. Pre-filter: identical
signature over the same definition type, identical interval-overlap arithmetic, no differing
constraint. Because the layering contract permits application to import domain and forbids the
reverse, the domain copy is the only admissible canonical home.

EXTRACTION CANDIDATE, on-disk journal repository substrate. The config-reset journal repository and
the profile-bundle-export journal repository share five structurally identical members: the
constructor, the root property, the existing-root validator, the root creator and the writer, plus
an identical load body. Pre-filter result is deliberately different here: neither CLASS is
substitutable, because one carries exclusive-create, incompleteness-refusal, ownership and
retention guards the other lacks, while the other carries a lock target, a delete and a scan. The
classes are constraint-shape divergent; the file-substrate helpers beneath them are not. The
remediation is extraction of a shared journal substrate, not replacement of one by the other.

FILTERED OUT by the pre-filter, recorded so the filter's work is visible. The catalogue-input
coercion validator appears in three domain model modules with a 155-node identical shape, but each
is bound to its own catalogue class, keys on its own field name and validates its own element type;
not substitutable. The M347 declarable-party fold appears in the counterpart and invoice binding
families with identical threshold arithmetic, but over two different observation types with no
shared protocol; not substitutable, and its regulatory threshold is already read from the single
core constant in both, so the value cannot drift. Pass A's 334 names appearing in two or more
packages are dominated by protocol method names such as load, get, save, exists and delete, which
are interface conformance rather than duplication.

Novelty confirmed rather than assumed. Exact search over the vault returns zero documents naming
the casilla accessor, the OR-group builder or the field-overlap predicate. The evidence invariant
is named in three vault documents, but every one describes the invariant itself; none records that
two implementations of it exist. None of the five appears in the clone runner's recorded
dispositions, which is consistent with a token matcher that cannot see renamed twins.

## Notes

What this search could NOT reach, stated so the coverage is not overread.

The scan is confined to the 1372 production modules. Duplication between a production module and a
test helper, and duplication among the 2276 test modules, is outside it.

Pass B only collides bodies whose normalised AST is EXACTLY equal. A concept implemented twice with
one extra guard clause, a reordered pair of statements, or a loop written once as a comprehension
does not collide. This finds identical twins, not similar ones, so a null result from it is much
weaker evidence than a hit.

The twelve-node floor was chosen to suppress boilerplate. Genuine short duplicated helpers below
that size are invisible.

Pass A cannot distinguish a duplicated implementation from an interface implemented many times, and
Pass C surfaced only docstrings and CLI tokens already covered by the five-surface sweep; neither
produced a finding on its own. Only Pass B did.

Cross-language duplication, duplication between source and the registry TOML tree, and duplication
between source and the documentation tree are all outside this instrument.

No remediation was performed. This Step discovers and classifies; each cluster needs its own Step
with a verification gate.

The semantic code index was degraded throughout this Phase: the service reported `Source code
sections: 466` against 3982 tracked Python files while declaring its code generation succeeded.
The service was not restarted and not reindexed. No absence recorded here rests on a semantic
miss.

## Re-verified 2026-07-28 at HEAD `a4534b8a2bfbf9d9d95eed883f98d2098a437ec0`

Written three days after the sections above, against a tree that has moved. The
figures below supersede any that conflict; nothing above is edited, so the
original measurement stays readable next to what it became.

The four actionable clusters and the extraction candidate this Step discovered
have all been REMEDIATED. Each became its own Step and each has landed: the
M100 casilla-accessor copy retired onto the public accessor, the modelo
evidence-covers-snapshot copy routed onto the public assertion with its
cross-package private import removed, the byte-identical FTS or-group builder
given one shared leaf home, the filing export-field overlap predicate routed
onto the registry copy, and the journal-repository substrate extracted rather
than replaced, the two classes being constraint-shape divergent.

Confirmed independently rather than accepted from the commits. A fresh
structural scan was run with the same normalisation principle - every local
identifier rewritten to a positional placeholder, every string blanked, the
docstring stripped, the body hashed - and its discrimination proven before use
against a hand-built twin pair and an unrelated control. Corpus: 1411
production modules, 4250 bodies hashed at a 70-node floor, 0 unparseable. NONE
of the four retired clusters appears in the result. The retirements are real.

The scan surfaces 39 collision groups, 25 spanning more than one file. Those
are NOT reported as duplication here and must not be read as such: the
substitutability pre-filter has not been applied to them, and a prior pass in
this project that skipped that filter reached a 96 percent false-positive rate,
52 of 54 sites blocked by constraint incompatibility. Several are visibly
idiomatic on inspection - repository `load` templates, two-attribute `__init__`
bodies, `_*_unique` validators. They are recorded as a lower bound needing
per-cluster adjudication, which is the honest handover rather than a finding.

The instrument's limit, restated because it governs how the null is read: it
collides only exactly-equal normalised bodies, so one extra guard clause or a
reordered statement pair defeats it. A hit is strong evidence; a null is weak.

Command and result for the structural scan cited above, added because the
evidence bar asks for the invocation and not only its corpus. The scanner was
run as a standalone module against the production tree:
`python ast_twin_scan.py` over `src/cadrumo`, production modules only, 70-node
floor. Result line: `corpus: 1411 production modules, 4250 bodies hashed, 0
unparseable` followed by `collision groups: 39 total, 25 spanning more than one
file`, exit code 0. Its discrimination proof printed first and must pass or the
run aborts: `discrimination: twins collide = True (want True); control collides
= False (want False)`.
