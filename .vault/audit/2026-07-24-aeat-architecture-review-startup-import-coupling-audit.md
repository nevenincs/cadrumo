---
tags:
  - '#audit'
  - '#aeat-architecture-review'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:1407e65ac228c13cd0a20ca9fdc5b71aa78ce32fd1402dfc2e3db70d64308f82'
related: []
---

# `aeat-architecture-review` audit: `startup import coupling`

## Scope

The quarterly architecture pass raised a medium finding: resolving the `config` CLI
command group eagerly imports 1675 modules, 804 of them first-party and 265 of those
in the domain layer, taking roughly 7 seconds before the lightest auth command parses
its own arguments. Importing the CLI root pulls none of them, so deferral already
works at the root; the cost lands per GROUP, not per leaf.

The finding named the profile-setup wizard as the coupling and proposed deferring the
construction of its two verbs. This audit records what measuring that proposal showed:
the wizard was a symptom, the named remedy moves 3 percent of the cost, and the actual
coupling is one edge in the application layer that three other paths hold open
independently. Measurements were taken in fresh interpreters against a working tree at
commit `736a179158`, counting `sys.modules` after resolving the group rather than after
importing the package, because the root import was always clean and an import-time
assertion passes vacuously.

A note on this document's own provenance, since the git history is misleading. It landed
as commit `be23fbfdd3`, whose subject reads `docs(quickstart): execute the filed-marker
sequence and record the walkthrough`. That subject belongs to unrelated work. Two agents
were writing commit messages to the same conventionally-named file in a scratchpad
believed to be per-session but in fact shared across the team, and the peer's text
overwrote this document's during the interval a stale index lock held the commit. The
file set in `be23fbfdd3` is correct and was verified; only the message is wrong. The real
quickstart work is commit `3101115bc2`. The commit was left unamended deliberately: it
sat two commits deep with peer work built on top, and rewriting shared history to correct
a subject line is a worse trade than an inaccurate label.

## Findings

### four-tail-pullers-one-edge | high | Four independent paths hold the same import edge open, so cutting the named one moves 3 percent

The wizard was not the coupling; it was winning the import race. Cutting it moved the
group from 1675 modules to 1632. Four packages each pull the same tail on their own,
measured one at a time in fresh interpreters by first-party module count: the wizard at
575, `application.workflow` at 514, `application.modelo` at 806, and
`application.bucket_maintenance` at 557. The wizard and workflow edges are now cut. The
modelo edge survives through the collaboration command module, and the
bucket-maintenance edge survives independently.

All four converge on one line: the workflow adapters module imports three symbols from
the filing package facade, and that facade eagerly materialises its whole surface,
including the import module that pulls the justificante PDF adapter, plus the review and
complementaria modules. That package alone costs 4.1 seconds cumulative under import
timing. The CLI is therefore not coupled to the wizard at all. It is coupled to the
filing facade, and any command surface that legitimately needs workflow or modelo
inherits a PDF parser as a consequence.

The practical consequence for anyone reading the original finding: cutting CLI-side
edges does not converge. Two were cut and two more stood behind them, and each new
consumer of workflow or modelo reopens the same edge. An audit trail recording only
"the wizard was deferred" would leave the next reader believing the coupling was
resolved.

### barred-repairs-need-an-adr | high | Both obvious repairs at the chokepoint are forbidden by an existing rule

Narrowing the workflow adapters import to reach past the filing facade violates the
import-ownership rule, which requires a cross-package import to resolve to the owning
package's public facade. Making the filing facade lazy is forbidden by the same rule,
which permits a lazy package facade only where the pattern already exists and states
that an eager facade is never retrofitted to lazy.

The remaining route is to split the light draft and schema surface into its own
sub-package that filing re-exports, leaving the heavy import, review and complementaria
modules behind the facade. That is an application-layer restructure with consequences
for every consumer of those symbols, so it is an ADR decision rather than an
implementation choice. It is named here so the next agent does not re-derive the same
dead end.

### blast-radius-narrowing-observed | medium | A peer's accidental module-level error demonstrated the narrowing that was only hypothesised

The original finding argued that a module-level exception anywhere across the four
coupled subpackages surfaces as a crash on `config login`, with nothing in the traceback
connecting to what the operator typed, and cited an occurrence during an operator
walkthrough.

That was reproduced accidentally and under observation. Mid-measurement, a concurrent
agent landed a module-level `NameError` in the storage namespace registry, using a
filename constant it had not imported. Before the wizard deferral this reaches the
config group through the filing facade and takes down `config --help` entirely. After
it, `config --help` and `config login --help` both stayed green, and only the wizard
verb broke, which is correct because that verb genuinely needs the tail.

This is recorded as a measurement rather than a prediction, and the distinction matters:
an audit bullet asserting that blast radius will narrow is a hypothesis, whereas a peer
breaking an unrelated module by accident and the blast radius being observably smaller
is evidence. It was luck, not design, and it cannot be commissioned. It also carries the
caution that the narrowing is partial: the same class of error inside modelo or
bucket-maintenance still reaches the config group, because those two edges remain.

## Recommendations

Raise an ADR for the filing facade split, tied to the barred-repairs finding. The
decision it must make is whether the draft and schema symbols the workflow adapters
consume move into their own sub-package behind their own facade, leaving the import,
review and complementaria modules reachable only through the full filing facade; and if
so, which consumers move with them. The two alternatives are already eliminated by the
import-ownership rule, so the ADR's work is the split boundary, not the choice of
approach.

Land the justificante gate with that ADR's implementation, not before, tied to the
four-tail-pullers finding. The assertion is that the PDF adapter is absent from
`sys.modules` after resolving the config group, and it must assert after RESOLUTION
rather than after import, since the root import has always been clean. It is red today
and was deliberately not committed; a guard that cannot pass is not a guard. The narrower
boundary that does hold is already in place: resolving the config group must not import
the wizard, paired with a counterpart proving the verb still builds on demand, so the
absence assertion cannot be satisfied by a command that silently became unreachable.

Treat the surviving modelo and bucket-maintenance edges as in scope for that same ADR,
tied to the blast-radius finding. Closing only one of them repeats the pattern this audit
documents, where a partial cut reads as a resolved coupling.

Do not pursue further CLI-side edge cutting as an independent workstream. The measured
return was 43 modules of 1675, and the remaining edges are legitimate application-layer
dependencies rather than accidents of CLI wiring.
