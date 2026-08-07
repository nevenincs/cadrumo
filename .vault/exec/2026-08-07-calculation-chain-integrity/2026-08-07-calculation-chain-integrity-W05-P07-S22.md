---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a84bc41b69fb3b6471b148a7454f1eb7d284b935f60db61a8cdc98a40f1fc889'
step_id: 'S22'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S22

## Outcome

**Landed.** Both preconditions the earlier pass recorded came true, and the mechanical half of this Step is now done. `src/` is clean on ruff and the size ratchet is four findings tighter.

The earlier pass left this unchecked with two named preconditions. Re-testing them rather than assuming they still held is what unblocked it — the peer WIP had landed and the file it was holding was no longer even in the violation set.

## The lint half

Three `I001` violations in `src/`, and the honest accounting is that one was mine: my `TipoActividad` import went into `core/__init__.py` unsorted and rode a peer sweep into HEAD before I could fix it. The other two are the `core.tty` import in `_secure_input.py` and `_custody_secret.py`, both **landed** rather than in flight, so fixing them collides with nobody — which is exactly the check the earlier pass made and got a different answer to.

`src/` now reports clean.

`dev/agent_eval` still carries 57, and they are deliberately not touched. Thirteen are `I001` and mechanical, but forty-four are `D103` — a missing docstring is a sentence someone has to write, not a reordering — and the whole tree is mid-relocation under `relocation:agent_eval`. Mechanically fixing imports in a package being moved lands the fix on lines that are about to move.

## The ratchet half

`--write-baseline` cleared all four stale pins, and the diff is worth reading as a tightening rather than an absorption. Almost every changed number goes down:

    _llm_classification.py   1687 -> 1619
    core/config.py           1574 -> 1562
    ledger_add                258 -> 242
    ledger_classify           234 -> 206
    _natural_key_resolvers    245 -> 238

Two entries drop out entirely (`_ledger_read_cli.py` and `_stage_running_preflight`, both dead weight), and three tick up by one to three lines.

The important line is the one that did **not** move. `_models.py` stays pinned at 1541 while measuring 1571, because the writer refuses to lift a ceiling that was broken through. That refusal is what makes the ratchet mean anything, and it is why running the writer here is safe rather than a way of laundering tonight's growth into the baseline.

Findings: 23 → 19.

## My own contribution, stated rather than netted out

`_models.py` is 30 lines over, and roughly 14 of those are mine — the `tipo_actividad` field and its Attributes entry from `W03.P05.S11`. The file was already about 16 over before that, so the breach is not mine, but the addition is real.

I did not trim it. The docstring is what tells a reader that `None` means undeclared rather than "no activity", which is the distinction an aggregation has to get right; buying 13 lines of budget by deleting it would trade the documentation for the number.

## What is left, and why it is not this Step

Eleven modules and five callables remain over budget. Each needs an extraction, which is a cohesion judgement per subject, and most sit in lanes other agents are actively moving — `_ledger_bindings.py` has grown to 1913 since the earlier pass measured it at 1843, which is the clearest possible signal that it has not settled.

The Step's qualifier is "completing an already-argued intent rather than making a new decision". Extraction is a new decision every time.
