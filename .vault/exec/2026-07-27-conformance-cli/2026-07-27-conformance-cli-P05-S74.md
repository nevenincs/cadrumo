---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:08a5c935891204932480c61285290f76815598b2e8016f750f3d999533052c32'
step_id: 'S74'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# rule the capability-fact duplication between the conformance composer and the registry matrix CLI, which independently recompute the same predicates, applying the single-authority answer this campaign already chose for the boundary detector

## Scope

- `dev/registry/matrix/manager.py`

## Description

- Read both named modules in full and then swept the tree for every site
  computing the same predicates, rather than ruling on the two the row names.
- Established what each site is keyed on and what question it answers, so
  substitutability was judged on constraint shape rather than on field-name
  overlap.
- Confirmed the candidate delegation targets are reachable through public
  facades.
- Ruled on the measured evidence and recorded the ruling as an in-place
  amendment to the accepted campaign ADR, leaving its status untouched.
- Opened the two Steps the ruling implies, in the phases matching the surfaces
  they touch.

## Outcome

The duplication is wider than the row states, and that changes the answer. There
are three sites, not two. The shipped domain support matrix builds a per-modelo
row keyed on the latest revision; the shipped conformance composer builds a
per-revision fact set; the dev matrix manager builds a per-modelo row keyed on
the latest revision. The row named the second and third and missed the first,
which is the one that owns the question.

The dev manager is a pure duplicate of a shipped public authority. Every one of
its ten fields is already returned by `build_support_matrix` on `ModeloEntry`,
from the same primitives and by the same expressions, including the
latest-revision selection helper and the two export-format membership tests. The
dev module's own See Also block names that builder and names the operator facade
over it, so the module documents the authority it forked. Its tests carry the
same relationship in the other direction: the shipped support-matrix test
declares itself as mirroring the dev manager test.

The conformance composer is not a duplicate of the same question and is not the
consolidation target. It is per-revision where the other two are per-modelo
latest, it carries eight further counts the others do not, and it already
delegates its own latest-revision probe to the shipped support matrix. Its
overlap with the domain builder is four predicate expressions on two different
questions, which the substitutability filter excludes: neither site is promotable
into the other.

The ruling is to RETIRE the dev matrix package, delegating nothing. Its single
report verb renders a table the operator support-matrix verb already renders from
the shipped authority, and the dev conformance report verb already carries the
same probe for every revision as a strict superset, with a registry-root flag and
row-level degraded-mode labelling the matrix has neither of. There is no question
the retired module answers that a surviving surface does not.

Both offered alternatives were rejected on evidence. Delegating the dev manager
to the per-revision conformance fact builder closes four of the ten fields and
leaves the latest-revision selection, the axis the whole matrix is keyed on,
still forked dev-side; that fold also carries no extractor boolean, only a count,
so two of the ten fields could not be sourced from it at all. Declaring the
duplication deliberate behind a divergence gate fails on the same ground the
campaign rejected two boundary detectors: these copies have already diverged, the
dev row lacking title, calculation class, supported revisions, renames,
deprecations and portal cross-references, and the conformance fold having dropped
the extractor boolean. A gate would pin a fork in place rather than delete it.

The residue is a type gap and is tracked separately. After the retirement two
sites still spell the export-format tokens as bare strings, and they are the two
legitimate non-substitutable questions. What forces the re-spelling is that the
export-format closed set is a bare Literal on the export-layout schema rather
than a core StrEnum, contrary to the closed-value-set rule. That is the durable
fix for the literal-level fork and is a different change from the retirement.

The retirement also has to correct two prose references pointing the wrong way
across the boundary this campaign hardened. The shipped support-matrix module
docstring and the shipped support-matrix test docstring both declare themselves
as mirroring the dev matrix. Neither is an import nor a runtime path read, so the
boundary gate does not fire on either, but a shipped module naming dev
scaffolding as its origin of truth is the campaign's own arrow reversed. The
synthetic planted-import fixtures in the boundary tests also name the retiring
module as a string; they are fixture content rather than imports, so they keep
working, but they would name a module that no longer exists.

Recorded as an amendment, not a new record. This is concretization of an already
accepted decision, the single-authority rule the campaign chose for the boundary
detector, applied to the second instance of the same shape. The campaign ADR
status stays accepted and its body gained the ruling next to the boundary-detector
paragraph it extends, plus two honest consequence bullets. The write went through
the owning body verb, which preserved the frontmatter byte-for-byte and refreshed
the modified stamp.

Two Steps were opened for the code work, which this Step deliberately did not do.
The retirement is a dev CLI surface change and sits in the dev CLI phase; the
export-format enum lift is a shipped closed-value-set change and sits in the fact
phase.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
semantic index is broken and the service is stopped, so it was neither started,
restarted, reindexed nor probed. Grounding was whole-file reads of the three
capability sites and the two CLI shells, plus ripgrep sweeps for the export-format
literals and for the predicate field names across both trees, which is how the
third site was found.

No source file was edited and none was intended to be. The deliverable is the
ruling and the Steps it implies; the consolidation is code work for the Steps
opened here.

The plan carried uncommitted peer changes throughout. Every plan mutation went
through the owning Step verb, each reporting its preserved prose blocks, and the
frontmatter edge was added through the link verb and diffed against a copy taken
immediately before the write to confirm the body was untouched.
