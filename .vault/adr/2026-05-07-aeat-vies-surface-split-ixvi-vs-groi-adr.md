---
tags:
  - '#adr'
  - '#live-parity-oracle'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - '[[2026-05-06-aeat-nif-iva-checker-adapter-adr]]'
  - '[[2026-05-06-live-parity-oracle-backend-adr]]'
  - '[[2026-05-06-cross-reference-oracle-binding-adr]]'
  - "[[2026-05-06-live-parity-oracle-backend-research]]"
---


# `aeat-vies-surface-split-ixvi-vs-groi` adr: `Split the AEAT VIES verification surface into two sibling adapters` | (**status:** `accepted`)

## Review State

This ADR is accepted as the operational record of a live-probing
finding from 2026-05-07. The original AEAT NIF-IVA checker ADR
(2026-05-06) scoped a single oracle adapter targeting the AEAT-hosted
foreign-EU VIES proxy at the IXVI servlet on www1. Live probing under
cl@ve-movil authentication (redacted operator identity, captured via the
project's DefaultBrowserSession) revealed:

- The IXVI servlet at www1 (foreign-EU VIES proxy) returns HTTP 200
  but redirects to `/Sede/errores/erro4033.html` (403 page) under
  cl@ve-movil. The same authenticated session does not unlock IXVI.
- The GROI servlet at www2 (Spanish-ROI consult) IS reachable under
  the same cl@ve-movil session. The form renders, accepts a 9-char
  Spanish NIF, and returns a verdict text including
  ``CONSTA UN OPERADOR INTRACOMUNITARIO`` (registered) or
  ``no es un NIF válido`` (input-format error).

The two surfaces serve fundamentally different verification needs.
Treating them as a single oracle would couple the auth-tier blocker
of one to the workable surface of the other.

## Problem Statement

The original `_aeat_nif_iva_oracle.py` adapter declared a single
``aeat-nif-iva-checker`` oracle id targeting the IXVI form. That id is
now wired into the live parity catalogue with the assumption that
``cl@ve-movil`` is sufficient. The live probe disproves the
assumption: cl@ve-movil unlocks GROI, not IXVI.

If the project ships only the IXVI adapter, no AEAT-side VAT-ID
verification works under cl@ve-movil at all — the entire oracle is
inert until the auth tier IXVI requires (presumably certificate plus
ROI-registered caller) is figured out and wired through.

If the project conflates the two surfaces under one oracle id, the
binding semantics get muddled: a cross-reference declaring
``oracle_id = "aeat-nif-iva-checker"`` for a Spanish counterparty is
asking the wrong question (the ROI registry, not VIES) and a
cross-reference declaring it for a foreign EU counterparty hits the
auth-gated surface and fails.

The two surfaces also differ in form structure (single Spanish NIF
input vs. country-code dropdown plus VAT number) and verdict semantics
(``CONSTA UN OPERADOR INTRACOMUNITARIO`` vs. VIES ``valid``/``invalid``),
which makes the per-NIF query, response parser, and host pinning
materially different code paths.

## Decision

The project ships two sibling sede adapters with two distinct oracle
ids and overlapping host-pinning suffix:

1. ``_groi_check.py`` exposes ``GroiSedeDriver`` and oracle id
   ``aeat-groi-spanish-roi-checker``. Targets
   ``https://www2.agenciatributaria.gob.es/wlpl/GROI-JDIT/ConsultaOperadorSedeGroiServlet``.
   Verifies whether a Spanish NIF is registered in the Spanish
   ROI registry. Reachable under cl@ve-movil. Use case: confirming
   Spanish counterparties on modelo 349 are ROI-registered, since
   modelo 349 is the EU intra-community recapitulative declaration
   and Spanish counterparties on it must hold ROI registration.

2. ``_nif_iva_check.py`` keeps oracle id ``aeat-nif-iva-checker``
   and continues to target
   ``https://www1.agenciatributaria.gob.es/wlpl/IXVI-JDIT/ConsultaIntracomunitarios``.
   Verifies foreign-EU VAT-IDs through AEAT's VIES proxy. Currently
   gated by an auth tier above cl@ve-movil; the existing auth-gate
   detector emits a precise diagnostic naming this empirical finding.
   Use case: confirming foreign EU counterparties on modelo 349
   hold a valid VAT identifier, once the auth path is unblocked.

Both adapters share the existing ``agenciatributaria.gob.es`` host-
pinning suffix in the remote-state guard, so neither requires an
allow-list expansion.

The two adapters do not share code beyond the public sede helpers
(``_browser_stage`` runner factory, ``SedeFailureMode`` enum,
``BrowserSession`` lifecycle). Form selectors, verdict markers, and
URL constants are owned per adapter.

## Constraints

The two adapters must not share oracle ids in the live parity
catalogue. A modelo cross-reference binding the wrong oracle id to
its surface would make the audit pass silently while the actual
verification fails (or asks the wrong service). Distinct ids force
the modelo TOML to declare which question is being asked.

The two adapters must not share verdict markers. The GROI verdict
phrases (Spanish certification text from
``ConsultaOperadorSedeGroiServlet``) differ from the IXVI VIES proxy
phrases. Sharing a parser would either be a lowest-common-denominator
miss or a maintenance liability.

The two adapters must not share URL constants. A drift on one URL
must not silently retarget the other.

## Implementation Direction

The GROI adapter is implemented in this commit slice
(``_groi_check.py``, ``test_groi_check.py``, 17 offline tests + a
live probe under ``.tmp/`` confirming end-to-end correctness against
Telefónica's NIF and a syntactically invalid NIF).

The IXVI adapter remains in ``_nif_iva_check.py`` (parallel-agent
implementation) with the auth-gate diagnostic sharpened to record
the cl@ve-movil empirical finding (commit 073228b8). Future work:

- Probe certificate auth against IXVI; if certificate unlocks, no
  further changes needed. If certificate also 4033s, document the
  remaining barrier (likely caller must be ROI-registered).
- If certificate works, capture form HTML live and replace the
  parallel agent's fallback selector lists with verified specific
  selectors.

## Rationale

Two distinct surfaces serving distinct verification needs map
cleanly to two distinct oracle ids in the live parity catalogue. A
modelo cross-reference declaring an ``oracle_id`` then explicitly
chooses the question being asked, and the audit pass surfaces
mismatches between cross-reference surface and bound oracle (per the
oracle-surface-compatibility ADR) at boot time.

The GROI adapter delivers immediate value: Spanish counterparty
verification on modelo 349 unlocks now. The IXVI adapter retains
its existing scope so foreign-EU verification can land when the
auth tier is figured out, without retroactively forcing a second
refactor.

The decision deliberately does not centralise common Playwright
selector or verdict logic between the two adapters. The two AEAT
forms are different enough that shared abstractions would be either
trivial (shared by accident) or premature (forcing future drift to
fork two callers). Sibling files that own their own selectors and
verdict markers stay honest about what they verify.

## Consequences

The live parity catalogue grows by one oracle id
(``aeat-groi-spanish-roi-checker``). Modelos that need Spanish
counterparty ROI verification can declare an ``oracle_id`` binding
on the corresponding cross-reference now.

The IXVI adapter remains a NotImplementedError-equivalent under
cl@ve-movil; its diagnostic now names the empirical auth tier finding
and the suggested next steps. Production callers attempting to use
``aeat-nif-iva-checker`` under cl@ve-movil get a precise SedeNavigationError
with ``failure_mode=auth_gate_detected`` instead of a misleading
shape-change error.

Future foreign-EU verification work has a documented unblock path
(certificate auth probe) and a documented fallback path (pivot to
the EU Commission's public VIES at ec.europa.eu, requires host-pinning
expansion).

## Explicit Non-Decisions

This ADR does not bind any modelo cross-reference to either oracle
id. Each modelo TOML may opt in when its parity ledger calls for it.

This ADR does not change the host-pinning policy. Both adapters use
existing AEAT subdomains under the existing ``agenciatributaria.gob.es``
suffix.

This ADR does not commit to certificate auth as the IXVI unblocker.
That is a hypothesis to test in a follow-up. The conclusion may be
that IXVI requires the caller's NIF to be ROI-registered, which is
a separate prerequisite.

## Open Review Questions

Should the GROI adapter participate in the calculation-engine
audit-on-startup wiring (the boot-time
``audit_registry_oracle_bindings`` call)? Currently the audit needs
a populated catalogue to do anything; registering GROI at bootstrap
would make any modelo binding to it visible in the boot health
report.

Should there be a third oracle id reserved for the EU Commission's
public VIES at ec.europa.eu, in case certificate auth ALSO does not
unlock IXVI? That oracle would need a host-pinning expansion and
would be the only project oracle outside AEAT-controlled hosts.
