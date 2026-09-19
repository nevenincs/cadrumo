---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-26'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:a33464395e9df018cb3f71bd9c323abbf16e739961ada8e23a1c7b7a3760f813'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `calculation-correctness-campaign` audit: `cross period clean state suite red from the external import evidence refusal`

## Scope

Attribution pass over a red test slice, run to establish whether today's
campaign landings regressed anything. Sequential (`-n 0`), because the parallel
run died with six `node down` workers on this worktree's backing share and that
signal is not diagnostic. Read-only; no production code changed.

Measured: `src/cadrumo/domain/portals` plus `src/cadrumo/application/calculations`,
33 failed, 765 passed, 4 errors, 21m10s.

## Findings

### CORRECTION: the attribution in the first version of this audit was wrong

This document originally blamed commit `5662e92b44` (2026-08-26) and framed the
slice as broken by work landed that day. Both claims were wrong, established by
an independent adjudication and verified here against `git blame`.

The refusal at `src/cadrumo/application/modelo/external_import_actions.py:485`
was introduced by `fb5b2fc6ea` (2026-08-11, "S58: close immutable filing
evidence lifecycle"). `5662e92b44` blames only to the `if` line at :484 and
contributed the module rename `_external_import_actions.py` ->
`external_import_actions.py`. A second twin raise exists at :220 on the
`import_external_filing_source` path, from `4299a31a15` (2026-08-23).

The refusal is therefore roughly sixteen days old, not one day. The slice has
been red since 2026-08-11, and the original framing would have misrouted a peer
to a commit that only renamed the module.

### The refusal is unconditional, so no fixture can satisfy it

    if work_unit.modelo == Modelo.M303.value:
        raise ExternalModeloImportError(... m303_filing_evidence_required ...)

There is no guard and no evidence inspection: it fires on every modelo 303
external import. The revision the same function builds hardcodes
`filing_instance_evidence=None`, and the public signature exposes no parameter
through which a caller could supply typed filing-instance evidence. The EN
locale states the position plainly -- modelo 303 external import "requires
complete typed filing-instance evidence and cannot infer it from casilla
values".

This retracts the first version's central judgement. The refusal is neither
correct-and-fixture-satisfiable nor over-broad. It is a categorical
not-yet-implemented stop wearing an error message, and the fixture-side remedy
this document recommended is impossible: fixtures cannot supply what the API has
no parameter to accept.

The fixtures do genuinely reach it -- `_cross_period_clean_state_support.py:443`
imports external filing evidence for the M390 source quarters, which are M303.

### The owning Step is marked complete

`W04.P07.S58` in `.vault/plan/2026-08-10-aeat-export-fragment-generator-authority-plan.md`
is `[x]`. It claims to have made complete typed M303 filing evidence part of
encrypted immutable revision creation. On the external-import path the delivered
behaviour is a blanket refusal, and sibling S59 defers to it explicitly.

That is the failure `aeat-agent-orchestration` names: delivered-as-specified,
delivered-narrower and recorded-but-not-implemented wearing the same checkbox.

### The failure count in the first version is stale

It recorded 33 failed / 4 errors for the slice. A later sequential run reached
roughly 55 per cent showing 72 failures and 15 errors. Do not scope remediation
off either number; re-measure before acting.

## Recommendations

- Route this to the owner of `W04.P07.S58`, not to `5662e92b44`. The fix is to
  give `import_external_filing_evidence` a typed filing-evidence parameter and
  thread it through -- implementing what S58 already claims -- which is that
  campaign's work and its Step's completion claim to answer for.
- Do not relax the refusal to restore green. It guards a real gap.
- Do not reroute the fixtures through
  `_cross_period_clean_state_support.py:436`'s no-import helper either. That
  helper exists to omit justificante metadata; using it to dodge the M303
  refusal would hide the construct from the matcher, which the quality-gate
  rules forbid as squarely as weakening the refusal itself.
- Re-measure the slice sequentially before scoping any remediation.
- Treat this slice as red for attribution purposes until S58's gap is closed:
  it cannot currently confirm or deny a regression from any other campaign.
