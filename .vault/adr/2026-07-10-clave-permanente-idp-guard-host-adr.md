---
tags:
  - '#adr'
  - '#clave-permanente-idp-guard-host'
date: '2026-07-10'
modified: '2026-07-17'
related:
  - "[[2026-05-06-live-parity-oracle-backend-adr]]"
  - "[[2026-04-18-auth-provider-abstraction-adr]]"
  - '[[2026-07-10-clave-permanente-idp-guard-host-research]]'
---

# `clave-permanente-idp-guard-host` adr: `Sanction the Cl@ve IdP host in the remote-state guard for auth browser-action policies` | (**status:** `accepted`)

## Problem Statement

`clave_permanente_auth_browser_action_policy` in
`src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente_support.py` builds a
`RemoteStateGuardPolicy` whose `allowed_hosts` include
`urlsplit(external.aeat.domains.clave).netloc` — the host `clave.gob.es`. The guard
model's `_validate_hosts` field validator
(`src/cadrumo/domain/calculations/registry/_remote_state_guard.py`, ~line 204) refuses any
host that fails `is_aeat_host` (`src/cadrumo/domain/calculations/registry/_aeat_hosts.py`),
which accepts only the configured AEAT apex `agenciatributaria.gob.es` plus the legacy
`aeat.es` suffix. `clave.gob.es` is under neither apex, so the builder raises
`RegistryValidationError` ("allowed host is not an AEAT host") on every invocation.

The defect is latent, not live: the function has zero production or test callers. The
Cl@ve Móvil sibling `auth_browser_action_policy` (`_clave_movil_support.py`) is
consumed at click-guard time (`_clave_movil_page_flow.py`,
`_continue_own_name_representation`) and covered by `test_clave_movil.py`; the
Permanente builder is only defined, exported in `__all__`, and cross-linked in
docstrings. `ClavePermanenteAuthProvider` (`_clave_permanente.py`) drives its login
flow without ever consulting the policy. The module docstring names the builder as the
"Remote-state guard policy builder for the headless login form", so the designed
wiring — the moment issue #283 or any guard enrollment lands — crashes at policy build.
The validator predates the current live-pull robustness campaign; the crash surfaced
2026-07-10 when a host-suffix-widening test first attempted to build the policy.

## Considerations

**What clave.gob.es is.** Cl@ve is Spain's unified government electronic-identification
platform (Gobierno de España), not an AEAT data surface. Public Cl@ve documentation
(clave.gob.es, "Cl@ve: How does it work?") describes the gateway flow: the relying
service hands the browser to the Cl@ve gateway, the gateway redirects to the
method-specific identification screen, then returns the browser to the service. The
publicly observable Cl@ve login host is `se-pasarela.clave.gob.es` — a subdomain of the
apex, which matters for the fix shape: an exact-host entry `clave.gob.es` would not
match the real IdP host under `_host_within_policy` exact membership even if it
validated.

**Project-internal grounding that the Permanente flow lands on the IdP.**
`src/cadrumo/core/external_constants.toml` (section `aeat.clave_permanente`) declares
`idp_host_marker = "clave.gob.es"` alongside IdP form selectors (`#usuario_login`,
`#password_login`, `#enviar_login`) with the authoring comment that the values were
"captured from the live Cl@ve login page" and that "the Cl@ve IdP itself then branches
to the DNI/NIE + password form" after the AEAT selector page
(`SelectorAccesos.html` with `aut=CP`, an AEAT sede host).
`ClavePermanenteAuthProvider._drive_login_form` fills exactly those IdP selectors
mid-flow. The Móvil flow, by contrast, stays on AEAT hosts throughout: its QR/push
screens are AEAT sede paths (`/wlpl/MOVI-P24H/...`), which is why the Móvil policy
legitimately lists only agenciatributaria hosts and builds fine.

**Honesty limit.** No replayable Cl@ve Permanente trace exists in this repository, and
the operator holds only Cl@ve Móvil credentials, so the exact runtime redirect chain
(including the precise IdP subdomain) cannot be re-verified live from here. The
grounding is: the project's own captured-form-shape data in `external_constants.toml`
(marked "needs-design", issue #283) plus public Cl@ve platform documentation. That is
sufficient to rule the guard-model question — the policy's allowed actions are, by the
code's own design, executed on a Cl@ve IdP page — but the eventual live wiring must
re-confirm the observed IdP hostname before the Permanente flow is enabled for real
use.

**Guard mechanics that kept the defect invisible.** `allowed_hosts` is enforced at
runtime only for `http`-kind operations (`_evaluate_http` via `_host_within_policy`);
`_evaluate_browser_action` checks action text against forbidden tokens and the allowed
pattern set, never hosts. For the two auth policies — whose sole consumers submit
`browser_action` operations — `allowed_hosts` is therefore build-time declarative data.
This is why an unbuildable policy could sit unnoticed, and also why sanctioning the IdP
apex widens no runtime data-host acceptance today. It must still be narrow: a future
`http`-kind consumer inherits the declared host set with real enforcement teeth.

**Security posture.** The remote-state guard is the deny-by-default refusal of non-AEAT
surfaces (live-parity-oracle backend ADR: "pins AEAT hosts, blocks write methods,
rejects forbidden action tokens"). Any IdP allowance must be a separate, explicit,
opt-in mechanism scoped to the single national-IdP apex — never a widening of
`is_aeat_host`, never an arbitrary `gob.es` admission, and never available to data-read
policies that have no business naming an identity provider.

## Considered options

- **Option A (chosen) — explicit, opt-in government-IdP sanction in the guard model.**
  A new `RemoteStateGuardPolicy` boolean field (default false) opts a policy into a
  closed sanctioned-IdP host set derived from `external.aeat.domains.clave` (exactly
  one apex: `clave.gob.es`, subdomains admitted by suffix). Host validation admits IdP
  entries only when the policy opts in AND is `authenticated_read_surface` with
  `requires_authentication` true. Pro: honest declarative data (the login actions do
  run on the IdP page), AEAT-data predicate untouched, refusal preserved everywhere
  else, unbuildable-policy crash fixed. Con: one more field and validation phase on the
  guard model.
- **Option B — remove `clave.gob.es` from the Permanente policy.** Pro: zero
  guard-model change; the policy builds. Con: misdeclares the surface — the three
  allowed actions (fill username, fill password, submit) execute on the Cl@ve IdP page
  per the project's own captured markers; a policy claiming the actions happen on AEAT
  hosts is dishonest data and would silently mislead any future `http`-kind consumer or
  a browser-action host-enforcement extension. Rejected.
- **Option C — delete the dead builder until #283 wires the Permanente guard.** Pro:
  honest about dead capacity (the no-dormant-resolver discipline shape). Con: removes
  the designed guard surface without fixing the model inability to describe a
  federated-IdP auth flow; the identical crash returns the day the wiring lands.
  Rejected as the ruling, partially absorbed: the ruling mandates a build test so the
  policy stops being untested dead weight.
- **Option D — widen `is_aeat_host` to accept `clave.gob.es`.** Rejected outright:
  conflates "AEAT-owned data surface" with "sanctioned identity provider", lets every
  data-read policy pin the IdP host, and corrupts `first_aeat_host`-based semantics
  (e.g. the synthetic-data-on-AEAT-host prohibition).

## Constraints

- No live Cl@ve Permanente trace is obtainable (operator has Móvil only); the sanction
  is apex-suffix-shaped so the publicly observed `se-pasarela.clave.gob.es` login host
  is covered without enumerating unstable IdP subdomains. Live wiring (#283) must
  re-confirm the observed hostname before enabling the flow.
- `_validate_hosts` and `_validate_host_suffixes` are field validators with no view of
  the policy classification or the opt-in flag; the IdP admission must be evaluated
  in the `_validate_policy` model-validator phase (or host validation moves there),
  keeping the field validators as the syntactic plus AEAT-host gate for non-opt-in
  entries.
- Per the `aeat-schema-central-config` rule, the sanctioned apex derives from the
  existing `aeat.domains.clave` entry in `external_constants.toml`; no inline host
  literal. The literal-scan fixtures (`src/cadrumo/tests/aeat_literal_fixtures.py`,
  `PORTAL_LITERAL_SCAN_TOKENS` already tracks `clave.gob.es`) police inline copies.
- Out of scope, recorded for #283: extending runtime host enforcement to
  `browser_action`-kind operations (today hosts bind only `http`-kind evaluation). This
  decision neither adds nor depends on that enforcement.
- Parent-surface stability: the guard model and the `_aeat_hosts.py` predicates are
  stable, accepted surfaces (live-parity-oracle backend ADR); the Permanente IdP form
  markers are the declared least-stable surface ("needs-design", #283) but are data,
  not code, and do not gate this decision.

## Implementation

Code-surface footprint of the chosen fix (implementation follows as a separate grounded
commit; nothing here is implemented by this ADR):

- `src/cadrumo/domain/calculations/registry/_aeat_hosts.py`: add
  `sanctioned_gov_idp_host_suffixes()` returning the netloc of
  `Settings.external_constants().aeat.domains.clave` (single-member tuple) and an
  `is_sanctioned_gov_idp_host(host)` suffix predicate mirroring `is_aeat_host`.
- `src/cadrumo/domain/calculations/registry/_remote_state_guard.py`: new
  `RemoteStateGuardPolicy` field `allows_gov_idp_hosts: bool` defaulting to false;
  `_validate_hosts` and `_validate_host_suffixes` defer non-AEAT entries that are
  sanctioned-IdP hosts to the model phase; `_validate_policy` gains a phase refusing
  (a) any IdP host on a policy that has not opted in, (b) opt-in on any classification
  other than `authenticated_read_surface` or with `requires_authentication` false, and
  (c) any non-AEAT, non-sanctioned host unconditionally (unchanged behaviour).
- `src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente_support.py`:
  `clave_permanente_auth_browser_action_policy` sets `allows_gov_idp_hosts=True` and
  carries the Cl@ve apex as an `allowed_host_suffixes` entry (so IdP subdomains match
  if an `http`-kind consumer ever appears), keeping the two AEAT hosts; add the missing
  `-> RemoteStateGuardPolicy` return annotation.
- Tests: `src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_permanente.py` gains
  policy-build coverage mirroring `test_clave_movil.py` (policy builds; the three
  `clave-permanente-*` patterns allowed; unlisted actions refused).
  `src/cadrumo/domain/calculations/registry/tests/test_remote_state_guard.py` gains: IdP
  host refused without opt-in; opt-in refused on `open_simulator` and
  `public_read_surface`; an arbitrary `gob.es` host refused even with opt-in; Móvil
  policy behaviour unchanged.
- Untouched: `is_aeat_host`, `first_aeat_host`, every data-read policy, the Móvil
  policy, and the currently-unconsumed `idp_host_marker` (its consumption belongs to
  the #283 wiring, not this fix).

## Rationale

The guard exists to refuse non-AEAT surfaces, and that refusal is correct for every
data-read policy — the bug is not that the validator is strict but that the model has
no vocabulary for the one legitimate non-AEAT host class an authenticated flow
structurally requires: the national identity provider AEAT itself delegates to. The
project captured constants (`idp_host_marker` set to `clave.gob.es`, the IdP form
selectors the provider fills) and public Cl@ve platform documentation both place the
Permanente password form on a clave.gob.es page, so removing the host (Option B) would
trade a loud build crash for quietly false declarative data, and widening the AEAT
predicate (Option D) would weaken the load-bearing refusal everywhere. A separate,
explicit, opt-in sanction — one apex, sourced from central config, admissible only on
authenticated policies — fixes the unbuildable policy while leaving the AEAT-data
restriction byte-identical for every other policy in the tree. Because browser-action
evaluation never consults hosts, the sanction changes no runtime admission today; it
makes the declared data honest and the future enforcement extension safe.

## Consequences

- Good: the latent `RegistryValidationError` crash is removed; the Permanente guard
  policy becomes buildable and gains its first build test, ending its
  untested-dead-code state.
- Good: the guard model gains an explicit, auditable vocabulary for federated-IdP
  hosts — one greppable opt-in flag plus one central-config-derived apex — instead of
  an implicit precedent of hosts smuggled past a weakened predicate.
- Good: AEAT-data host pinning is unchanged for all existing policies; new refusal
  paths (IdP host without opt-in, opt-in on the wrong classification, arbitrary
  `gob.es`) are added, so the posture is strictly tightened for everyone but the one
  sanctioned auth flow.
- Bad, accepted cost: the sanction is grounded in captured form-shape data and public
  Cl@ve documentation, not an in-repo live Permanente trace; if the Cl@ve gateway host
  scheme changes, the declared apex could drift until the #283 live wiring re-confirms
  it. This is declarative-data risk only, since no runtime host admission rides on it
  today.
- Neutral: the browser-action host-enforcement gap (hosts unchecked for
  `browser_action`-kind operations) is now recorded; closing it is deliberately
  deferred to the #283 wiring where a real consumer exists to exercise it.
- Neutral: one more field on `RemoteStateGuardPolicy` and one more validation phase;
  policies that never opt in are unaffected.

## Addendum: submit-action write-token collision

Appended 2026-07-10 by an authorized fable ruling pass; accepted 2026-07-10 per the operator's standing "Fable-authored ADRs accept automatically" ruling. This
addendum rules the second latent defect surfaced by the build coverage above and honestly
documented in `test_policy_submit_action_is_write_token_blocked`: the third allowed action
pattern, `clave-permanente-submit`, contains the universal write-forbidden token `submit`
(`AEAT_WRITE_FORBIDDEN_VERB_TOKENS`,
`src/cadrumo/domain/calculations/registry/_remote_state_guard.py:76`), and
`_evaluate_browser_action` checks forbidden tokens BEFORE the allow-list
(`_remote_state_guard.py:423-433`), so the guard refuses the login-form submit at runtime
and Cl@ve Permanente authentication can never complete.

**Ruling 1 — classification: authentication, not an AEAT tax-filing write.** The action
behind the label is the Cl@ve national-IdP LOGIN form submit: `external_constants.toml`
`[aeat.clave_permanente]` declares `submit_button_selector = "#enviar_login"` on the
`clave.gob.es` IdP page, and successful completion creates an authenticated SESSION — no
declaration, presentation, payment, or any AEAT server-side filing state. The write-token
block exists (per `aeat-safety-legal-gates` and the token set's own docstring) to refuse
state-modifying AEAT calls — the presentar/firmar/pagar/TGVI class. An IdP credential
login is categorically outside that class; the collision is lexical (our own action label
happens to contain the English token `submit`), not semantic. The correct resolution is
therefore to rename OUR label, never to carve an exception into the guard.

**Ruling 2 — replacement label: `clave-permanente-authenticate`.** Verified clean by
substring scan (`_first_forbidden_token` matches `token in value`) against the full
`_FORBIDDEN_TOKENS` union — every member of `AEAT_WRITE_FORBIDDEN_VERB_TOKENS` and
`_URL_AND_METHOD_FORBIDDEN_TOKENS` — and, for cross-surface hygiene, against the
click-time extension set `_CLICK_ONLY_FORBIDDEN_TOKENS` in
`src/cadrumo/adapters/outbound/aeat/sede/_renta_web_open_safety.py`. Rejected alternatives:
any `enviar`/`send`-derived label (both are tokens); a `validate-credentials` label
(passes the guard today, but the `validar`/`validacion` family is a click-time forbidden
extension because AEAT's Validar surface is pre-presentation write-adjacent — reusing that
stem for a benign action invites confusion and future collision); a `confirm`/
`login-confirm` label (passes today only because the set carries the Spanish
`confirmar`/`confirmacion` and not English `confirm`; the English equivalent plausibly
joins the set later, recreating this defect). `authenticate` is durable: it names an auth
verb that by definition never belongs in a write-verb denylist, and it accurately
describes the operation (present the filled Cl@ve credentials to the IdP).

**Ruling 3 — hard constraint: the token filter is untouchable.** The fix is ONLY the
action-label rename. `AEAT_WRITE_FORBIDDEN_VERB_TOKENS`,
`_URL_AND_METHOD_FORBIDDEN_TOKENS`, the token-before-allow-list evaluation order in
`_evaluate_browser_action`, and every derived consumer set (`FORBIDDEN_CLICK_TOKENS`)
MUST NOT be modified, weakened, reordered, or given a bypass parameter. Every genuine
AEAT tax-filing write action stays blocked. The implementing commit MUST include a test
proving the safety net is intact after the rename: a browser action whose name carries a
genuine write verb (e.g. containing `presentar`, `submit`, or `enviar`) is STILL refused
by the Permanente policy even though the policy allow-list exists — mirroring the shape
of the current `test_policy_submit_action_is_write_token_blocked`, which that test
replaces.

**Code-surface footprint (one atomic change).** `clave-permanente-submit` has exactly
three references in the tree; the policy is currently unconsumed and
`ClavePermanenteAuthProvider` (`_clave_permanente.py`) emits no browser-action labels at
all, so nothing else moves:

- `src/cadrumo/adapters/outbound/aeat/auth/_clave_permanente_support.py:84` — the
  `allowed_browser_action_patterns` tuple entry (rename to
  `clave-permanente-authenticate`); also update the builder docstring's "(username fill,
  password fill, submit)" wording at ~line 57.
- `src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_permanente.py:100-114` —
  replace `test_policy_submit_action_is_write_token_blocked` with (a) the renamed action
  is allowed, and (b) the Ruling-3 still-blocked write-verb test.
- When the #283 wiring lands a provider/page-flow that raises `browser_action`
  operations against this policy, it MUST emit the renamed label; the policy pattern and
  the emitter stay in lockstep (today there is no emitter).

**Ruling 4 — no live re-confirmation is needed for the rename itself.** The action label
is project-internal naming for our own guard vocabulary — not an AEAT- or Cl@ve-observed
token. The AEAT-observed data (`submit_button_selector = "#enviar_login"`,
`idp_host_marker`) is untouched, and the guard never scans selectors on the
`browser_action` path (it evaluates only `operation.action`). The parent ADR's honesty
limit stands unchanged: before the Permanente flow is enabled end-to-end, the #283 live
wiring must re-confirm the captured IdP form semantics (selectors, host) — but that
obligation predates and is independent of this rename.
