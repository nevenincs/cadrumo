---
name: aeat-swarm-audit-cadence
trigger: always_on
---

# AEAT swarm audit cadence

Run the multi-agent audit swarm on event triggers, not only when something feels
off. It is a standing gate, and it is the most reliable surface for catching
cross-domain drift, persistence-boundary gaps, type-erasure regressions, and
discriminator coverage holes that no single-agent pass notices.

## Triggers

Dispatch the swarm on any of three conditions: before a release cut that has
crossed a domain boundary or persisted a new record type; after a structural
refactor touching more than two domain subpackages; and every six to eight
commits on a long-running branch when no other trigger has fired.

## The eight axes

One agent per axis: calculation-engine grounding, persistence-boundary identity,
cross-domain handoffs, export/import fidelity, workflow and CLI surface,
selector and binding drift, semantic functionality-cluster overlap, and runtime
import-graph coupling. Give each a focused scope plus an explicit reference to
the established roundtrip-test pattern, so findings come back as actionable
structural deltas rather than open-ended commentary.

**Match the model to the axis.** Use the reasoning tier for the four axes
needing deeper structural analysis — calculation engine, cross-domain handoffs,
selector/binding drift, semantic overlap. Use the cheap tier for the four
breadth-oriented axes — persistence identity inventory, export/import fidelity,
workflow and CLI surface, runtime import-graph coupling.

**Axis seven — semantic functionality-cluster overlap** — runs as a parallel
multi-agent discovery pass. It discovers, by meaning rather than by symbol,
every site implementing a given functional concept; classifies the set as a true
duplication cluster or a constraint-shape-divergent set; and confirms consumers
import the canonical implementation rather than re-deriving it. Where no
canonical home exists but two or more substitutable sites do, it nominates one.
Pair every sweep with a targeted `rg` pass for known canonical symbols, so a
single-site authority is not misread as having no cluster. The substitutability
pre-filter below is mandatory for this axis.

**Axis eight — runtime import-graph coupling** — runs a grimp pass over the
executed import graph, not the import-time graph the layered-contract linter
audits. The runtime graph is materially denser, because the codebase defers many
function-local imports to break module-load cycles; a cycle "fixed" by deferring
an import is hidden from the static linter, not removed. Build the graph with
`grimp.build_graph("cadrumo", include_external_packages=False)` and diff its
cross-layer and cycle edges against the static picture. A cross-layer edge or
module cycle present in the grimp graph and absent from the import-linter graph
is a hidden coupling to report. **There is no sanctioned inventory of
function-local first-party edges to diff against**, so report a runtime-only
edge on the graph difference alone, and state that the finding is
**unclassified** rather than implying an allowlist cleared the rest.

## Discipline

**Apply the substitutability pre-filter before flagging any "X where Y exists"
violation.** Verify that Y's constraint shape is a superset of — more permissive
than — X's current constraint before classifying X as actionable. If Y carries
additional constraints (min_length, pattern, max_length, value-format
restrictions) that X does not, the site is NOT promotable: exclude it, or
document it as a constraint-shape mismatch. Without this filter the false
positive rate on such passes is overwhelming.

**Persist every finding in the vault.** Each agent writes one
`.vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md` following the vaultspec
template, with findings as third-level headings carrying a pathway label,
`file:line`, what is lost, and a concrete remediation. Reports must not modify
production code; they exist to drive subsequent action commits.

**Action every finding** as either a structural fix paired with a roundtrip
test, a vault audit note recording the wontfix rationale, or a follow-up task
linked back to the originating audit. Do not let findings rot unactioned.

**Treat swarm output as inventory, not gospel.** Sub-agents miss things and
occasionally hallucinate `file:line` coordinates. Verify every finding against
current code before action. The pattern is agent-as-discovery,
coordinator-as-confirmation, structural test as enforcement.
