---
tags:
  - '#audit'
  - '#import-hygiene-test-debt'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:616012c831f618a4056b06bcc0192d3578fa5f3c2bcfba583840110567135018'
related: []
---

# `import-hygiene-test-debt` audit: `test-only private-reach regression: per-site adjudication`

## Scope

The test-only private-reach ratchet in the import-hygiene gate was red at 107 live sites
against 95 documented in the test-debt allowlist. The gate compares site identities keyed
by importer path, target module and imported names, so the fix is per-site adjudication;
raising the allowlist to absorb the difference is the precise failure the ratchet exists
to catch, and was ruled out at dispatch.

Each of the thirteen undocumented sites was judged on its own, choosing between promoting
the symbol to its owning package's public facade and rewriting the import, recording a
named and reasoned allowlist entry, or removing the reach as a design defect. The
adjacent lazy-facade binding failure on the ledger package was folded in because it sat
on a facade this work already owned.

## Findings

### ratchet-reads-the-working-tree | critical | uncommitted peer work reds this gate for the whole team

The scanner walks files on disk, not the committed tree. The single site left undocumented
at the end of this work does not exist at HEAD at all: it is an added line inside roughly
two hundred lines of another agent's uncommitted work in a calculations test module. At
HEAD content the ratchet reads ninety-five live against ninety-five documented and is
green; the residual red is entirely working-tree state belonging to someone else.

This is the structural explanation for the count churn observed across the session, where
the live figure moved between one hundred and seven and ninety-five while the documented
figure moved independently as concurrent work landed. Neither number was stable because
neither was a property of any commit. It also means no committed change can clear the
gate while the work in progress exists, and the agent holding that work will clear it
merely by finishing, without ever seeing the failure attributed to them.

The site was deliberately left alone. Editing the file would have entangled unrelated
work in progress, and writing an allowlist entry for a reach that exists only in a working
copy would record speculative state as a durable decision.

**The reproduction, verifiable in two commands.** Take the calculations test module that
the gate names, and count the two private symbols it is reported as reaching. Against the
committed blob the count is zero; against the working copy it is four, on a single import
line. The file is modified but uncommitted, and it stayed that way across every
measurement in this session while the branch tip advanced underneath it. So the gate
fails three of its tests at a commit where the offending import does not exist in the
commit at all.

That is a sharper demonstration than the count churn, because it is one named site rather
than a moving aggregate, and because the two counts disagree at the same instant on the
same machine. It also isolates the mechanism cleanly: the disagreement is not caused by
timing, parallelism, caching or the registry-fingerprint race that produces transient
collection errors elsewhere in this tree. It is caused solely by which bytes the scanner
chose to read. Anyone re-verifying this finding later should compare the committed blob
against the working copy first, before reaching for any of those other explanations.

### gate-is-red-with-three-signatures | critical | all three failures are one site, and none is a stale entry

The gate is RED at working-tree state. A sequential full-module run reports three failed
and thirty-two passed: the count ratchet, the named-set equality check, and the
live-occurrence reconciliation. An independent run by another reader reported the same
three, so the signature is reproducible even though the underlying scan is not.

**All three share a single root cause, and it is the one uncommitted site.** The count
ratchet fails at ninety-six live against ninety-five recorded. The set check fails with
exactly one unnamed reach. The live-occurrence check asserts in BOTH directions from one
per-triple count comparison, and it is failing on its SECOND assertion, the one covering
occurrences that outnumber their records. Its first assertion, the one covering entries
that no longer answer a live reach, passes. There are ZERO stale entries. The allowlist
needs nothing removed.

That distinction matters because the check's name reads as though it can only mean stale
documentation, which invites a reconciliation pass that would find nothing to reconcile and
risks deleting live entries to satisfy a misread. The evidence is the assertion the
traceback names, not the test's title.

**A reporting failure of this campaign's own, recorded rather than smoothed over.** The
earlier report of this ratchet described a single undocumented site and left the gate
looking like one failing dimension. It was derived from a direct enumeration of the scan
rather than from running the gate module, and that enumeration compared documented and live
sites as SETS. Set comparison is blind to multiplicity, which is precisely the blindness
the live-occurrence check exists to close and says so in its own docstring. A second
partial reading then checked only the first of that check's two assertions. Both errors
pushed the same way: they understated how many gate surfaces were red. The full module
should have been run before reporting, and the count is now taken from the gate rather than
from a reimplementation of it.

### reaches-past-already-public-symbols | high | five of thirteen needed no promotion at all

Five sites were not private-access decisions in any real sense. The symbols were already
exported from their owning package facades, and the tests had simply spelled the import
against the private module instead. A withholding observation type was already on the
registry facade beside its sibling observation types, and the production assembler the
test exercises already imported it publicly. A ledger precondition condition and a filer
fact path were already in the ledger facade's exports and lazy map. A result-disposition
projection was already exported from the calculations facade, on the line directly above
the private import in the same file.

Had these been swept as a group rather than judged individually, the likely outcome was
either allowlist entries recording non-existent debt or promotions of already-promoted
symbols. The count would have gone green and the tree would have been worse. This is the
strongest argument in the exercise for per-site adjudication over any aggregate remedy.

### asymmetric-constant-family | high | half a constant family was public and half was private

Two application packages reached the same private deadlines module for the same
membership set governing which profile paths claim the IVA block. The instinctive reading
is that two consumers prove a shared primitive, but the decisive evidence was narrower:
the facade already exported the counterpart constant naming the paths the block requires.
The two constants are one family read from opposite directions, and only one direction
had a public home. The asymmetry was the defect, not the consumer count. Promoted under a
name stating what the set does rather than mechanically stripping the leading underscore,
with the Spanish domain stems and every profile path string left untouched.

### private-helper-reaches-are-not-promotion-candidates | medium | four resolved by removing the reach

Four reaches targeted genuinely private helpers, where promotion would have been the wrong
remedy because it mints a public surface for one test's convenience. In each case the
property under test was already reachable another way. A withholding row-building helper
already had intra-package tests in its owning package, and the application-layer test was
asserting a domain internal from outside; the assertion moved to the owning package beside
its siblings, carrying over one genuinely missing case rather than dropping it. A filer
scope helper's real claim was producer-agnostic and the neighbouring property was already
gated inside the ledger package, so the test now raises through the public resolver. A
profile resolver had exactly one caller, a test, and the public entry point peels the same
refusals in the same order; retargeting it was a strict improvement, because the previous
shape hand-built its input and bypassed the canonical token projection every real caller
traverses.

### identity-gate-must-name-its-target | medium | one reach is correct and is now documented

A single site earned an allowlist entry on its merits. The test is an identity gate
asserting that the scope mapper bound in two separate modules is the same object as the
canonical definition, which cannot be expressed without naming the defining module. The
symbol has no cross-package production consumer. Promoting it would have created exactly
the caller-reachable override door the module exists to prove absent, leaving the gate
asserting the absence of a surface the promotion had just added.

### lazy-binding-drift-was-two-sided | medium | the name had fallen out of two places, not one

The ledger facade exposed a consent rederivation error through its lazy export map while
that name was missing from both the type-checking binding block and the declared exports.
It therefore resolved correctly at runtime while every consumer typed it as an untyped
object and no declared public surface carried it. Its eight siblings from the same private
module were bound in both places. A sweep of the whole facade found the asymmetry isolated
to this one name across roughly two hundred and seventy lazy entries.

## Recommendations

Tied to `ratchet-reads-the-working-tree`: a follow-on ADR should decide what a structural
ratchet is a property OF. The options are that it keeps scanning the working tree and is
understood as a local pre-commit signal that cannot be held green in a shared tree, or
that it scans committed content so its verdict is attributable to a commit and reproducible
in continuous integration. The present shape gives a shared-tree failure no owner, because
the agent whose uncommitted work causes it is not the agent who sees it fail. Any decision
should also state whether the same reasoning binds the other working-tree-scanning
structural gates in this repository, since the defect is generic to the shape rather than
specific to this ratchet.

Tied to `reaches-past-already-public-symbols`: the scanner reports a private-module import
without checking whether the same symbol is already exported from the owning facade. Adding
that distinction to its output would separate a genuine access decision from a mis-spelled
import, which is the difference between work that needs judgement and work that needs a
one-line rewrite. Five of thirteen sites in this batch were the latter, and nothing in the
gate's message said so.

Tied to `identity-gate-must-name-its-target`: the allowlist entry format should be
confirmed as the sanctioned home for reaches that are correct by construction rather than
tolerated debt. The file's name frames every entry as debt to be repaid, which mislabels a
reach that must never be repaid because repaying it would defeat the test. Either the
format grows a category for a permanent and reasoned reach, or the naming stops implying
that every entry is provisional.
