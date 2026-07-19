---
tags:
  - '#audit'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-19'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
  - "[[2026-07-17-auth-cert-recovery-custody-adr]]"
  - "[[2026-07-16-cli-authority-verb-conformance-duplication-authority-audit]]"
---

# `auth-cert-recovery-custody` audit: `certificate secret door safety review`

## Scope

Independent, fresh-context safety review of the certificate-secret CLI door landed by plan phases P05 and P07 — the `certificate secret set` and `remove` verbs, their secure-storage custody, secret-mutation event handling, and the removal of the production test-double seam. The review examined `_config/_certificate.py` and the secret-store factory path.

**Verdict: PASS.** No Critical, High, or Medium findings. One Low hardening item.

## Findings

### secret-secure-storage-only | confirmed | Certificate secrets persist only in secure storage, addressed by name

Certificate secrets are set and removed only by name through secure storage, with no plaintext side store and no path pointer standing in for the secret bytes. The door exposes no compatibility alias or migration surface.

### single-custody-authority | confirmed | No certificate keyring backend or backend selector

The certificate-specific keyring backend, backend selection, and key set were removed, so selected-profile secure storage is the sole certificate-secret authority; independent master-key OS-keyring custody remains untouched and is not conflated with it.

### secret-mutation-idempotent-event | confirmed | A failure after mutation before event commit retries to one correctly-classified event

A command failure after the secret mutation but before the event commit, followed by an idempotent retry, yields exactly one correctly-classified event. Backend selection, keyring spellings, migration, fallback, and duplicate mutation paths are all rejected.

### secret-input-default-safe | confirmed | The default secret-input path is a hidden prompt with no echo

The default secret-input path is a hidden, no-echo prompt (the `prompt=True, hide_input=True` option), so an operator following the intended flow never exposes the passphrase. This default is safe; the argv affordance below is the only residual exposure.

### no-production-test-double-seam | confirmed | The module-global secret-store override seam is removed

The module-global `override_secret_store` test-double seam was removed in favour of constructor dependency injection, and an AST recurrence gate bans its reintroduction, so no test double lives in the production secret-store path.

### low-1-argv-secret-affordance | low | certificate secret set accepts the PKCS#12 passphrase as an argv value

`certificate secret set --secret` accepts the PKCS#12 passphrase as an argv value (`_config/_certificate.py` around lines 391-401, `secret: str = typer.Option(..., "--secret", prompt=True, hide_input=True)`). The hidden-prompt and stdin default is safe, but the argv-value affordance lets a caller pass `--secret hunter2` on the command line, landing the passphrase in the process table (visible via `ps` to other local users) and in shell history. This is the same no-argv-secret class as the P04 door's invariant. Remediation: make the verb prompt/stdin-only, reusing the P04 door's bounded-stdin/no-echo `_secure_input.py` infrastructure once that door commits rather than building a parallel secret-input authority. Enrolled as a deferred gated hardening step in the plan.

## Recommendations

Close LOW-1 by removing the argv-value affordance from `certificate secret set` so the passphrase is read only via the hidden prompt or bounded stdin, folding into the live P04 `_config` work so it reuses `_secure_input.py` rather than duplicating a secret-input authority. The step is deferred until the operator's P04 door commits. No other action required; the P05 and P07 cert-secret door is otherwise independently verified sound.
