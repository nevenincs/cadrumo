---
tags:
  - '#audit'
  - '#distribution-installation-readiness'
date: '2026-07-15'
modified: '2026-07-19'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
  - "[[2026-07-16-distribution-harness-identity-adr]]"
---

# `distribution-installation-readiness` audit: `Distribution close: harness identity and publish guardrail disposition`

## Scope

Close audit for the local-scope tail of the `distribution-installation-readiness`
campaign: the harness-identity verification (`W02.P06.S67`, `W02.P06.S68`), the
publish-workflow structural guardrail (`W04.P09.S44`), and the closeout gate and
index rows (`W05.P12.S57`, `W05.P12.S60`). It audits every in-scope deliverable
against the three acceptance dimensions the harness-identity decision adds to
delivery evidence: Cadrumo brand parity, canonical `cadrumo-` harness-prefix
coverage, and parity between the English and Spanish MCP product descriptions. Per
the accepted decision and the plan's own intent note, this audit does not authorize
a rename or translation; it records the disposition of each deliverable and leaves
every noncompliant artifact open.

The audit reads the honest output of the read-only distribution identity verifier
and the publish-workflow guardrail suite as its evidence. The verifier materialises
the real authored harness, the workspace/plugin/marketplace generators, and the live
MCP prompt/resource projections, and reports drift without mutating any byte.

## Findings

### harness-prefix-coverage | high | Authored and generated harness identifiers carry no `cadrumo-` prefix; verifier fails closed as designed

The distribution identity verifier exits `1` with `ok = false`. The authored
authority holds seven personas, 34 skills, and seven rules; none carries the required
`cadrumo-` prefix, and the generated Claude workspace, plugin, and marketplace trees
faithfully preserve those generic identifiers. The MCP prompt names and every
concrete and prompt-embedded harness-resource leaf are likewise unprefixed; only the
six MCP resource templates already carry the product prefix. Exact-set inventory
parity between every authored inventory and its workspace, plugin, marketplace,
prompt, and resource projection passes, so the failure is purely the missing product
prefix rather than any generation drift. This is the intended visible-noncompliance
result. Disposition: `W02.P06.S67` remains OPEN. Closing it requires the harness
identifiers to actually carry `cadrumo-`, which is a rename the accepted
harness-identity decision explicitly does not authorize.

### mcp-description-bilingual-parity | high | Client-facing MCP product descriptions are English-only; bilingual parity fails as designed

The verifier inventories five real client-display fields (the generated Claude plugin
description, the marketplace description, the marketplace-served plugin description,
and the MCPB `description` and `long_description`). Every field carries unlabelled
English copy with no explicitly labelled English section and no Spanish section, so no
field reaches English/Spanish claim parity across the six required claims (capability,
safety, privacy, on-host storage, human confirmation, never-files-live). The
approved-pair inventory is empty, so keyword similarity alone cannot pass a
description; a separately product-reviewed exact pair is required. The English-only
model-facing operational description contract is correctly preserved (its frozen
digest is compliant and carries no product-language labels). Disposition:
`W02.P06.S68` remains OPEN. Closing it requires operator-approved Spanish product copy
and an artifact migration the accepted decision explicitly does not authorize.

### brand-parity-mcp-tuple | low | Accepted Cadrumo MCP product tuple passes across every real projection

The independent MCP product-identity comparison passes. The human executable is
`aeat`, the MCP server and plugin identifier are `cadrumo`, the MCP executable is
`cadrumo-mcp`, the tool prefix is `cadrumo_`, and the resource scheme is `cadrumo://`,
consistent across canonical, project-script, runtime-server, generated plugin,
generated marketplace, MCPB, tool, and resource projections. The tool comparison
accepts only `cadrumo_` or the closed generic progressive-discovery set (`describe`,
`execute`, `search`, `toolsets`); every observed projection passes. Top-level Cadrumo
brand identity is therefore compliant; the noncompliance is confined to the harness
namespace and the bilingual descriptions above. No action.

### publish-guardrail | low | Publish workflow proven fail-closed; publication remains operator-held

The publish-workflow guardrail suite passes as real-behavior coverage against the
shipped `publish.yml` and `justfile`. The workflow accepts one run-bound
`packaging_run_id`, requires a successful `packaging-smoke.yml` authority run,
downloads only the named cohort and evidence artifacts, and pins checkout to that
run's source commit. It carries read-only permissions and no build, publish, OIDC
write, PyPI environment, or publish-token capability, so it cannot build, regenerate,
or accept unrelated artifacts. Disposition: `W04.P09.S44` CLOSED. The operator publish
hold is untouched and independent of this proof.

### closeout-gates | low | Path-scoped lint/format and feature-scoped tests green over touched surfaces

Path-scoped `ruff check` and `ruff format --check` are green across all 38 touched
Python surfaces, and the identity verifier suite (7 passed) and publish-workflow
guardrail suite (2 passed) are green. The only feature-scoped vault item was the
index staleness introduced by the closeout execution records, which the index rebuild
resolves. Disposition: `W05.P12.S57` CLOSED; `W05.P12.S60` CLOSED (feature index
rebuilt to include every evidenced execution record, with `S67`/`S68` left open).

## Recommendations

- Keep `W02.P06.S67` and `W02.P06.S68` OPEN. Their verification deliverables are
  complete and their execution records are committed; the rows stay open because the
  honest verification fails on the current, intentionally-unmigrated harness. Do not
  check them by editing artifacts under this campaign.
- Route the actual `cadrumo-` harness-namespace migration and the operator-reviewed
  bilingual MCP product copy through a separately-authorized implementation, as the
  accepted harness-identity decision requires. That work owns the skill/persona/rule
  renames, prompt and resource URI changes, plugin/marketplace/MCPB metadata, Spanish
  translations, tests, and real-client proof.
- Treat the read-only distribution identity verifier as the standing gate for both
  open rows: it already fails closed on the missing prefix and the English-only
  descriptions, so the migration is complete only when the verifier reports `ok`.
- Keep the publish workflow fail-closed; the guardrail suite reddens on any future
  reintroduction of a build, upload, OIDC-write, or unrelated-artifact path.
