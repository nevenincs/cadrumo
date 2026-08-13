---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:4b089d1594f94414b22b3afcca15ae8df6783014f938e1b814d89d52addfef84'
step_id: 'S82'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# Build the identity-pattern canary the 2026-05-30 security audit recommended and nobody built, reusing the sanitiser's existing residual-identity detection rather than a second copy - pattern plus the project's own control-letter checksum via validate_identity, findings that never carry the matched text, and path-scoped exclusions with a stated reason each rather than any value allowlist since an allowlist would itself carry the identifier. Census measured first across 40325 text files: 2247 checksum-valid occurrences in 778 files, 33 distinct values, split 1922 in tests, 272 in vault, 15 in docs, 15 in eleven production-source files, 12 in locales - so pattern plus checksum alone is unusable as a gate and the fixture convention is undocumented

## Scope

- `dev/`

## Description

- Re-measured the census at HEAD rather than trusting the row's figures.
- Relocated the sanitiser's residual-identity detection out of its test
  package into `dev/sanitizer/_residual_identity.py` and exported it from the
  package facade, because it now has a non-test consumer.
- Added `checksum_valid_spans`, one match-and-verify loop both the PDF surface
  scan and the working-tree canary run over.
- Rewrote `dev/identity/_tree_scan.py`: blocking scope narrowed to data
  payloads, exclusions credited independently per fragment, advisory census
  added for the population the gate excludes.
- Added the `dev/identity` facade, a `python -m dev.identity` report, and the
  gate at `dev/identity/tests/test_identity_canary.py`.
- Enrolled `dev/identity/tests` in the dev-tooling lane.

## Outcome

The canary ships and the gate is green: 17,696 data files scanned, zero
findings. Detection is not duplicated. The pattern, the control-letter
checksum and the value-free finding shape all come from the sanitiser's
existing scan, which imports the project's own `validate_identity`; the scan
moved to the sanitiser package facade so the canary reaches it through a
public import rather than a private module in another package's test
directory, and both surfaces now share one match-and-verify loop.

The census reproduced within drift. Measured across 41,986 text files: 2,333
checksum-valid occurrences in 813 files, 38 distinct values, split 1,980 in
tests, 289 in the vault, 16 in twelve production-source files, 15 in docs, 12
in shipped corpus data, 12 in locales, 7 in dev tooling. The row measured
2,247 across 40,325 files with 33 distinct values; the tree has grown, the
shape of the finding has not.

The delivery is narrower than the row asks for, deliberately. The row calls
for an identity-pattern canary; what ships gates data payloads only -- `.json`,
`.csv`, `.toml`, `.yml` and siblings -- and reports source, prose and the
excluded paths as advisory instead of failing on them. Every one of the 2,333
occurrences was triaged with the value redacted, and every occurrence outside
tests and the vault is a documentation example: format illustrations in
operator help, docstring specimens, a demo tax id in the README, the
authority's own worked example in bundled BOE and AEAT text. Nothing in the
repository declares which values are deliberate, so pattern plus checksum over
the whole tree is unusable exactly as the row says. A payload is different: no
legitimate reason exists to ship a taxpayer identity as data, that is the
shape the motivating exposure took, and the payload surface is provably clean
today.

What the row asks for that this excludes: a canary over source and prose. That
population is 2,335 occurrences and it stays ungated. The open item is a
declared synthetic-identity convention -- a documented set of example
identities that production docstrings, locale help and READMEs draw from --
without which no gate can separate a deliberate example from a real leak in
those surfaces. The advisory census exists so the size of that gap stays
visible rather than silent; a test asserts the excluded population is
non-empty, so if it ever empties the gate must widen rather than the test
being deleted.

Exclusions are path-scoped with a stated reason each: the test corpus, fixture
payloads, locale catalogues, bundled corpus text and recorded CLI transcripts.
There is no value allowlist, and none is possible: storing values republishes
them, and storing hashes does not help because the eight-digit-plus-letter
space is brute-forceable from an unsalted digest. Suppression is credited to
every exclusion covering an occurrence rather than the first declared, so
declaration order cannot make one exclusion look alive on another's work; a
gate fails any exclusion that has stopped suppressing anything. A vault
exclusion was dropped during the build for exactly that reason -- it covered
no data file.

The gate was proven to bite twice. Permanently, by positive controls that
build a real temporary git repository outside this tree, plant an all-zero
checksum-valid specimen, and assert the real scanner finds it -- tracked and
untracked both, with a wrong-control-letter twin proving the checksum, not the
pattern, is what keeps the gate usable. Once by hand, by writing an untracked
payload into the working tree, running the repository gate, and removing the
file: the gate failed and named the location, the line and the pattern class
and nothing else. No finding, no rendering and no failure message carries the
matched value; a test builds every reader-visible surface and asserts the
value and its body are absent from all of them.

Nine files in one commit, `6867e4ee0e`. The relocated detection keeps its own
gate green at eleven tests; the identity gate is nine; the two lanes together
are 111.

## Notes

Two tree-wide hygiene gates are red at HEAD and stay red: the mock inventory's
fake-stub-dummy check and the monkeypatch inventory. Both failures cite
`src/cadrumo` test files under other campaigns and neither names a file in
this Step's surface; the identity and sanitiser lanes are green.

`ty` reports diagnostics in the pre-existing hex-64 and identifier census
probes that share the `dev/identity` directory. None are in the modules this
Step wrote or changed, and none were introduced here.

## Correction

Code review found the first delivery not sound and the Step was re-opened. The
remediation is commit `f708875112`, six files, +1008 / -96.

What the review found. The canary was blind to gitignored files while its own
docstring claimed the opposite: enumeration ran through a single
`--exclude-standard` pass, which applies `.gitignore`, so every ignored file was
omitted. The originating incident was an operator identity in an ignored
environment file, and that exact file was invisible to the delivery built to
catch it. Detection also carried only the natural-person tax-identity shape, so
a legal entity's CIF and any ES-prefixed intra-community spelling passed the
gate green, while an exclusion reason in the same module asserted CIF awareness
the detector did not possess. The `.env` entry in the data-suffix set matched
nothing named `.env`, because a leading-dot filename is all stem and has no
suffix. Four smaller defects: the advisory observability tripwire counted the
canary's own planted constant and so could never fire; unreadable files were
swallowed and still counted as scanned; the module docstring cited a vault
audit, which the reference direction forbids; and three full-tree sweeps ran per
test session on a lane that runs pytest in parallel over a network-backed copy.

The originating incident's own file is now visible, and the gate would have
caught what it was built for. A second enumeration pass reads ignored content.
Proven by hand against this repository: a synthetic payload written into a
genuinely gitignored location is absent from the old enumeration and present in
the new one, reported with path, line, column and class and no value. Proven
permanently by a specimen repository carrying a real `.gitignore`, an ignored
directory and a checksum-valid payload inside it, plus a companion proof that
git really does ignore the planted file - the previous control cited the ignore
scenario while planting a file that was not ignored, so the scenario it named
had never run.

The two tiers, and why the verdict is keyed on tracking state rather than path.
Tracked content that carries a checksum-valid tax identity fails the gate: it
ships, reaches every clone, and cannot be taken back out of history. Untracked
and ignored content is swept just as hard and reported in a separate
non-blocking operator tier, because a hit there is routinely the system working
rather than a leak - the Cl@ve Movil settings must carry the operator's own DNI
or NIE to authenticate against AEAT, and gitignoring that file is the correct
handling. Excluding the environment file by path was refused: it would restore
precisely the blindness the review found. Under the tier the ignored sweep keeps
its full value and gains its real one - enumerating ignored files is what proves
the operator's own identity has not also reached tracked content, and that
cross-check does not exist without it. A single test plants one value in a
tracked file and an ignored file in one specimen and requires the tracked copy
to red while the ignored copy only reports, so the tier cannot become a route by
which anything escapes the blocking set.

Measured after the change: 17,701 data files scanned, zero blocking findings in
tracked content, one occurrence in the operator tier - the ignored Cl@ve Movil
credential file. Classification over the real enumeration is 18,896 tracked, 12
ignored, 3 untracked.

Detection now decides four tax-identity classes through one authority. The
legal-entity and ES-prefixed classes were added, and the natural-person leader
class was widened to K, L and M alongside X, Y and Z. That widening was not in
the review's findings; it was taken on the executor's own initiative because the
checksum authority routes K/L/M-prefixed documents while the pattern could not
express them, which is the same blindness class as the two the review named, and
the plan lead ratified it. Every class is admitted by the project's existing
`validate_identity` and never by shape, and the shape knowledge was mirrored
rather than imported from the redaction funnel: that arm is private to another
package and is separator-tolerant for printed prose, which would swallow
neighbouring columns of a data row. The decision is not duplicated - one call
into one checksum authority serves every class. The locale exclusion's stated
reason, which names the NIF, NIE and CIF formats, is now true and is pinned by a
test that reads the suppressed population back and requires both classes to be
present.

Exclusions and their reasons. Blocking-scope exclusions, each still required to
suppress a live occurrence or fail: the test corpus, because the project uses
structurally valid synthetic identities in fixtures as undeclared established
practice; fixture payloads, synthetic by construction; the locale catalogues,
where a format illustration is the content; bundled BOE and AEAT corpus text,
the authority's own worked examples which must not be edited; recorded CLI
transcripts generated against the documentation demo profile; and, added by this
correction, the extracted text of the bundled AEAT Manual practico publications,
whose worked examples carry fictitious identities the project reproduces
verbatim and must not alter. That last entry was adjudicated rather than taken:
six findings surfaced there, all six one sentence of the Renta manual naming a
fictitious investment fund, and the fragment was scoped to the manual
publications rather than the whole extracted-corpus tree so no future
operator-derived material can hide behind it.

Separately, the ignored pass alone skips trees this repository does not author -
git's own store, compiled bytecode, installed Python and JavaScript packages,
documentation and package build output, tool caches by naming convention,
recorded harness state, generated search indexes, and transient scratch and
local runtime directories. Unfiltered, that pass opens roughly 265,000
machine-written files, the great majority transient scratch, and returns a
verdict that differs per machine and per hour. Each entry states what it is, a
test requires every one to do so, and a further test fails if the skip set ever
grows to cover every ignored file.

What the delivered gate still does NOT cover, stated because the first delivery
was faulted for claiming a capability it lacked. Source and prose remain
reported and ungated; that population is now 3,109 occurrences and it needs a
declared synthetic-identity convention before any gate can separate a deliberate
example from a real leak. Binary payloads are not scanned at all, since a
pattern means nothing before extraction. An identity dropped into a scratch or
local runtime directory is invisible, which is the price of a verdict that does
not vary per machine. The operator tier is reported and never enforced, so
nothing prevents an untracked identity file existing - only its promotion into
tracked content is gated. Of the checksum-verified classes the bank-account
shape is deliberately not gated; extending to it is an open item, now stated in
the constant rather than left to be inferred. Each of these narrows the standing
goal, which is that no real identity reaches this repository by any route.

The four smaller defects. The advisory tripwire subtracts this module's own path
before asserting, requires the remaining population to span more than one file,
and is protected by a companion test that fails if the subtraction ever becomes
a no-op. Unreadable files are named in their own tuple, excluded from the
scanned count and asserted empty by the gate, proven on the real race by
enumerating, deleting the file and scanning the stale list. The docstring states
the security fact without citing the record. The whole-tree sweep is computed
once per module through shared fixtures, and the report enumerates once and
feeds both sections.

Verification. The canary module is 24 tests green; the sanitiser residual gate
is 18 green, with its hardcoded blocking-tier pair replaced by a behavioural
proof that each class refuses a specimen of its own shape carrying a wrong
control character and that the two new classes actually fire. `ruff format`,
`ruff check` and `ty` are clean on all six files. The wider dev lane carries 23
failures at this commit, all in the CLI action census, error-code rehoming and
registry conformance modules of other campaigns; none is in this Step's surface.
