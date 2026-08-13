---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:297e74e26d572431173550b93405afddb761665b320c0ee282be1ffa2fa0c3c5'
step_id: 'S68'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Retype M303ProductSoftwareEvidence.digest onto the canonical ContentDigest alias, closing the SEVENTH hex-64 redeclaration site. This site existed in NO row of this plan, including S66's widened count. The Wave was planned against two duplicates, S66 re-measured six, and the true figure at HEAD is seven. A peer campaign landed this inline pattern at 2026-08-12 11:11, AFTER this campaign's own redeclaration gate landed at 2026-08-10 16:35, so the gate was green and is now red on a site no row names. Rowed rather than folded silently into S04 because S04 is a verification row and a fix carried inside a verification row is invisible to review. The remedy is the one this Wave proved five times over and the primitive's own docstring prescribes. The value is a payload digest, so it takes ContentDigest rather than a bare Hex64Str or a newly minted per-concept alias, and the module already imports from core.identity so no new import path is created. NOTE that the gate deliberately scans at HEAD rather than the working tree, so this row cannot be verified green until its commit lands. The working-tree proof is a census_sources run over the edited source

## Scope

- `src/cadrumo/core/product_identity.py`

## Description

- Re-measure the hex-64 redeclaration census at HEAD rather than trusting the sibling
  record's closing claim that zero redeclarations survive.
- Retype `M303ProductSoftwareEvidence.digest` from a bare `str` carrying an inline
  `^[0-9a-f]{64}$` onto the canonical `ContentDigest` alias.
- Widen the existing `core.identity` import to carry `ContentDigest` beside
  `SubjectTaxId`, adding no new import path.
- Prove the edited source is clean by feeding the working-tree bytes to the census
  scanner directly, because the gate itself reads HEAD and cannot see an uncommitted fix.

## Outcome

**A seventh site, found by disbelieving a closed row.** The sibling record for `S66` closes
with the measured claim that zero re-declarations of the hex-64 shape survive in production
code. That was true when written on 2026-08-11. It is false at HEAD: the census run for this
Step returned exactly one open `redeclared_pattern` site, `M303ProductSoftwareEvidence.digest`
at line 76 of the product-identity module.

**The regression is dated and attributable, and the direction matters.** This campaign landed
the redeclaration gate at 2026-08-10 16:35. A peer campaign's M303 variable-envelope commit
landed the inline pattern at 2026-08-12 11:11, roughly forty-two hours later. So the gate did
not fail to catch an old site - it was green, and a new site was added past it. That is the
decay mode the gate exists to catch, caught on its first occurrence.

**The remedy is prescribed, not chosen.** The canonical primitive's own docstring rules the
disposition explicitly: a field whose concept already has a semantic alias uses it, a field
whose concept has none takes the primitive directly, "or `ContentDigest` where the value is a
payload digest". This value is the digest of an evidence artefact authorising a software
identity, so `ContentDigest` is the named case rather than a judgement call. The docstring
also forbids the alternative a reader might reach for first - minting a per-concept alias -
on the recorded grounds that a plain annotated alias carries no nominal distinction and so
buys naming convention at the price of another parallel spelling.

**Substitutability was checked before promoting, not assumed.** `ContentDigest` resolves to
`Hex64Str`, which carries `strip_whitespace=True`, `min_length=64`, `max_length=64` and the
identical `^[0-9a-f]{64}$` pattern. The replaced declaration carried the pattern alone. The
pattern already pins the length at exactly 64, so the length bounds are redundant rather than
narrowing, and no value accepted before is refused now. The one behavioural delta is
`strip_whitespace`, which is a widening at the input boundary and produces a byte-identical
stored value. The peer's own test constructs this model with a 64-character digest and passes
unchanged.

**Evidence.** The census fed the working-tree bytes returns an empty declaration tuple for the
edited module, while the same census at HEAD still reports the single open site - the pair
together prove the fix is real and that the gate will flip when the commit lands, rather than
that the scanner simply stopped looking. The product-identity and hex-64 identity suites pass,
67 tests. Lint and format are clean on the edited file. The tree-wide type check reports 47
diagnostics, none of them in this module.

## Notes

**THIS ROW IS NOT CLOSED AND MUST NOT BE CHECKED YET.** Its named gate scans at HEAD by
deliberate design, recorded in the gate's own comment: the repository is written to by many
agents at once, and a gate whose subject moves between collection and assertion reports a tree
nobody can reproduce. The consequence is that an uncommitted fix cannot turn the gate green,
so the gate stays red until this Step's commit lands. The working-tree census run above is the
strongest available proof short of that commit, and it is deliberately recorded as a proxy
rather than presented as the gate passing.

**The commit is queued, not skipped.** The repository index lock has been held by a dead writer
since 19:31 and no commit has landed in this worktree for several hours. The lock was diagnosed
by its modification time and left untouched. Every change for this Step is on disk and complete.

**A peer-owned surface was edited, and the justification is narrow.** The product-identity
module belongs to an active peer campaign that touched it hours before this edit. The edit was
taken anyway because the violated gate belongs to THIS campaign, the file carried no
uncommitted peer work at edit time, and the change is the canonical one-line remedy rather than
a workaround to make a closeout pass. Had the fix required reshaping the peer's model or
weakening the gate's matcher, the correct action would have been to report it instead.

**A standing correction for whoever closes this Wave.** The Wave's count has now moved three
times - two at planning, six at the `S66` re-measure, seven here. The lesson is not that the
count is wrong again but that a hex-64 count is a moving target while other campaigns are
live, so the Wave should close against a green gate at HEAD rather than against any recorded
number.
