---
name: aeat-swarm-audit-cadence
trigger: always_on
---

# AEAT swarm audit cadence

Run the multi-agent audit swarm on event triggers, not only when something feels
off. It catches cross-domain drift, persistence-boundary gaps, type-erasure
regressions and discriminator coverage holes that no single-agent pass notices.

**Triggers:** before a release cut that has crossed a domain boundary or
persisted a new record type; after a structural refactor touching more than two
domain subpackages; and every six to eight commits on a long-running branch when
no other trigger has fired.

**The eight axes**, one agent each: calculation-engine grounding,
persistence-boundary identity, cross-domain handoffs, export/import fidelity,
workflow and CLI surface, selector and binding drift, semantic
functionality-cluster overlap, and runtime import-graph coupling. Give each a
focused scope plus an explicit reference to the roundtrip-test pattern, so
findings return as actionable structural deltas rather than open commentary.

**Match the model to the axis.** The reasoning tier for the four needing deeper
structural analysis (calculation engine, cross-domain handoffs, selector/binding
drift, semantic overlap); the cheap tier for the four breadth-oriented ones
(persistence identity, export/import fidelity, CLI surface, import-graph
coupling).

**Axis seven, semantic overlap**, runs as a parallel discovery pass: it finds by
MEANING every site implementing a functional concept, classifies the set as a
true duplication cluster or a constraint-shape-divergent one, confirms consumers
import the canonical implementation, and nominates a canonical home where none
exists but two or more substitutable sites do. Pair every sweep with a targeted
`rg` for known canonical symbols, so a single-site authority is not misread as
having no cluster.

**Axis eight, runtime coupling**, runs a grimp pass over the *executed* import
graph, not the import-time graph the layered linter audits. The runtime graph is
materially denser because many function-local imports are deferred to break
cycles, and a cycle "fixed" by deferring an import is hidden from the static
linter rather than removed. Diff grimp's cross-layer and cycle edges against the
static picture; an edge present in one and absent from the other is a hidden
coupling. **There is no sanctioned inventory of function-local first-party edges
to diff against**, so report such an edge on the graph difference alone and state
that the finding is **unclassified** — never imply an allowlist cleared the rest.

## Discipline

**Apply the substitutability pre-filter before flagging any "X where Y exists"
violation.** Verify Y's constraint shape is a superset of — more permissive than
— X's current constraint before calling X actionable. If Y carries additional
constraints (min_length, pattern, max_length, value-format) that X does not, the
site is NOT promotable: exclude it, or document the mismatch. Without this filter
the false-positive rate is overwhelming.

**Persist every finding** as one `.vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md`
following the template, findings as third-level headings with a pathway label,
`file:line`, what is lost, and a concrete remediation. Reports must not modify
production code.

**Action every finding** as a structural fix paired with a roundtrip test, a
vault note recording the wontfix rationale, or a follow-up task linked back to
the audit. Do not let findings rot.

**Treat swarm output as inventory, not gospel.** Sub-agents miss things and
occasionally hallucinate `file:line` coordinates. Verify every finding against
current code before action: agent-as-discovery, coordinator-as-confirmation,
structural test as enforcement.
