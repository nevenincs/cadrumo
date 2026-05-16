---
name: aeat-swarm-audit-cadence
---

# AEAT swarm audit cadence

Run the multi-agent audit swarm on a recurring schedule, not only when something feels off. The swarm is the most reliable surface for catching cross-domain drift, persistence-boundary gaps, type-erasure regressions, and discriminator coverage holes — drift that no single-agent pass would notice. Treat it as a periodic gate, not an ad-hoc rescue tool.

Trigger the swarm under three conditions. First, before any release cut that has crossed a domain boundary or persisted a new record type. Second, after any major structural refactor that touches more than two domain subpackages. Third, on a calendar cadence (suggest monthly while the codebase is in flux; quarterly once the structural baseline is steady).

Cover the six standard axes. Dispatch one agent per axis: calculation-engine grounding, persistence-boundary identity, cross-domain handoffs, export/import fidelity, workflow + CLI surface, selector + binding drift. Each agent gets a focused scope plus an explicit reference to the established roundtrip-test pattern so findings come back as actionable structural deltas rather than open-ended commentary.

Mix the models. Use sonnet for the three axes that need deeper structural analysis (calculation engine, cross-domain handoffs, selector / binding drift). Use haiku for the three breadth-oriented axes (persistence identity inventory, export/import fidelity, workflow + CLI surface). The cost / latency profile rewards model selection that matches the cognitive shape of each axis.

Persist every finding in the vault. Each agent writes a single .vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md document with frontmatter following the vaultspec template. Findings are third-level headings with pathway label, file:line, data lost, and a concrete remediation. Reports must not modify production code; they exist to drive subsequent action commits.

Action findings in the same incremental pattern this campaign established. Every finding becomes either a structural fix paired with a roundtrip test, a vault audit note explaining the wontfix rationale, or a follow-up task linked back to the originating audit document. Do not let findings rot in the vault unactioned — process them on the same cadence as their landing.

Treat the swarm output as inventory, not gospel. Sub-agents miss things and occasionally hallucinate file:line coordinates. Every finding gets verified against the current code before action. The pattern is agent-as-discovery, human / coordinator-as-confirmation, structural test as enforcement.