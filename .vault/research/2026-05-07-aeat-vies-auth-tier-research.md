---
tags:
  - '#research'
  - '#live-parity-oracle'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - '[[2026-05-07-aeat-vies-surface-split-ixvi-vs-groi-adr]]'
  - '[[2026-05-06-aeat-nif-iva-checker-adapter-adr]]'
---


# `aeat-vies-auth-tier` research: empirical findings on which AEAT auth tier unlocks which VIES surface

## Summary

Live probing on 2026-05-07 via the project's
`DefaultBrowserSession` + cl@ve-movil authentication
(redacted operator identity) established two empirical findings:

1. **GROI servlet on www2** (Spanish-ROI consult, form action
   `ConsultaOperadorSedeGroiServlet`) IS reachable under cl@ve-movil.
   The form renders, accepts a 9-char Spanish NIF, and returns the
   expected `CONSTA UN OPERADOR INTRACOMUNITARIO` certification text.
   End-to-end verified for A28015865 (Telefónica, registered) and
   B00000001 (syntactically invalid).

2. **IXVI servlet on www1** (foreign-EU VIES proxy, form action
   `ConsultaIntracomunitarios`) IS NOT reachable under cl@ve-movil.
   Direct GET and click-from-sede-entry both result in HTTP 200
   landing on `https://sede.agenciatributaria.gob.es/Sede/errores/erro4033.html`
   (page title "Agencia Tributaria: 403"). The same authenticated
   session that unlocks GROI is rejected by IXVI.

The IXVI failure is now surfaced by `is_aeat_auth_gate_redirect` and
the `SedeFailureMode.AUTH_GATE_DETECTED` enum value committed in
073228b8.

## Open question

What auth tier does the IXVI servlet require?

Hypotheses, ranked by likelihood:

1. **X.509 certificate (FNMT-RCM or similar)** — the AEAT eIDAS
   ladder treats certificates as the highest authentication
   guarantee level. Many AEAT services that gate harder than
   cl@ve-movil are reachable under certificate. Plausible blocker.
2. **Caller's NIF must itself be ROI-registered** — the IXVI servlet
   verifies foreign NIF-IVAs, but AEAT may restrict the verification
   service to operators who themselves are in the ROI registry
   (modelo 036/037 with box 582 marked). The redacted probe NIF may
   not be ROI-registered.
3. **Geo-restriction** — unlikely but not yet ruled out; the live
   probe ran from a Spanish residential IP.
4. **Specific service-level subscription / signed-up user agreement**
   — some AEAT services require a separate sign-up.

## Probing methodology (re-runnable)

When certificate auth becomes available locally:

1. Configure certificate provider:
   `uv run --no-sync aeat setup auth configure --provider certificate --file <p12_path>`
2. Authenticate:
   `uv run --no-sync aeat setup auth login --fresh`
3. Run the probe script:
   `uv run --no-sync python .tmp/probe_aeat_vies_surfaces.py`
4. Inspect the IXVI line:
   - Landing URL `agenciatributaria.gob.es/Sede/errores/erro4033.html`
     -> certificate also blocked; advance to hypothesis (2).
   - Landing URL contains `ConsultaIntracomunitarios` and form
     count > 0 -> certificate UNLOCKS IXVI; the parallel-agent
     `_nif_iva_check.py` driver becomes runnable, capture form HTML
     and replace the fallback selector lists with verified specific
     selectors.

Hypothesis (2) test (after hypothesis 1 confirmed-or-denied):
register the probe NIF as an intra-community operator (modelo 036
box 582 + AEAT approval cycle) and re-run the IXVI probe under the
same auth that previously failed. Outcome:
- Now succeeds -> hypothesis (2) confirmed; IXVI requires both
  certificate AND ROI-registered caller.
- Still fails -> escalate to AEAT support or a different consultation
  surface entirely (e.g., the EU Commission's public VIES at
  ec.europa.eu, which requires no AEAT auth at all but lives outside
  the host-pinning allow-list).

## Cl@ve-movil empirical pattern (recorded for future agents)

The pattern of "cl@ve-movil unlocks consult-Spanish surfaces but not
consult-foreign surfaces" is consistent with AEAT's general design:
Spanish-resident operators get lighter-tier consult of Spanish
counterparties via cl@ve-movil, while VIES verification of foreign
counterparties requires the operator to be ROI-registered themselves
and to authenticate at a higher tier. Future surfaces (modelo 349
counterparty validation, modelo 369 OSS validation, etc.) should be
expected to follow the same auth-tier ladder unless probed otherwise.

## Decision pending

Until certificate auth is probed, the live parity catalogue ships:

- `aeat-groi-spanish-roi-checker` — usable now, end-to-end verified.
- `aeat-nif-iva-checker` — registered but `verify_payload` raises
  `SedeNavigationError(failure_mode=auth_gate_detected)` with the
  full empirical context until the auth tier is unblocked.

A modelo cross-reference may bind to either id; the audit pass at
boot will surface the IXVI binding's auth-gate status without
breaking the registry.
