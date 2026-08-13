---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:d96fda5fc04283638768b0728b6c17f5ca18c25a306e9e5120fb351ebc6d06b3'
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
