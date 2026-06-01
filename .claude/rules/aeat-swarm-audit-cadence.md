---
name: aeat-swarm-audit-cadence
trigger: always_on
---

# AEAT swarm audit cadence

Run the multi-agent audit swarm on the event triggers below, not only when something feels off. Treat it as a standing gate, not an ad-hoc rescue tool. The swarm is the most reliable surface for catching cross-domain drift, persistence-boundary gaps, type-erasure regressions, and discriminator coverage holes — drift that no single-agent pass would notice.

Trigger the swarm under three conditions. First, before any release cut that has crossed a domain boundary or persisted a new record type. Second, after any major structural refactor that touches more than two domain subpackages. Third, every 6–8 commits on a long-running branch when no other trigger has fired in the interim, to surface drift before it accumulates.

Cover the seven standard axes. Dispatch one agent per axis: calculation-engine grounding, persistence-boundary identity, cross-domain handoffs, export/import fidelity, workflow + CLI surface, selector + binding drift, and semantic functionality-cluster overlap. Give each agent a focused scope plus an explicit reference to the established roundtrip-test pattern so findings come back as actionable structural deltas rather than open-ended commentary.

Run the seventh axis — semantic functionality-cluster overlap and canonical-definition enrollment — through the resident vaultspec-rag service. This axis discovers, by meaning rather than by symbol, every site that implements a given functional concept; classifies the set as a true duplication cluster or a constraint-shape-divergent set; and confirms that consumers import the canonical implementation rather than re-deriving it. Where no canonical home exists but two or more substitutable sites do, it nominates one. It exists because text search cannot cluster lexically different but semantically identical code: two modules that both round a Decimal to cents never co-occur in a grep result.

Query the service by functional concept, never by domain jargon. Always pass `--port 8766` and `--max-results 20`. Treat a score floor around 0.50 as the signal threshold. Use RAG for discovery, then `rg` to verify the exact sites. Filter locale and test-docstring rows and treat the same string across four locales as one signal. RAG is a clustering instrument, not a symbol locator: pair every sweep with a targeted `rg` pass for known canonical symbols so a single-site authority is not misread as having no cluster. Apply the substitutability pre-filter below — it is mandatory for this axis. RAG goes stale during active remediation; run an incremental `index --type all --port 8766` after major commits and before each sweep rather than relying on the filesystem watcher alone.

Match the model to the axis. Use sonnet for the four axes that need deeper structural analysis: calculation engine, cross-domain handoffs, selector / binding drift, semantic functionality-cluster overlap. Use haiku for the three breadth-oriented axes: persistence identity inventory, export/import fidelity, workflow + CLI surface. The cost / latency profile rewards model selection that matches the cognitive shape of each axis.

Persist every finding in the vault. Each agent writes a single .vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md document with frontmatter following the vaultspec template. Write findings as third-level headings with pathway label, file:line, data lost, and a concrete remediation. Reports must not modify production code; they exist to drive subsequent action commits.

Action findings in the same incremental pattern this campaign established. Turn every finding into either a structural fix paired with a roundtrip test, a vault audit note explaining the wontfix rationale, or a follow-up task linked back to the originating audit document. Do not let findings rot in the vault unactioned — process them on the same cadence as their landing.

Treat the swarm output as inventory, not gospel. Sub-agents miss things and occasionally hallucinate file:line coordinates. Verify every finding against the current code before action. The pattern is agent-as-discovery, coordinator-as-confirmation, structural test as enforcement.

Apply the substitutability pre-filter before flagging any "X where Y exists" violation. Any audit brief that identifies a site X where a canonical alternative Y exists MUST require the auditor to verify that Y's constraint shape is a superset of (more permissive than) X's current constraint before classifying X as actionable. If Y carries additional constraints (min_length, pattern, max_length, or value-format restrictions) that X does not, the site is NOT promotable: exclude it from the findings or document it as a constraint-shape mismatch. This pre-filter eliminates the 96% false-positive rate observed in the PROMOTE-001 pass (52 of 54 sites were blocked by constraint-shape incompatibility).