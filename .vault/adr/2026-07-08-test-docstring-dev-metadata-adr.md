---
tags:
  - '#adr'
  - '#test-docstring-dev-metadata'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:a6866ae8e86fba9b56372bee363a6ed66f3ae9403ecfdb1c3908bfe9cc41522b'
related:
  - '[[2026-07-10-test-docstring-dev-metadata-research]]'
---

# `test-docstring-dev-metadata` adr: `test docstrings and comments must not carry dev/campaign metadata` | (**status:** `accepted`)

## Problem Statement

Test docstrings and comments across the tree had accumulated development
process metadata: dated ADR/audit/plan document stems (the
`2026-..-...-adr` filename pattern), `.vault/` document paths, bare "ADR" /
"wave" / "phase" / "plan Step" vocabulary, and canonical plan-step notation
(`W##.P##.S##` and its partial forms). This is campaign provenance, not
test documentation: it describes the process moment a test was authored in,
not what the test verifies. Under `aeat-source-hygiene` (source code stays
free of project-management metadata — waves, phases, issue workflow,
process history), these citations are drift the moment the referenced
campaign closes, and they train readers to look up a vault document instead
of reading the test's own contract. During the perf-and-test-hardening
campaign the enforcing gate —
`test_source_test_comments_and_docstrings_do_not_reference_campaign_metadata`
in `src/cadrumo/tests/test_marker_integrity.py`, driven by the
`_CAMPAIGN_METADATA_PATTERNS` tuple (~lines 67-85) — surfaced these
citations at scale, and the question was ruled on by the operator: is the
gate over-strict, or is the metadata genuinely forbidden?

## Considerations

- The operator ruling during the campaign is the deciding input: dated
  ADR/audit/plan stems, `.vault/*` paths, bare "ADR"/"wave"/"phase"/"plan
  Step" vocabulary, and `W##.P##.S##` notation in test docstrings and
  comments are forbidden dev/campaign metadata, and the gate is CORRECT to
  enforce this strictly. No gate-narrowing.
- A test docstring's job is to describe what the test verifies in stable
  domain terms — terms that remain true after the current project plan
  changes (the same standard `aeat-source-hygiene` already applies to
  production identifiers). A docstring stating which casilla aggregation a
  test proves outlives every campaign; one citing the plan step it was
  authored under is stale process history the day the plan closes.
- Not every structured citation is dev-metadata. Legitimate `:class:` /
  `:mod:` / `:func:` code cross-references (the `core-struct-docstring-links`
  discipline), registry-identifier citations, and registry TOML-path
  citations name stable code and data surfaces, not process artefacts; they
  are KEPT, and the gate's pattern set is shaped to leave them alone.
- The distinction that separates the two classes: a code/registry citation
  points at something the test exercises and that exists at HEAD; a
  dated document stem or step identifier points at a process artefact whose
  meaning requires vault archaeology and whose relevance decays with the
  campaign. Provenance belongs in the vault (exec records, ADRs, audits)
  and in commit messages — both of which already carry it — never in the
  durable test source.
- The tree-wide state at ruling time: a ~96-file sweep (commits
  `a527048116` and `3a824a916c`) stripped the forbidden metadata across
  core, domain, and application test docstrings per this ruling. The
  residual violations are all owned by the actively-landing `iva-prorrata`
  peer campaign — a moving target whose files this campaign deliberately
  did not touch (shared-worktree discipline: peer WIP is not swept).

## Considered options

- **Enforce the gate strictly; sweep the tree; keep code/registry
  citations (chosen).** The gate's patterns stay as-is, the forbidden
  metadata classes are removed from test docstrings and comments
  tree-wide, and the stable citation forms (`:class:`/`:mod:`/`:func:`
  roles, registry identifiers, TOML paths) remain first-class.
- **Narrow the gate to bless dated ADR citations as "grounding".**
  Rejected: an ADR stem is a dated process artefact, not a stable domain
  name. Blessing it would formalize exactly the drift the gate exists to
  catch — tests annotated with document references that rot as campaigns
  close and vault documents are archived, while the docstring's actual job
  (state the verified contract) goes undone. Grounding lives in the test's
  assertions and its domain-term docstring; provenance lives in the vault
  and the commit history.
- **Delete the gate and rely on review discipline.** Rejected implicitly
  by the scale of the finding: the metadata accumulated to ~96 files'
  worth under review discipline alone. A structural gate is the only
  mechanism that holds across many concurrent campaign agents.

## Constraints

- The gate must keep distinguishing forbidden process metadata from kept
  citation forms. `_CAMPAIGN_METADATA_PATTERNS` matches the step-notation
  grammar, dated `-adr` stems, `.vault/adr` paths, and the bare process
  vocabulary; it does not match Sphinx cross-reference roles, registry
  casilla/modelo identifiers, or registry TOML paths. Any future pattern
  addition must preserve that boundary.
- The `iva-prorrata` residual is a peer-ownership constraint, not an
  exemption: those files belong to an actively-landing campaign and are
  not swept from under it (`uncommitted-wip-is-not-orphaned`,
  `full-tree-gate-must-distinguish-owner`). The prohibition binds them the
  same as everyone else; the sweep timing is theirs.
- This ADR changes no code and no gate patterns; it records the ruling the
  sweep already executed against.

## Implementation

The enforcement already ships: the gate in
`src/cadrumo/tests/test_marker_integrity.py` scans test docstrings and
comments against `_CAMPAIGN_METADATA_PATTERNS` and fails with
file-and-line violations. The tree was brought to conformance by the
~96-file sweep in commits `a527048116` (core/domain/application docstring
slice) and `3a824a916c` (test-docstring slice). What remains is the
documentation layer this ADR grounds: a follow-on sharpening of the
`aeat-source-hygiene` rule to name these citation forms explicitly — dated
document stems, `.vault/*` paths, bare process vocabulary, step notation —
as forbidden in test docstrings and comments, and to name the kept forms
(`:class:`/`:mod:`/`:func:` roles, registry identifiers, TOML paths) as
explicitly legitimate, so peer campaigns stop re-introducing the forbidden
class in good faith. The companion gate (`test_marker_integrity`) is cited
from the rule as its enforcement surface.

## Rationale

The ruling resolves a genuine tension the campaign surfaced: agents cite
ADRs in docstrings with good intent (traceability), and a gate that
rejects those citations can look over-strict. The operator's ruling lands
on the side `aeat-source-hygiene` was always pointing at — source code
uses domain names that remain true after the current project plan changes,
and a dated document stem is by construction a name that does not. The
vault already provides the traceability the citations were reaching for
(exec records map steps to commits; `git log --grep` recovers campaign
provenance), so the docstring citation is redundant where it is accurate
and misleading where it is stale. Keeping the gate strict, rather than
carving out "grounding" citations, keeps the boundary mechanical: a
reviewer never has to adjudicate whether a given ADR reference is still
live. The kept citation forms are the mirror-image proof that the gate is
not anti-documentation: everything that names a stable code or regulatory
surface stays.

## Consequences

- Test docstrings converge on stating the verified contract in stable
  domain terms, which is the only description that stays true across
  campaigns; process provenance is read from the vault and commit history,
  where it is maintained.
- The gate stays strict, so the ~96-file cleanup cannot silently regress:
  a new docstring carrying a dated stem or step notation fails CI with a
  file-and-line message.
- The honest cost: agents lose an in-source shortcut they demonstrably
  reach for. Until the follow-on `aeat-source-hygiene` sharpening lands
  (naming the forbidden and kept citation forms explicitly), peer
  campaigns may keep re-introducing violations in good faith and paying a
  gate failure to learn the rule — the `iva-prorrata` residual is the live
  example. The rule sharpening this ADR grounds is what converts that
  from a recurring gate-failure lesson into loaded-at-session-start
  context.
- The `iva-prorrata` residual remains visibly red on the gate until that
  campaign sweeps its own files — the intended, honest state under
  shared-worktree ownership discipline, not a defect of this decision.
