---
tags:
  - '#audit'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-16'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace protected-browser-certificate-auth with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

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

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### {topic} | {level} | {summary}

     followed by a paragraph carrying the detail. {topic} is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

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
at a token-directory JSON filename, while fresh certificate, Cl@ve Móvil, and
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

## Recommendations

Resolve every critical, high, or medium finding before publication. Retain low
findings only when they are explicitly evidenced as non-blocking and do not
reintroduce a parallel authority or compatibility path.
