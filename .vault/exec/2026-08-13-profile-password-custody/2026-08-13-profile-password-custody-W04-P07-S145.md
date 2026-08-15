---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:78c58a33f1cc1b0562e022b5873c5b2bcb20a60e4faede84397c5f2104be56b6'
step_id: 'S145'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh sever the dependency cycle between the core distribution and the extracted harness by moving the four harness-delivery surfaces into the harness package and dropping the core dependency, since the harness project file states that it consumes the core library and never the reverse while a repair added exactly that reverse edge, making the current shape a deliberate temporary the sever supersedes

## Scope

- `pyproject.toml and src/cadrumo/entrypoints/ and src/cadrumo-harness/`

## Description

- Identify the four harness-delivery surfaces the prior repair repointed, and
  confirm the direction the harness project file declares.
- Establish the edge's live state at both ends rather than from the row's
  description of it.
- Gate the direction so the next reverse edge cannot land silently, and prove
  the gate bites on the exact shape that already landed once.
- Verify both distributions build, resolve and expose their console scripts.

## Outcome

The four surfaces are named, and all four had already moved. They are the three
MCP entrypoint modules that read the operating layer - the harness tools, the
prompts and the resources projection - plus the CLI agent-workspace command.
The prior repair had repointed exactly those four at the extracted package,
which is the reverse edge the row exists to sever; a peer commit later moved
the whole MCP entrypoint tree into the harness package and folded the CLI
surface into the shared command-schema module, so the four surfaces now live on
the consumer side where the declared direction puts them.

**The edge is severed at both ends, and the built artefacts are the evidence,
not the source tree.** The core wheel's metadata resolves no harness
requirement in its base dependencies and in none of its seven extras; the
retired agent extra is gone and its absence is documented in place; the core
declares exactly one console script, `aeat`, and the wheel carries zero harness
members. The harness wheel declares the core as a version-bounded dependency
and carries the `cadrumo-mcp` script pointing at its own module. A fresh
virtualenv given only the harness wheel resolves the whole four-distribution
cohort, both scripts land on disk, the CLI reports its version, and both entry
points load their callables. Read back from the installed metadata: the core
requires nothing named harness, the harness requires the core.

**What did NOT need severing is named, because leaving it unexplained would
read as a miss.** The development dependency group still names the harness. That
is not the cycle: a PEP 735 group is never written into wheel or sdist metadata,
so it creates no edge between the two published distributions, and the
repository's own evaluation harness and packaging tooling genuinely import the
package and run its suite in that environment. Workspace membership is likewise
not a dependency - it exists so both lock together and the harness can be
exported independently for the bundle pins.

**The row's real remaining deliverable was making the direction enforceable,
because prose is what failed the first time.** The contract was stated correctly
in the harness project file, one section below build configuration that had been
opened twice for other reasons, and the repair still closed the cycle - nothing
in the tree could tell. A directional gate now lives in the harness package's
own test tree, gating both ends: no module in the core source tree may name the
harness in an import, in any of the three shapes an import takes, including the
dynamic module-string cycle-break an import-statement walk would not see; and
the core's published metadata may resolve the harness in neither its base
dependencies, nor any extra, nor a console-script target. Both are hard zero
with no allowlist. A fourth assertion holds the converse edge present, so a
future change that unrelates the two distributions cannot leave the gate passing
over nothing.

**The gate was proven to bite, from outside the repository.** A probe in scratch
space copied the real files out, reintroduced the historical defects into the
copies, and rebound the gate's locators at them for one call each: the verbatim
import line the repair added, a plain module import, the dynamic string form,
the deleted dependency line put back, an extra resolving the harness, the
console script re-registered on the core, and the harness dropping its core
dependency. All seven went red; the three unmodified baselines stayed green. The
false-positive direction was proven too - a core module carrying a harness
cross-reference in its docstring, which is a shape the tree really has in eight
places, stays green. No tracked file was mutated and the copies were deleted.

## Notes

**Two residues of the sever were fixed and one class was deliberately left,
because it needs a ruling this row does not carry.** The retired agent extra was
still named as an install route in the evaluation harness's refusal hint and in
the release documentation's executable-evidence step; both now name the harness
distribution, and both were one-line corrections with one correct answer.

The class left open is the published release cohort. Three lanes still install
the retired extra and then probe for the MCP launcher it no longer supplies -
the post-publication public reacquisition, the immutable cohort oracle emitter,
and the release-readiness bundle test. Those cannot be corrected by renaming,
because the cohort constant enumerates three wheels and the harness is not one
of them: fixing them means deciding whether the harness ships in the published
cohort at all, and if so at which version, since it is on its own `0.1.0` line
while the other three are version-locked together. That is a ruling, and
inventing one inside a sever row would be the quieter failure. It is reported
for its own row.

**The tree-wide collection state was measured twice and is clean**, exit zero
with no collection errors on both runs, against a warned baseline of seven to
twelve errors from a concurrent registry writer. The two runs disagreed on the
total by nine tests, which is that writer, not instability in the subject.

The harness MCP suite carries twenty-seven failures that are not this row's.
Every one is a registry validation refusal - missing export layouts, authority
grades claimed over blocked families, a layout-authority evidence tier over a
file with no annex - raised from modelo data an authority-grade sweep is
actively rewriting. The three structural gates this row touches and the harness
package-level suites run green in isolation, sixty-six passed.

**Every file this row changed was committed by a peer's broad sweep commits
before this record was written.** No git write command was issued here. The
content is intact on the branch; it simply landed inside two commits whose
subjects describe registry work, so the change is on the branch but not
attributable from its commit message.
