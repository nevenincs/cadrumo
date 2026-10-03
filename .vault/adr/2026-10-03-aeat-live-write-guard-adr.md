---
tags:
  - '#adr'
  - '#aeat-live-write-guard'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:7d5f5d5e2af34a169d37d06650469f1f737d3e74f53e08fc84e840671391b151'
related:
  - "[[2026-08-02-adjacent-domain-deduplication-write-verb-substring-matching-adr]]"
  - "[[2026-07-10-clave-permanente-idp-guard-host-adr]]"
  - "[[2026-06-12-live-pull-verification-sweep-adr]]"
  - "[[2026-06-04-live-auth-decomposition-adr]]"
  - "[[2026-09-24-aeat-live-write-guard-plan]]"
  - '[[2026-08-01-adjacent-domain-deduplication-wave-two-audit]]'
  - '[[2026-07-10-clave-permanente-idp-guard-host-research]]'
---

# `aeat-live-write-guard` adr: `Browser-context request guard semantics` | (**status:** `proposed`)

## Problem Statement

Step S02 of the `aeat-live-write-guard` plan routes every request a browser context makes through `evaluate_remote_operation` (`src/cadrumo/domain/calculations/registry/remote_state_guard.py:424`), so that an AEAT reader that forgets its own guard call is still refused. Today the guard is called only by each reader on its own target URLs (`assert_read_http_for`, `src/cadrumo/adapters/outbound/aeat/sede/_adapter_utils.py:134`), never on the requests AEAT's pages and the Cl@ve choreography issue on the reader's behalf. Applying the unchanged guard to every request would refuse legitimate live reads and the login itself.

Re-verified on 2026-10-03 by evaluating the real guard against the real policies in the current tree:

- Cl@ve Móvil policy (`auth_browser_action_policy`, `src/cadrumo/adapters/outbound/aeat/auth/clave_movil_support.py:52`): GET `/wlpl/OVCT-CXEW/DialogoRepresentacion` is blocked by token `presentacion` (substring of `representacion`), although the login lands there (`src/cadrumo/adapters/outbound/aeat/auth/_clave_movil_page_flow.py:524`, `:562`). The own-name continuation POST to the same path and POST `/wlpl/MOVI-P24H/AutenticaDniNieContrasteh` are blocked as write methods. GET `/wlpl/MOVI-P24H/CancelarClaveMovil` is blocked by token `cancelar`.
- Cl@ve Permanente policy (`clave_permanente_auth_browser_action_policy`, `src/cadrumo/adapters/outbound/aeat/auth/clave_permanente_support.py:51`): any POST to the IdP is blocked as a write method.
- A declarations-style ZK AJAX POST to `/wlpl/SCEJ-MANT/zkau` is blocked as a write method; a ZK static asset GET under the same prefix is allowed.
- GROI (`src/cadrumo/adapters/outbound/aeat/sede/groi_check.py:110`, `integration_test_service`) and NIF-IVA (`src/cadrumo/adapters/outbound/aeat/sede/nif_iva_check.py:81`, `open_simulator`) form POSTs are blocked, and remain blocked even when their exact path is added to `allowed_read_post_paths`, because `_http_method_is_allowed` (`remote_state_guard.py:439-444`) admits a read POST only on `authenticated_read_surface`.
- Declaring `/wlpl/OVCT-CXEW/DialogoRepresentacion` in `allowed_read_post_paths` does not help: the whole-URL forbidden-token scan in `_http_policy_block_reason` (`remote_state_guard.py:447-459`, scan at `:452-458`) has no exception for policy-declared paths.

These semantics must be decided before S02 is implemented, because each obvious repair weakens a refusal whose failure mode is silence.

## Considerations

- The token matcher's direction is already settled: `2026-08-02-adjacent-domain-deduplication-write-verb-substring-matching-adr` (accepted) keeps whole-URL substring matching, measured segment matching as losing 37 real write surfaces (including `RealizarPresentacionLotes`, `TGVIOnline` and `CancelarClaveMovil`), forbids narrowing the token set, and directs that a benign collision be admitted by a surface-scoped allow-list entry, landed with the guard call it unblocks and its own coverage. This record reuses that ruling and only specifies the entry's typed form.
- `2026-07-10-clave-permanente-idp-guard-host-adr` (accepted), Ruling 3, makes the token sets, the token-before-allow-list order in `_evaluate_browser_action` and the absence of a bypass parameter untouchable. Its host sanction for `clave.gob.es` is reused unchanged; it also records that no live Cl@ve Permanente trace exists and the operator holds only Cl@ve Móvil credentials.
- `2026-06-12-live-pull-verification-sweep-adr` (accepted) governs authenticated pull-only acceptance; the `2026-10-03-live-verification-session-plan` is the authorised session that can observe the real request stream.
- `2026-06-04-live-auth-decomposition-adr` (accepted) keeps Playwright context construction in the browser session, away from operator-output code; context creation is `BrowserSession.create_context` (`src/cadrumo/adapters/outbound/aeat/browser/session.py:101`, `browser.new_context` at `:330`), not the factory module the plan names.
- A context-level guard sees network requests, not clicks; page actions keep their per-reader `browser_action` checks.
- The rules `aeat-architecture-boundaries`, `no-legacy-compatibility` and `sensitive-financial-data-secure-storage-only` bind: one canonical definition, no shim or bypass, and no taxpayer data in logs or captures.

## Considered options

Token matching (ruling 1):

- **Typed declared read request, exact method plus path, exempting only that path from the token scan (chosen).** Realises the surface-scoped allow-list entry the 2026-08-02 ADR directs; every other URL keeps substring matching.
- **Path-segment or word-boundary matching (rejected).** Already measured and rejected by the 2026-08-02 ADR; AEAT write verbs live inside CamelCase segments.
- **Drop or special-case `presentacion` (rejected).** Narrows the token set, unguarding batch presentation; forbidden by both accepted ADRs.

Read POSTs on other classifications (ruling 2):

- **Admit exact declared read POSTs on every live read classification (chosen).**
- **Reclassify GROI and NIF-IVA as `authenticated_read_surface` (rejected).** NIF-IVA is unauthenticated and `authenticated_read_surface` requires authentication; the classification would be false data.
- **Admit their POSTs through `browser_action` patterns (rejected).** The context guard sees requests, not action labels.

Cl@ve Móvil cancellation (ruling 3):

- **Declare `CancelarClaveMovil` as an exact declared request on the Cl@ve Móvil auth policy only (chosen).** It withdraws the operator's own pending identity request; it carries no tax, filing, censal or notification state. The 2026-08-02 ADR keeps it in the scan's catch set everywhere else, and this exact entry is the surface-scoped admission that ADR directs.
- **Refuse at context level and remove the cleanup call (rejected).** AEAT refuses any new Cl@ve Móvil request for up to five minutes while one is pending. The product already detects and names that refusal (`PENDING_PETITION_BLOCKED`, `_clave_movil_page_flow.py:288-324`, markers in `pending_petition_text_markers`), so removing cancellation turns every approval timeout into a lockout of up to five minutes.

Composition (ruling 4):

- **Union of the context's declared policies at a new public browser module, installed at context creation for every provider (chosen).**
- **Per-phase active policy switched by the flow (rejected).** Depends on the reader signalling correctly, which is the failure S02 defends against.
- **One global browser policy (rejected).** Duplicates per-surface posture in a second home.
- **An observe-only or bypass flag (rejected).** An off switch for a no-write guarantee.

Grounding (ruling 5):

- **Recorded live capture of method and redacted path during the authorised verification session, shipping fail-closed only afterwards (chosen).**
- **Declare paths from code reading or public documentation (rejected).** ZK and Cl@ve SAML endpoints are not observable statically; a guessed list either over-admits or breaks login.
- **Ship fail-closed immediately (rejected).** It breaks login and declarations reads before the declared set is known.

## Constraints

- No change to `AEAT_WRITE_FORBIDDEN_VERB_TOKENS`, `_URL_AND_METHOD_FORBIDDEN_TOKENS`, the substring matcher, or `_evaluate_browser_action` order. Reaffirmed from both accepted ADRs.
- A declared read request is exact: a method from a closed read set (GET, HEAD, or POST) plus an exact absolute path on a host the policy already admits. No prefixes, globs or regexes. Only the declared path is exempt from the token scan; host, query string and declared `forbidden_actions` are still scanned.
- Declared read requests live on the guard policy. They are a separate field from any landing-refusal or read-path-prefix tuple. The 2026-08-02 ADR's trap applies: on the IVA compensation wallet, the representation gate stays out of the landing tuple, and this record does not change that.
- `static_official_only` and `forbidden_stateful_surface` still refuse every live operation (`remote_state_guard.py:424-436`).
- No bypass flag, environment variable, observe mode or per-call override in product code.
- Refusal logs carry only policy ids, method, host and path. They never include the query string, body, headers, cookies or identifiers.
- Implementation hypotheses that may change within these constraints: the field name (for example `declared_read_requests`), the module name (for example `src/cadrumo/adapters/outbound/aeat/browser/request_guard.py`), and whether `allowed_read_post_paths` is folded into the new field. Under `no-legacy-compatibility` it must be folded in, not kept beside it, if the meanings coincide.

Proposed reconciliation of accepted wording (apply only once authorised):

- In `2026-07-10-clave-permanente-idp-guard-host-adr`, Ruling 3, append: "This ruling governs the token sets and the `browser_action` evaluation path. An exact, policy-declared HTTP read request under `2026-10-03-aeat-live-write-guard-adr` is the surface-scoped allow-list entry directed by `2026-08-02-adjacent-domain-deduplication-write-verb-substring-matching-adr`. It is policy data, not a bypass parameter."
- In `2026-08-02-adjacent-domain-deduplication-write-verb-substring-matching-adr`, Implementation, append: "The typed form of a surface-scoped allow-list entry on the remote-state guard is the declared read request ruled in `2026-10-03-aeat-live-write-guard-adr`. It does not alter any landing-refusal tuple."

## Implementation

Rulings:

1. **Token matching.** We will keep whole-URL substring matching and add a typed declared read request on `RemoteStateGuardPolicy`. A request that matches a declared exact method and path has only its path exempted from the token scan. This addresses `presentacion` matching inside `representacion`: the Cl@ve Móvil auth policy declares GET and the own-name POST on `/wlpl/OVCT-CXEW/DialogoRepresentacion` (path from `src/cadrumo/core/external_constants.toml:68`), and every other URL containing `representacion` stays refused.
2. **Read POSTs beyond `authenticated_read_surface`.** We will admit declared read POSTs on `open_simulator`, `integration_test_service`, `public_read_surface` and `authenticated_read_surface`. GROI declares its consult servlet path, which is already pinned by `_assert_form_action_is_consult_endpoint` (`groi_check.py:407`). NIF-IVA declares its `ConsultaIntracomunitarios` servlet path. Each change lands with the surface's coverage.
3. **`CancelarClaveMovil`.** We will declare GET `/wlpl/MOVI-P24H/CancelarClaveMovil` as an exact declared request on the Cl@ve Móvil auth policy and on no other policy. The best-effort cancellation in the timeout path (`_cancel_pending_auth_request`, `_clave_movil_page_flow.py:326`, called from `clave_movil.py:1007`) stays. Every other URL containing `cancelar` stays refused. The exact method and path are confirmed by the live capture under ruling 5 before enablement. The path markers used by landing classification (`clave_movil.py:605`) are unaffected.
4. **Composition.** We will add one public module in `src/cadrumo/adapters/outbound/aeat/browser/`. It evaluates each routed request against the union of the policies the context was created with: a request is allowed if any member policy allows it. An empty policy set refuses every request. `BrowserSession.create_context` (`session.py:101`) installs the route on the new context before any page exists, for every provider (certificate, Cl@ve Móvil, Cl@ve Permanente and unauthenticated readers). It aborts refused requests and logs them with redaction. Readers keep their own target-URL and `browser_action` checks as defence in depth. The plan's "browser factory" location is corrected to `browser/session.py`, and S02's "page action" scope is narrowed to requests. Both corrections are recorded through the plan verbs.
5. **Grounding.** We will ground unobserved read paths, such as the exact ZK endpoints under `/wlpl/SCEJ-MANT/` and the Cl@ve Móvil choreography POSTs, from a recorded live capture during the authenticated `2026-10-03-live-verification-session-plan` session. The capture records only method, host and path. Query strings, bodies, headers and cookies are discarded before anything is written, and no taxpayer data is persisted. The capture is a verification-harness listener, not a product mode. Cl@ve Permanente SAML endpoints cannot be captured with the operator's Móvil-only credentials, so its policy declares no read POSTs and the Permanente flow stays refused at context level until a grounded capture exists. This is consistent with the host re-confirmation obligation in `2026-07-10-clave-permanente-idp-guard-host-adr`. The context guard ships enabled and fail-closed only after the declared set is grounded.

Sequencing: `remote_state_guard.py` and `src/cadrumo/core/remote_authority.py` currently carry another contributor's uncommitted edits, and `browser/factory.py` with its test carries staged edits. Implementation waits until those land, then re-reads the live files before editing.

## Rationale

The knockout for ruling 1 is the 2026-08-02 measurement: any matcher change loses real write surfaces, while an exact declared path admits one known read and nothing else. Exactness is what stops the allow-list from becoming the escape hatch both accepted ADRs warn against. Ruling 2 follows because whether a POST is a read depends on the surface, not on its authentication class; the current restriction forces either false classification or broken consult oracles. Ruling 3 keeps the no-write line where it matters, on tax, filing, censal and notification state, while admitting the one identity-hygiene request whose absence locks the operator out: AEAT refuses a new Cl@ve Móvil request while one is pending, which the product already detects as `PENDING_PETITION_BLOCKED`. Ruling 4's union is safe because every member is a read-only policy and no member admits a token-bearing URL beyond its exact declarations, while the empty-set refusal turns a forgetting caller into a visible refusal instead of an unguarded context. Ruling 5 exists because a fail-closed guard declared from guesses either breaks authentication or admits too much; only the real request stream can ground it.

## Consequences

- Until this record is accepted and S02 lands, the no-write guarantee rests on the per-reader guards, the static no-write scans (for example `src/cadrumo/adapters/outbound/aeat/sede/tests/test_no_write_surface.py`), `SubmissionEngine` exposing no transport, and the MCP `live_write` refusal, as in the accepted live-pull sweep.
- Good: a reader that omits its guard is refused at the network boundary, and the `representacion` false positive is resolved without weakening the scan.
- Cost: one state-changing identity request, the operator's own pending Cl@ve Móvil cancellation, is admitted by exact declaration. Any other `cancelar` URL is still refused.
- Cost: third-party or unexpected AEAT sub-resources not covered by the capture are refused after enablement. Each one needs a grounded declaration, and a refusal is visible, not silent.
- Cost: Cl@ve Permanente login stays unavailable behind the context guard until it is grounded.
- Reconsider if Playwright routing cannot observe a class of requests the readers issue (for example service-worker or WebSocket traffic). A guarantee stated for every request must then name what it does not see.
