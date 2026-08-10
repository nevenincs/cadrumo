---
name: casilla-schema-buildout
trigger: always_on
---

# casilla-schema buildout discipline

*(Operator-directed campaign rule, 2026-08-10. This file exists to survive rate
limits, context rot and attention attenuation during the casilla-schema
buildout — the failure modes that broke step follow-through before. RETIRE this
file at campaign close, in the same action as the closing honesty review; it
does not outlive the campaign.)*

## One plan, entered through its next open step

The campaign is enumerated in `.vault/plan/2026-08-10-casilla-schema-plan.md`
(W01–W04), governed by the four `casilla-schema` ADRs and grounded in
`2026-08-10-casilla-schema-research`. Enter every session with
`vaultspec-core status casilla-schema` and read the NEXT OPEN STEP — never
re-derive the backlog from memory, chat history, or the artifact. Before
starting a step, `git log --grep` for it: a peer may have landed it.

## Ordering law: canonical answers before consumers

Shared answers land as importable, facade-exported code BEFORE their first
consumer. A consumer step whose canonical symbol does not exist yet is BLOCKED —
do the producing step first, never inline a private copy "for now". The
canonical homes this campaign establishes: the binding↔casilla joins
(`bound_casilla_binding_ids` and its reverse dual), the relation-consumption
index, the official-box classification, the `ModeloWorkReview` producer, and
the operator action spine with total, import-asserted projections.

## Follow-through protocol, per step

- One Step = one atomic commit; a canonical landing retargets or deletes its
  duplicates in the SAME commit. Clean `--collect-only` before committing.
- Close the step through the plan verbs, write its exec record, and run its
  named verification gate before claiming it. A step without a green gate or a
  recorded carry-forward stays open.
- The outliers are the acceptance test: M720, M200 2024, M100 2024/2025 and
  M349 must render truthfully before any casilla-surface step closes.

## Hard prohibitions for this campaign

- No new binding→casilla mapper, relation join, blocker vocabulary, or box
  classification outside the canonical homes above.
- No compatibility alias, bridge, re-export or read-tolerance for anything the
  dead-surface ADR deletes. Owner mandate (2026-08-10): missing semantics are
  re-homed case by case, and in every case no legacy surface is maintained and
  all superseded code is removed.
- Progress numbers: counts only against the NAMED manifest denominator;
  UNDEFINED (not zero) where no manifest exists; never a bare percentage; never
  ratio-token field names. (Owner ruling 2026-08-10 permits counts under
  exactly these guardrails.)
- Manifest authoring priority is owner-ruled: IRPF/retención/IVA revisions
  (including M145) first, informative annual rollups second, remainder last.
