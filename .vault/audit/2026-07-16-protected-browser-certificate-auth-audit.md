---
tags:
  - '#audit'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-17'
related: []
---

# `protected-browser-certificate-auth` audit: `ADR-to-code hard-cut reconciliation`

## Scope

Audit the accepted protected-browser certificate-auth decision against its
research, the superseded certificate-auth corpus, the implementation and tests,
and the complete branch diff. The review specifically checks that the single
protected Playwright proof remains fail-closed; retired handshake, marker,
backend, configuration, compatibility, and borrowed-session paths are absent;
typed credentials and encrypted persistence remain intact; and browser
ownership has deterministic, retryable teardown.

## Findings

### reset-journal-error-registry | high | Reset journal exceptions cannot import

`ConfigResetJournalError` now derives from `AeatError`, but the error-code
registry has no matching declaration. Import-time subclass binding raises
`ValueError`, breaking the reset repository and reset workflow test modules
before collection. This is a branch-wide publication blocker even though it is
adjacent to, rather than part of, the certificate-auth hard cut.

### architecture-plaintext-storage-fallback | high | Fresh auth can consume an unvalidated plaintext profile session

`BrowserSession.create_context` implicitly loads `Profile.storage_state_path`
whenever the caller supplies neither `storage_state` nor an explicit
`storage_state_path`. The production default factory points that profile field
at a token-directory JSON filename, while fresh certificate, Cl@ve MÃ³vil, and
Cl@ve Permanente authentication call `create_context` without either explicit
storage argument. A leftover or externally created plaintext cookie file can
therefore enter a nominally fresh auth attempt outside the encrypted session
repository, its digest/schema/provider validation, and the `fresh=True`
encrypted-object deletion path. The canonical live protected probe still
prevents this from becoming a second proof authority, but the read-tolerance is
an active plaintext/legacy compatibility path and contradicts the encrypted
storage and hard-cut constraints. Fresh provider calls must explicitly suppress
the profile fallback, or the generic browser boundary must remove it and make
every storage-state source explicit.

### architecture-accepted-adr-conflict | medium | Accepted auth ADRs still prescribe the deleted handshake and marker stack

The accepted `session-persistence`, `aeat-access-gate`,
`auth-provider-abstraction`, and `auth-protocol` ADRs still require one or more
of `HandshakeResult`, `verify_handshake`, persisted handshake fields, context
markers, marker-producing provisioners, configurable verification targets, or
a fresh-handshake fallback. The protected-browser ADR says conflicting clauses
are no longer authoritative, but its formal `supersedes` inventory names only
the three archived certificate-auth ADRs; several contradictory accepted ADRs
do not link back to the new decision and semantic search still returns the
obsolete access-gate prescription prominently. The code correctly deletes the
retired stack, but the active decision corpus does not yet form the single
non-contradictory authority required for maintainers and RAG consumers. Amend
the still-valid decisions to remove the superseded clauses, or explicitly
supersede/archive them where their remaining scope has no independent value.

### architecture-stale-authenticator-contract | low | Authenticator documentation still promises retired marker and implicit-factory behavior

`AeatAuthenticator.authenticate` still documents a missing thumbprint marker
as a failure mode even though marker evidence was deleted, and the constructor
still says an omitted browser-session factory creates a real Playwright session
lazily even though `_resolve_browser_session` raises `AuthConfigurationError`
when no factory is supplied. These comments are not user-facing and do not
change runtime proof behavior, but they describe two contracts the code and
accepted decision explicitly do not provide. Correct them so source-level
maintainer guidance agrees with the hard-cut architecture.

### lifecycle-concurrent-close-barrier | medium | Concurrent close calls can tear down a newly admitted verification

`AeatAuthenticator.close()` sets `_closing`, waits for `_inflight_drained`, and
then reacquires `_lock` for teardown, but concurrent close callers are not
serialized across that whole sequence. The first closer can reset `_closing`
after teardown while a second closer has already passed its drain wait. A new
`verify()` can then register against the reset latch before the second closer
reacquires `_lock`; the second closer tears down the context without waiting for
that new page. `authenticate()` also does not reject the closing latch, so an
authentication started on an otherwise-empty authenticator can complete between
the latch and teardown and return a session that the concurrent closer
immediately invalidates. The existing race coverage exercises one closer and
one verifier only, so it does not defend either interleaving.

### lifecycle-certificate-context-teardown | medium | Certificate context teardown is unbounded and can mask primary failures

`AeatAuthenticator._drop_context()` clears the retained context before directly
awaiting `context.close()`, applies no configured timeout, and catches only
`PlaywrightError` even though `BrowserContextLike.close()` does not narrow its
exception surface. A hung context close prevents the retryable browser-session
close from running at all. A non-Playwright close failure can replace the
original storage-capture exception, leave `_closing` latched during normal
`close()`, and discard the only context reference before cleanup completes. The
Cl@ve providers already use the configured close timeout and suppress secondary
context failures, so the certificate provider is the inconsistent lifecycle
implementation.

### lifecycle-clave-persist-failure-leak | high | Provider persistence failures can orphan an owned Chromium process

Both `ClaveMovilAuthProvider._fresh_login_locked()` and
`ClavePermanenteAuthProvider._fresh_login_locked()` create an owned browser
session and context, capture storage state, and only assign them to provider
fields after encrypted persistence succeeds. Their persistence-error branches
invalidate the partial secure object and re-raise without closing the local
context or browser session. Because the references were never retained on the
provider, the mandatory later `close()` call cannot retry that cleanup. Any
secure-store write or validation failure after a successful login can therefore
leave Chromium running for the process lifetime, contradicting the shared
`AuthProvider.close()` ownership contract and browser-leak decision.

### lifecycle-proof-test-grounding | high | CI does not exercise the authoritative browser proof with real behavior

The certificate proof, exact-resource predicate, persistence fallback, and
close/verify races are primarily asserted through hand-written
`_RecordingBrowserSession`, `_RecordingBrowserContext`, and recording Playwright
implementations in the auth and browser tests. Those implementations reproduce
the expected response and lifecycle logic instead of importing and driving the
real browser boundary. The only end-to-end certificate test uses
`requires_live_enabled()`, which calls `pytest.skip()` during ordinary CI. This
conflicts with the project prohibition on fakes and skips and with the accepted
decision that context construction be exercised through the production browser
boundary; a green default suite therefore does not independently prove that the
sole authentication authority works or that real Chromium is reaped.

### vault-missing-execution-chain | high | Protected-browser implementation has no plan or execution evidence

`vault list plan -f protected-browser-certificate-auth` and the equivalent
execution-record query both return empty inventories even though the accepted
ADR's Implementation section drove deletions and contract changes across auth,
browser, persistence, configuration, tests, and generated documentation. The
older linked `aeat-access-gate` plan cannot provide substitute evidence:
`vault plan status` rejects it with `PlanFrontmatterError`, and its body still
prescribes `HandshakeResult`, `verify_handshake`, the configurable verification
URL, the context marker, and per-call browser and target seams. There is
therefore no mechanically inspectable plan-step-to-exec chain for this hard cut.
Create the current plan and matching execution records, or explicitly record
why each implementation slice is carried by another still-open plan before
claiming this feature complete.

### coverage-stale-generated-doc-cache | medium | Ignored Sphinx output preserves the deleted backend architecture

The ignored `docs/_build` tree remains 1,697,564,740 bytes and contains 2,088
generated files that mention `AEAT_CERTIFICATE_VERIFY_URL`,
`CertificateBackend`, or `_certificate_backends`. Its rendered environment
reference and API index still instruct readers through the deleted handshake
and backend surfaces. The tracked documentation sources contain no such
residue, so this is a stale generated/temp tree rather than an authored-doc
defect. Delete it before publication and regenerate only from the reconciled
tracked sources when a rendered documentation artifact is actually required.

### vault-distribution-harness-inflight-conformance | low | Distribution-harness amendment remains honestly in flight

The accepted `distribution-harness-identity` ADR limits itself to a verification
invariant and explicitly does not authorize the later rename or bilingual-copy
implementation. The distribution-readiness plan carries the corresponding
namespace, bilingual-description, and public-reacquisition work as unchecked
steps `W02.P06.S67`, `W02.P06.S68`, and `W04.P10.S70`. Live plan status reports
24 of 71 steps complete, 33.8 percent completion, and no checked step missing an
execution record. That unrelated WIP is internally coherent and does not claim
capability that the codebase has not implemented; retain it as a separate
in-flight delivery lane.

### reset-journal-error-registry-resolution | low | Reset journal exception registry is complete

The reset journal base and five concrete subclasses now have distinct
application error-code declarations. Import, repository, and reset workflow
verification passes with 34 real tests, Ruff, and Pyright, so the earlier
publication blocker is resolved without reverting to a built-in exception
hierarchy.

### coverage-stale-generated-doc-cache-resolution | low | Stale generated documentation cache was deleted

The ignored `docs/_build` tree was verified inside the workspace and removed.
Tracked documentation sources remain free of the retired certificate backend
and configuration strings; the final documentation gate will rebuild current
output rather than carrying stale generated artifacts.

### final-architecture-clave-session-lifecycle | high | Clave verification is neither active-session-bound nor close-safe

`ClaveMovilAuthProvider.verify()` and
`ClavePermanenteAuthProvider.verify()` read the retained context without the
provider lock, a close-intent barrier, an in-flight registration, or an exact
active-session check. Either provider can therefore validate the cookies in its
owned context while building a successful assertion from an unrelated caller-
supplied `AeatSession`, including another identity or provider detail. A
concurrent `close()` can also acquire the provider lock and close that context
while the public verification page is navigating. The certificate provider now
guards both conditions, but the two Clave implementations still do not satisfy
the shared `AuthProvider.verify()` identity and ownership contract or plan step
`P02.S06`. Route public work and close intent through one shared lifecycle
barrier, keep an internal already-locked probe for resume, and require the exact
retained session before deriving assertion identity.

### final-architecture-access-gate-persistence-drift | medium | Accepted and live surfaces still describe or accept plaintext storage state

The reconciled `aeat-access-gate` ADR still defines
`AeatSession.storage_state_path` as a Playwright JSON location and says it may be
absent when the caller chooses not to persist, while the accepted
`session-persistence` ADR and live session store define that field as the
mandatory logical key of an encrypted current-schema object. The live
`BrowserSessionLike` and `BrowserSession` contracts also retain the explicit
`storage_state_path` filesystem input, with browser tests and Groi live tests
still exercising token-directory JSON, even though production auth resume uses
validated in-memory state loaded from `SecureObjectRepository`. This leaves a
plaintext side-channel and contradictory maintainer authority after the
implicit profile fallback was removed. Reconcile the accepted ADR language and
delete the auth-facing filesystem-state seam and its obsolete live-test callers
unless a separately accepted non-auth use case owns it.

### final-architecture-certificate-byte-binding | high | Recorded certificate identity can differ from the certificate Playwright presents

`load_certificate()` computes the health, thumbprint, subject, and NIF/NIE from
one read of the PKCS#12 file and retains those exact bytes on
`LoadedCertificate`, but `CertificateContextProvisioner` gives Playwright only
`pfxPath` and the passphrase. Playwright therefore performs a second file read
after identity validation. If the path contents change between those reads, the
canonical protected navigation can succeed with certificate B while the
session, assertion, and encrypted metadata claim certificate A. The installed
Playwright boundary accepts direct `pfx` bytes, so the already validated byte
snapshot can be passed to context construction and the dead second-read path
removed. Until the byte source used for proof and the byte source used for
identity are identical, the claimed certificate-bound protected proof is not
complete.

### final-coverage-exact-proof-regression | high | The sole certificate proof lost its fail-closed regression matrix

The hard cut correctly deletes the recording browser implementation, but it
also deletes the only default-suite cases that drove
`AeatAuthenticator._run_login_probe()` through canonical success, non-success
response, wrong path, and wrong host. The remaining credential-gated live test
asserts only the successful canonical result and is skipped when the central
live opt-in is absent. The same deletion removes the public-flow checks for a
failed resumed live probe, stale encrypted-state fallback to fresh
authentication, navigation-error redaction, and successful and failed
`reauthenticate()` delegation. The new encrypted-store matrix proves ten local
metadata refusals before browser resolution, but it does not prove that the
public `authenticate()` path performs the promised single fresh fallback or
that a live-probe refusal deletes the persisted object. These are active
fail-closed branches of the sole authority, not retired compatibility
behavior. Replace the removed recording responses with a credential-free real
HTTP and Playwright boundary that exercises redirects, status classes, and
exact final resources, and retain the external certificate oracle as the
separate AEAT acceptance proof.

### final-coverage-provider-lifecycle-gap | high | Lifecycle helpers pass while provider ownership branches remain unproved

The new real-Playwright lifecycle suite proves that the shared close helpers
time out, retain retryable resources, and eventually reap a driver, and its
barrier tests prove the primitive's close-intent ordering. It does not drive a
certificate or Clave provider through persistence failure, cleanup retry, or
verification racing with close. The changed Clave persistence-error branches
therefore have no test that observes their locally owned context and browser
being closed or retained, while existing Clave choreography still depends on
`_RecordingBrowserSession` and recording page/context implementations. The
public certificate concurrency replacement only calls `close()` on an empty
authenticator, so it cannot detect a context being torn down under an in-flight
probe. This leaves both the new provider wiring and the architecture finding
for Clave close safety outside compliant real-behavior coverage.

### final-coverage-evasion-reaping-resolution | low | Deleted recording browser tests retain their meaningful real-browser guarantees

The deleted recording evasion test and synthetic browser-process counters do
not represent a capability loss. The production factory suite launches real
Playwright, observes `navigator.webdriver` as false through the configured
evasion path, rejects a second live context, exercises a real context creation
failure, verifies explicit-only storage-state loading, and waits for the
Playwright driver to exit across three complete cycles. The focused real suite
completed with 28 passing tests; the broader auth and provider selection
completed with 94 passing tests. Static mock, monkeypatch, and skip/xfail
inventory gates also passed. This resolves evasion and process-reaping
conformance only; it does not resolve the exact-proof or provider-integration
findings above.

### final-vault-active-corpus-retired-backend-authority | high | Three accepted ADRs still mandate the deleted certificate backend architecture

The four auth ADRs amended by this hard cut now agree with the accepted
protected-browser decision, carry `accepted` status, link back to that decision,
and contain no retired handshake, marker, backend-selector, or configurable
probe clauses. The wider active corpus is not yet non-contradictory, however.
The accepted `2026-04-12-status-reader-adr`,
`2026-04-16-aeat-history-fetch-adr`, and
`2026-04-21-live-sync-backend-adr` still prescribe `CertificateBackend` and
implementation beneath the retired `src/aeat` namespace. Exact source search
finds no production `CertificateBackend`, status-reader package, or history
package; only negative configuration tests retain the deleted identifiers.
These accepted records must be reconciled, superseded, or deleted before the
ADR corpus can be called a single active authority.

### final-vault-supersession-and-rag-residue | medium | Supersession metadata is correct but archived poison remains discoverable

The new ADR formally supersedes all three retired certificate-auth ADRs. Each
archived ADR has canonical body status `superseded` and a matching
`superseded_by` value, and the active non-derived graph excludes those archived
nodes while showing the four amended auth ADRs as inbound authorities. The
archived bodies nevertheless retain body wiki-links, repeated stale `src/aeat`
paths, and the deleted handshake, marker, fallback, and backend design.
Semantic search also returned the archived live-cert supersession ADR under its
former active path, proving the resident index had not incorporated the archive
move. Reindexing can remove the stale search location, but the archived poison
still requires an explicit deletion or retention decision.

### final-vault-execution-chain-honesty | medium | The open plan is honest but one execution scaffold has stale scope

The protected-browser plan passes the non-fixing plan check and reports zero of
eight Steps complete. All eight execution records remain empty scaffolds, so
they do not fabricate execution evidence and no Step should be closed. This
resolves the earlier absence-of-chain finding only to the scaffold stage. The
`P01.S01` record names the nonexistent
`src/cadrumo/adapters/outbound/aeat/browser/_session.py`, while the plan row and
current source correctly name
`src/cadrumo/adapters/outbound/aeat/browser/session.py`. Correct that
plan-to-record scope mismatch before the record becomes completion evidence.

### final-vault-user-document-conformance | low | User documentation contains no development metadata or retired auth surface

Exact search across tracked user documentation, the README, and the environment
example finds no wireframe tags, Vaultspec scaffold metadata, retired handshake
or backend identifiers, configurable certificate probe, or deleted backend
module. Wiki-link text in the protected-browser plan and audit is confined to
frontmatter values and machine-owned template comments; authored bodies in the
active protected-browser and four reconciled ADR records contain no body
wiki-links or stale `src/aeat` Python paths.

### final-vault-unrelated-plan-truth | low | The three unrelated delivery lanes remain explicitly in flight

Non-fixing plan status reports the CLI-authority plan at 47 of 254 Steps, the
distribution-readiness plan at 24 of 71 Steps, and the Claude ecosystem plan at
42 of 47 Steps, with no checked Step missing an execution record. The Claude
remainder is still five operator-gated installation and support proofs. The
distribution namespace, bilingual-description, live-client inventory, public
reacquisition, and close-audit Steps remain unchecked. None of these plans
claims completion that the repository or external evidence has not established.

### final-vault-nonfix-check-warnings | low | Structural checks pass but the new internal records retain scaffold annotations

The non-fixing full Vault check exits successfully with clean structure and
frontmatter, but reports 8,902 modified-stamp warnings caused by checkout mtime
recency. Focused non-fixing checks report clean body links and placeholders,
while the protected-browser audit retains three template comment blocks, its
plan retains twelve, and each of its eight empty execution scaffolds retains
five. The plan also has two extra-blank-line markdown warnings. These are
internal Vault annotations rather than user-document metadata, but they remain
mechanical conformance work and must not be described as an all-warning-free
Vault result.

### architecture-accepted-adr-conflict-resolution | low | Active auth decisions now share one protected-browser authority

The accepted session-persistence, access-gate, provider-abstraction, and
auth-protocol ADRs were reconciled against the current application, outbound
auth, browser, access-gate, and encrypted-session boundaries. They now agree on
typed `ActiveCertificateCredentials`, the application-owned `AuthProvider`
protocol with mandatory `close()`, in-memory browser state, bucket-routed
`SecureObjectRepository` persistence, the fixed protected-resource certificate
proof, the `aeat_live` marker, and the
`CADRUMO_LIVE_TESTS_ENABLED=1` pytest opt-in. Retired handshake, marker,
backend-selector, configurable-target, filesystem-state, compatibility, and
live-submit clauses were removed. All four records link to the accepted
protected-browser decision and retain their independent non-certificate scope.

### final-vault-active-corpus-retired-backend-authority-resolution | low | Dead read-backend feature bundles were deleted

Exact source search confirmed there is no production `CertificateBackend`,
status-reader package, history-fetch package, filing-detail-fetch package, or
live-sync backend. The 25 active ADR, research, plan, execution, audit, and
index documents in the four dead feature bundles were deleted rather than
retained as false accepted authority. Surviving frontmatter edges were removed
or repointed to current governing records before deletion.

### final-vault-supersession-and-rag-residue-resolution | low | Named archived certificate-auth bundles were deleted

The three superseded certificate-auth ADRs and the 13 remaining archived
research, plan, execution, and index documents in their `cert-auth` and
`live-cert-auth` bundles were deleted. The accepted protected-browser ADR is
the sole certificate-session proof authority for that named corpus. Historical
audit and snapshot prose elsewhere may still describe retired designs as
evidence; this resolution does not claim that every historical Vault artifact
was purged.

### final-architecture-certificate-byte-binding-resolution | low | Browser provisioning uses the fingerprinted in-memory PKCS#12 bytes

`CertificateContextProvisioner` supplies Playwright's in-memory `pfx` value
from the private bytes retained by `LoadedCertificate`, not `pfxPath`. The
protected-browser ADR and research now state the same-byte identity invariant:
loading, parsing, fingerprinting, recorded session identity, and browser
presentation share one immutable PKCS#12 input, so path replacement cannot
change the presented certificate after validation.

### final-architecture-access-gate-persistence-drift-resolution | low | Session persistence identity is an encrypted secure-object key

The session-persistence and access-gate decisions now match the implementation.
The historically named `storage_state_path` field is a logical,
active-bucket-scoped object identity, not a Playwright JSON destination.
`aeat_auth_session_storage_state_path()` defines that identity,
`SecureObjectRepository` digests it and encrypts the single browser-state plus
metadata envelope, and `BrowserSession.create_context()` receives only the
validated in-memory storage-state mapping.

### final-vault-execution-chain-honesty-resolution | low | P01.S01 scope now names the live browser session module

The `P01.S01` execution scaffold was corrected through the canonical body
mutator to name `src/cadrumo/adapters/outbound/aeat/browser/session.py`, matching
the open plan Step and current source. The scaffold remains unpopulated and the
Step remains open; this correction records no fabricated completion evidence.

### final-architecture-clave-session-lifecycle-resolution | low | Both Clave providers enforce exact ownership behind the shared close-intent barrier

`ClaveMovilAuthProvider` and `ClavePermanenteAuthProvider` now route public
authentication, verification, and teardown through `_CloseIntentBarrier`.
Verification accepts only the exact retained `AeatSession` object with the
provider's matching kind and detail type before any navigation can begin, while
`close()` waits for the provider work lease and cannot tear down a context under
an in-flight probe. Resume establishes `_active_session` before invoking the
internal already-leased verifier. The real provider lifecycle matrix passes for
certificate, Cl@ve Movil, and Cl@ve Permanente copied-session refusal,
wrong-provider refusal, and close-waits-inflight behavior.

### final-coverage-exact-proof-regression-resolution | low | Real HTTP and Playwright tests cover every sole-proof outcome

The credential-free real-browser boundary now drives canonical success,
non-success response, wrong host, wrong path, navigation failure, stale
encrypted-state replacement, failed-resume deletion before one fresh fallback,
reauthentication, and cancellation cleanup through production imports. The
focused exact-resource and navigation-redaction matrix passes five cases; the
external credential-gated oracle remains a separate AEAT acceptance proof.

### final-coverage-provider-lifecycle-gap-resolution | low | Public provider lifecycle races are exercised with real browser resources

The real lifecycle suite instantiates each production provider around a real
Playwright context and local HTTP boundary. Three exact-session refusal cases
and three concurrent verify/close cases pass, demonstrating that provider
ownership checks and the shared close-intent barrier are integrated rather than
proved only as isolated helpers.

### final-architecture-serialized-proof-url-redaction | low | Raw proof validation is separated from safe assertion serialization

Certificate proof compares the raw observed URL's exact scheme, netloc, and
path with the canonical protected resource. Only after that decision does it
construct the assertion URL, with query and fragment removed. The real redirect
test confirms its sensitive query value is absent from both assertion JSON and
captured logs without weakening wrong-host or wrong-path refusal.

### final-architecture-route-witnessed-auth-projection | low | Operator auth consumers share one pinned provider and credential snapshot

Application auth now obtains workflow state, selected provider, and typed
certificate credentials through one `ActiveAuthProjectionSnapshot` held inside
`active_auth_projection_span`. State projection, status testing, preflight, and
login consume that witnessed snapshot instead of reopening provider or
credential authority after an active-profile pointer change. Focused integration
tests pass for pointer changes across two encrypted buckets and for cold-root
certificate settings before the no-active-bucket refusal.

### final-test-conformance-clave-recording-harnesses | high | Executable Clave tests still rely on prohibited synthetic browser implementations

The new credential-free HTTP and Playwright boundary closes the deleted
certificate proof matrix: exact success, unsuccessful response, wrong host,
wrong path, navigation redaction, stale-state replacement, failed-resume
invalidation, reauthentication, cancellation reaping, copied-session refusal,
and close-versus-verification are now exercised through production browser and
provider surfaces. The browser-profile hard cut is likewise protected by real
in-memory cookie roundtrip and real process teardown tests. However,
`_clave_movil_support.py` and `_clave_permanente_support.py` still implement
hand-written recording pages, responses, contexts, and browser sessions, and
the executable Clave test modules still import and drive those implementations.
That directly violates the repository rule forbidding fakes, mocks, stubs, and
recording substitutes, and means the auth test surface is not publication-ready
despite the new decisive-proof coverage. Replace each remaining protocol case
with a real local HTTP plus Playwright scenario, or delete cases whose only
assertion mirrors provider business logic, before closing the real-behavior
testing step.

### final-vault-residual-authority-reconciliation-resolution | low | Named setup-wizard, self-healing-sync, and generated-snapshot authority was removed

The superseded setup-wizard and self-healing-sync features had no production
implementation matching their accepted ADRs. Their 20 ADR, research, plan,
audit, execution, and index documents were deleted after all 14 incoming
frontmatter edges were removed. The generated June ADR state snapshot and its
index were also deleted after its one incoming plan edge was removed; git
history remains the appropriate source for that dated inventory.

The accepted browser-leak ADR now describes the live single-browser ownership,
serialized retryable closure, and provider close-intent contracts. The accepted
AEAT-verify ADR now names the sole `adapters.outbound.aeat.sede` transport,
`application.live` orchestration, typed auth-provider session, and encrypted
secure-evidence boundaries. Workflow and mantenimiento decisions now use the
live Sede callables and browser-owned site-health taxonomy rather than a
status-reader or sync-runner compatibility seam. The protected-browser ADR no
longer carries resident supersession edges to physically deleted certificate
ADRs; the rejected stack is identified only as deleted history available in
git. This resolution is limited to the bundles and edges named in this section;
it is not a corpus-wide claim that every unrelated historical record is free of
retired terminology.

### final-test-conformance-clave-recording-harnesses-resolution | low | Clave contracts now use production code and real browser resources

The hand-written Cl@ve recording pages, contexts, browser sessions, response
objects, and event journals were deleted from both shared test-support modules.
The representation-shape choreography test was deleted rather than preserving
a duplicate implementation of provider logic. Remaining policy,
configuration, identity, redaction, health, verification-refusal, and operator
diagnostic cases call production providers directly.

Credential-free lifecycle coverage now drives public Cl@ve Móvil and Cl@ve
Permanente authentication and verification through real Playwright contexts
and a real local HTTP server. It proves pending-petition classification,
own-name-only representation continuation, encrypted browser-state
persistence, invalid-credential classification, exact active-session
ownership, and close-versus-verification serialization without a synthetic
browser implementation. The focused production-direct Cl@ve matrix passes 30
cases, and all four new real-boundary Cl@ve cases pass.

### final-vault-linked-auth-bundle-curation-resolution | low | Named stale auth delivery bundles no longer form active authority

The accepted session-persistence, access-gate, provider-abstraction, and
auth-protocol ADRs now link to the current protected-browser research instead
of their retired research or review records. After their unique rationale was
distilled into those current decisions, 23 stale documents were deleted: the
complete six-document `test-clave-movil-mark-fix` bundle and the obsolete
research, review, plan, execution, and portal-reference records attached to the
four retained ADRs. Their four feature indexes were regenerated from the
surviving current ADRs.

The provider ADR now states the durable warning from the deleted marker-fix
bundle: protocol-shaped local choreography, especially a handwritten browser
substitute, is not live authentication proof. It also retains the live Cl@ve
observations that selector reachability is insufficient, the authenticated
landing URL is observed rather than assumed, and Cl@ve Móvil requires phone
approval. This resolution is scoped to those named bundles. The RAG service was
not rebuilt during this curation pass, so a previously built index may retain
stale chunks until its next separately authorised rebuild.

### final-architecture-password-materialisation-boundaries-resolution | low | Certificate passwords cross exactly two necessary logical boundaries

The protected-browser ADR and research now match the certificate implementation:
`SecretStr` is materialised for PKCS#12 decode and for Playwright browser-context
construction. Those are the two necessary credential-use boundaries; the
password is not logged, persisted, added to session evidence, or promoted into
another architecture seam.

### final-vault-second-pass-run-trace-conformance | high | One accepted ADR remains stale and the second pass damaged ADR text encoding

The dead certificate, status-reader, history-fetch, filing-detail-fetch,
live-sync, setup-wizard, and self-healing-sync ADR paths are absent; no current
ADR supersession edge resolves to them. Browser-leak, AEAT-verify, workflow,
mantenimiento, and notifications now describe the surviving Cadrumo/Sede
boundaries, semantic search no longer returns the deleted ADR paths themselves,
user-document poison searches are empty, and the protected-browser plan remains
honestly open at 0/8 with no missing execution records.

Publication is nevertheless blocked. The accepted run-trace ADR still names
`src/aeat/core/observability`, `aeat.core.observability`,
`aeat.core.logging`, `aeat.core.errors`, and `Settings.aeat_runs_dir`; the
implementation uses `src/cadrumo/core/observability`, the `cadrumo` import
surface, and `Settings.cadrumo_runs_dir`. The second-pass diffs also introduce
mojibake such as `â€”`, `Ã³`, and `â†’` throughout the modified workflow,
notifications, and run-trace ADRs. Reconcile the remaining accepted ADR names
and restore UTF-8 text before publication; do not mark the protected plan or
this reconciliation complete until both checks are exact-clean.

### final-vault-second-pass-run-trace-conformance-resolution | low | Run-trace authority and active ADR encoding match current source

The accepted run-trace ADR now binds trace capture, retention, and replay to
`src/cadrumo/core/observability`, the `cadrumo.*` import surface,
`Settings.cadrumo_runs_dir`, and `Settings.cadrumo_runs_retention_days`. It no
longer presents the retired `src/aeat`, `aeat.*`, or `aeat_runs_dir` names as
current authority. An exact active-ADR inventory also repaired every remaining
mojibake sequence, including the pre-existing code-duplication ADR text. The
protected plan and execution records remain open and unpopulated.

### final-vault-generated-index-and-dangling-resolution | low | Deleted auth poison no longer remains in generated or audit edges

The generated `aeat-auth-providers` index now retains only the existing
auth-provider ADR. It no longer links or lists the deleted provider research or
the independently retired Cl@ve portal reference. The continuous-review audit
now relates only to the existing auth-protocol ADR; its absent plan and review
audit edges were removed. Focused reference, dangling, and body-link checks are
clean, while the protected plan and execution records remain open and
unpopulated.

### architecture-plaintext-storage-fallback-resolution | low | Fresh authentication has no implicit plaintext storage-state source

`BrowserSession.create_context()` now accepts only an explicit in-memory
`storage_state` mapping and a provisioner. The `storage_state_path` parameter and
the `Profile.storage_state_path` fallback are gone, so no caller can reach a
plaintext cookie file by omitting an argument. `_build_context_kwargs()` sets
`storage_state` only when the caller passed one, and `_storage_state_source()`
reports `inline` or `none` — there is no third source to report. Exact search
finds no remaining `storage_state_path` filesystem input on the browser
boundary; every surviving use of that identifier is the logical encrypted
secure-object key described by the sibling persistence-drift resolution.

### lifecycle-clave-persist-failure-leak-resolution | low | Both Clave persistence-failure branches close their locally owned resources

`ClaveMovilAuthProvider._persist_fresh_session()` and the matching
`ClavePermanenteAuthProvider` helper wrap metadata construction and the
encrypted save in one `try`. The failure branch invalidates the partial secure
object inside its own suppressed `try` so a secondary cleanup fault cannot mask
the persist exception, then closes the local context and browser session through
the shared bounded helpers and re-raises. Each helper's boolean result decides
whether the provider retains the reference, so a close that times out stays
retryable through the mandatory later `close()` instead of orphaning Chromium.

### lifecycle-certificate-context-teardown-resolution | low | Certificate teardown is bounded, retryable, and non-masking

`AeatAuthenticator._drop_context()` and `_teardown_failed_attempt()` route
through `close_owned_browser_context()` and `close_owned_browser_session()` in
the shared lifecycle module. Both apply `cadrumo_browser_close_timeout_ms` via
`asyncio.wait_for`, catch the broad exception surface rather than only the
Playwright error type, log, and return a boolean instead of raising — so a hung
or non-Playwright close can neither block the browser-session close nor replace
the original storage-capture exception. The context reference is cleared only
when the close actually completed, so a failed teardown remains retryable. The
certificate provider and the two Clave providers now share one implementation.

### lifecycle-concurrent-close-barrier-resolution | low | One barrier serializes closers and bars newly admitted work

`_CloseIntentBarrier` replaces the ad-hoc `_closing` flag and drain latch. Close
callers are counted under a state lock and hold a gate for the whole teardown
sequence, so a second closer cannot pass while the first is still tearing down,
and the no-close-intent event is set only when the last closer exits. `work()`
waits for that event and re-checks the closing predicate after acquiring the
gate, so a probe cannot register against a momentarily reset latch. All three
providers construct the barrier and route public authentication, verification,
and teardown through it, which also closes the separate Clave ownership finding.

### final-gate-repository-wide-conformance | medium | Owner-distinguished gate run: the campaign surface is green, three peer campaigns are red

The repository-wide gate pass for this feature ran on 2026-07-24. Green:
pytest collection across the whole product tree (13,508 tests collected, zero
collection errors); the focused campaign suite for the outbound auth and browser
trees (208 passed, no skips, no live-marked cases selected); repository-wide
`ruff check` after this pass repaired it; `ruff format --check` and `ruff check`
scoped to the 146 files of the outbound AEAT adapter tree; the registry verify
command across all 73 modelos; the non-fixing full Vault check; and the
test-framework ratchets for discovery, markers, skip/xfail, mock, monkeypatch,
broad raises, bare except, and tautology drift.

Red, and owned elsewhere. The layered-architecture import contract is broken by
three edges from `cadrumo.application.user_profile._login_session` into
`cadrumo.adapters.persistence.storage`, one of them into the private `_zeroise`
submodule. Type checking reports 199 diagnostics, of which 194 sit in
`src/cadrumo/core/tests/test_session_absolute_minutes_setting.py`, one in
`_login_session.py`, and four `unresolved-attribute` in
`src/cadrumo/domain/calculations/registry/_queries.py`. The generated API
reference has drifted by one missing stub for `_login_session` and one stale
parent. A source-hygiene ratchet fails on a docstring in
`src/cadrumo/domain/user_profile/tests/test_portable_export_schema.py:82` that
names a plan Step identifier. Every one of these signatures was introduced by a
live peer campaign — profile login-session and the roundtrip-hardening lane —
and none touches the certificate-auth surface. They were reported to their
owners rather than patched, per the rule against editing an active peer
campaign's files to make a closeout gate pass.

This feature therefore cannot claim the plan's unqualified "full pytest, style,
format, type, import, registry, documentation, Vault, and GitHub CI gates pass"
sentence at close. The honest claim is narrower and is the one recorded here.

### final-gate-format-and-packaging-scope | low | Two named gates are out of this feature's reach and are recorded rather than claimed

`ruff format --check` reports 54 files repository-wide that would be
reformatted, spanning archived and active Vault markdown and eight unrelated
source and tooling modules, including one that is the live surface of an active
peer campaign. None is in the outbound AEAT adapter tree, which is fully
formatted. The drift is a consequence of the ruff 0.16.0 lock bump rather than
any campaign's authorship, and reformatting it would rewrite peer files for no
correctness gain, so it is left to a repository-wide mechanical pass. The format
gate is also absent from the per-push CI static job, which runs style, relative
imports, import architecture, and types.

The packaging smoke lanes and the semgrep regression rules were not run. The
packaging lanes build release cohorts and live in separate dispatch-gated
workflows, not the per-push wall; semgrep requires the Unix `resource` module
and cannot execute on this workstation. Neither is claimed as passing.

### final-gate-workstation-environment-staleness | medium | A missing core dependency had silently disabled the modelo CLI and the whole documentation gate

The nitpicky Sphinx build failed at the CLI-reference generator with an
import-failure fallback detected across the `aeat app modelo` subtree. The cause
was environmental, not architectural: `textual` became a core project dependency
on 2026-07-23 and the shared workstation environment was never re-synced, so
`cadrumo.adapters.inbound.tui` could not import and the modelo command group
degraded to the localized unavailable-command placeholder. Because every gate in
this worktree runs with `--no-sync`, the degradation was invisible to any
command that did not exercise the modelo tree, and it had been present for a
day. The exact locked version was installed and the subtree recovered its 23
subcommands. Two lessons are recorded rather than codified: an import-failure
fallback that presents as ordinary help text hides a hard dependency failure
behind a polite refusal, and a `--no-sync` gate discipline needs a dependency
freshness check to stay honest.

### final-gate-runner-encoding-defect-resolution | low | The quiet gate runner reported a fabricated failure on a narrow console

`dev/quality/quiet.py` ran every wrapped gate with `text=True` and no explicit
encoding, so the subprocess reader thread decoded tool output with the Windows
locale codepage and raised on the first UTF-8 byte. The captured stdout was then
`None` and the replay itself raised a `TypeError`, so `just check-format`
reported a failure caused entirely by the harness, with no drift list attached.
The encode side had the mirror fault. The runner now decodes UTF-8 with
replacement and writes the failure replay through the byte buffer when the
console encoding is narrower, so a wrapped gate reports the tool's real verdict.
This was found by running the gates this Step mandates and is repaired here
because the defect made one of them unrunnable rather than merely red.

### final-honesty-verify-package-close-typeguard | low | The remaining duck-typed close is a fail-closed assertion, not a compatibility path

A fresh reader sweeping for the decision's "every `getattr(..., "close", None)`
compatibility path are deleted" clause will find one surviving occurrence at
`src/cadrumo/adapters/outbound/aeat/verify/__init__.py:156`. It is examined and
cleared: `_is_verify_browser_session_like` is a `TypeGuard` narrowing helper that
requires both `create_context` and `close` to be present, and
`_build_default_browser_session` raises `_BrowserAdapterTypeError` when the guard
fails. It tolerates nothing and calls nothing optionally, so it upholds the
mandatory-close contract rather than weakening it. It is recorded so the next
sweep does not re-open it.

### final-honesty-live-oracle-scope | low | The external oracle is exact and fail-closed but never runs by default, by design

`test_authenticator_live.py` asserts that both the assertion target URL and the
observed final URL equal the canonical protected-resource constant, that the
response succeeded, and that the parsed identity matches the session identity.
After live opt-in, absent certificate configuration fails the test rather than
skipping it. The module carries the live marker, so the default suite deselects
it and no default run exercises real AEAT. That is the intended safety posture,
not a coverage gap: the credential-free real HTTP and Playwright boundary is what
proves the predicate in CI, and the oracle is the separate AEAT acceptance proof.
The feature performs no submission; it builds, validates, verifies, and exports
only.

### final-honesty-ratchet-scan-file-race | low | One ratchet error was concurrent peer file churn, not a defect

A first ratchet run reported six errors rooted in a `FileNotFoundError` for
`src/cadrumo/application/wizard/tests/test_monoparental_reduccion.py`. That path
is neither tracked nor present, and an immediate re-run was clean, so a peer
agent deleted the file between the marker gate's tree walk and its read. The
underlying robustness gap is real but small: the gate's per-path read assumes the
tree is stable for the duration of a scan, which is not true in this shared
worktree. No change was made; the observation is recorded for whoever next
triages an unreproducible ratchet error.

### final-gate-documentation-build-disposition | low | The documentation gate clears this feature and stops on a peer-owned golden

Once the missing core dependency was installed, the nitpicky Sphinx build got
past the CLI-reference generator that had been blocking it and ran to the
sequence-golden comparison, where it reported one divergence: a debug log line
from `src/cadrumo/domain/deadlines/_engine.py:191` appearing in a captured
modelo-readiness frame. The committed goldens under `docs/_sequences` were being
regenerated by another lane during this run — roughly fifty of them were
uncommitted when this Step began and had landed by the time it ended — so the
comparison raced a moving target. The documented repair is a golden refresh,
which would rewrite that lane's files, so it was not run here.

Nothing in this divergence touches certificate authentication. The build's
feature-relevant surfaces are clean: the API stubs for the outbound auth and
browser modules resolve, no cross-reference in this feature's documentation is
unresolved, and the campaign's own Vault documents pass the structural, body-link,
placeholder, and encoding checks. The gate is recorded as owner-distinguished
rather than claimed.

Two operational observations came out of the same run. The build exceeds the
suite's 300-second per-test ceiling when run serially on a contended workstation,
so a serial invocation reports a timeout rather than a verdict; and a parallel
invocation lost two xdist workers to abrupt termination. Neither is a docs
defect, but both make this gate unreliable to run locally while many agents share
the machine.

## Recommendations

Resolve every critical, high, or medium finding before publication. Retain low
findings only when they are explicitly evidenced as non-blocking and do not
reintroduce a parallel authority or compatibility path.

The certificate-auth surface itself is clear. The two medium findings that
remain open at this close are not owned by this feature: the repository-wide
conformance finding is a set of peer-campaign regressions reported to their
owners, and the environment-staleness finding is a workstation condition already
repaired. Publication of this feature is not blocked by either, but a
repository-wide green claim is, until the peer lanes land their fixes.
