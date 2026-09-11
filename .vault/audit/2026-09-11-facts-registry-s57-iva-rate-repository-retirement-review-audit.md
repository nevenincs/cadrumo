---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8a6ed8681e2b681cb5876b0e80c04bfc36e4af032f9cb8f3fadff1dd2e5b389f'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S57 IVA rate repository retirement review`

## Scope

Read-only review of the revised W04.P17.S57 safe portion against the accepted facts-registry ADR, its authority-plumbing research, the adapted-family reference, the revised S57/S85 plan split, the IVA rate projection, the removed resource repository, the resource registry, and focused retirement checks.

## Findings

### resource-test-baseline | low | Pre-existing unrelated topic-repository test defects prevent the whole resource test files from being green

The S57 removal itself is covered by the exact `ResourceRegistry` field census and the canonical IVA-rate provider tests. The full resource test files remain unhealthy for reasons present in `HEAD` before this change: `test_registry.py` expects an absent `topics` field, and `test_singletons.py` imports an absent `_repos.topics` module. Running the registry file without the repository-wide conftest produced one `topics` expectation failure; normal collection also stops on that missing import and the workspace currently lacks the published authority artifact. These are not introduced by the deleted IVA-rate repository and do not provide a compatibility path for it.

## Recommendations

Repair the unrelated topic-repository test baseline under its owning work, rather than expanding S57. Final verdict: CLEAR for the scoped S57 rate-repository retirement. `iva_rate_tables.py`, its `ResourceRegistry` field, and its singleton contract are absent; all live IVA rate paths resolve the canonical `iva-rate-schedule` authority fact. Retaining `_grounding.py` is explicit and justified: the classified legal raw tables still have three production readers, and S85 requires their lossless typed fact migrations plus equivalent authority evidence refusal before deletion.
