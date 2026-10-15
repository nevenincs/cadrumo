---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-14'
body_schema: 'body-v2'
body_hash: 'sha256:c7f5240f792ad84eaf87b9c31744819112a2ca9baad3c6476bdbe737e9b49414'
related:
  - "[[2026-10-10-mcp-parity-sign-in-doors-reference]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-options-research]]"
  - "[[2026-10-10-mcp-parity-admitted-surface-defects-reference]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
  - "[[2026-10-04-application-sign-in-adr]]"
---

# `mcp-parity` adr: `The MCP server resumes the shared sign-in exactly as the command line and terminal interface do, with the enrolled key as the single exception` | (**status:** `accepted`)

## Problem Statement

Cadrumo's MCP server can authenticate only with an enrolled key. A session made from that
key is independent of the person's login by design: it keeps working after the person
signs out or their session times out. The owner requires the opposite for MCP used inside
Cadrumo: no access to user data unless the runtime is up and a valid user session is
signed in, and no divergence from how the command line and terminal interface check that.
A decision is needed on which login the MCP server uses, because every later choice about
what an agent may call depends on what kind of session stands behind the call.

Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository, a separate project that drives this application through its MCP server; they are cited by name and are not in this vault.

## Considerations

Code facts are in `2026-10-10-mcp-parity-sign-in-doors-reference`.

- No surface keeps login state. The command line and the terminal interface each ask the
  runtime to log in for one exact profile, by resuming the shared sign-in, by password or
  by key.
- The runtime refuses the shared sign-in and the password from the MCP frontend, and the
  MCP adapter requires an automation grant. That one gate is the divergence.
- A key session survives sign-out and time-out; only an operating-system lock and a
  profile-wide lock stop it.
- A session descended from the person's sign-in by delegation is defined in Cadrumo's
  accepted access record, and cannot be created or refreshed in the code as it stands.
- A session made from the shared sign-in holds every operation and action with no grant
  to narrow it, and the human gate checks only the kind of session.
- The desktop shell already offers its sign-in dialog from polled sign-in state, about two
  seconds after a change. No component can ask it to.
- The owner, first-hand on 2026-10-10:
  - "MCP must always be coupled with the user login state - if user A is logged in and
    the session isn't timed out the MCP should be able to access user data. If the
    logged-in user session has timed out, the MCP access inside Cadrumo must prompt a
    login."
  - "Completely fine to have a state based login. No need to change architecture."
  - "Timeout like sign-out is correct. Backend should return no conversations when
    there's no signed in active user."
  - "There should be no divergence from their implementation - or the implementation
    should be evolved in tandem. None should be able to operate unless runtime is
    running, available and authed, and valid user session logged in and authed. The only
    exception is long-lived API key we can issue against a profile."
  - "I confirm MCP should resume the shared sign-in like CLI and TUI."
- The owner confirmed the same first-hand in another session: "Yes, the same sign-in"
  (`2026-10-10-cadrumo-integration-owner-rulings-research`).
- The runtime's handlers for signing the person out and for locking another session check
  the kind of session and not the frontend, so a client holding the person's own session
  can do both.

## Considered options

- **Enrolled key only, as today.** Rejected by the owner's rule: it works with nobody
  signed in.
- **A status check in the MCP adapter on top of the key.** Smallest change. Rejected: it
  is a second, MCP-only mechanism, and the adapter would enforce what the runtime should.
- **A delegated child of the person's session.** It keeps Cadrumo's accepted access
  record and lets a narrower scope be given to the agent. Not chosen: it does not exist
  in code and is a mechanism the other two surfaces do not use.
- **Resume the shared sign-in, as the command line and terminal interface do.** Chosen,
  and confirmed by the owner.

## Constraints

Binding:

- Inside Cadrumo the MCP server logs in by resuming the shared sign-in for the exact
  profile: the same request the command line and the terminal interface make. It never
  signs in by password or by a key named in a tool call, and no secret travels through
  MCP. (Amended 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`. Earlier
  that day, under `2026-10-11-mcp-parity-full-parity-adr`, it could also sign in by
  password carried as a typed secret; before that it never logged in by password.)
- The runtime decides, not the adapter. With no valid signed-in session for the profile,
  no MCP call reaches user data.
- The server answers initialization, the tool list and `status` with no session and no
  profile, and resumes the sign-in when any other call arrives. With no live sign-in to
  resume and no configured key, it refuses that call with a typed result telling the
  person to sign in to Cadrumo. A client can therefore
  read the tool list while nobody is signed in, which keeps the accepted access
  record's rule that a client connects without an unlocked profile
  (`.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:82`, `:130`).
  (Amended 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`; before that public
  queries were also answered with no session.)
- When the MCP server is run for an assistant that Cadrumo hosts, the profile is bound by
  the Cadrumo process that runs the server, never by an argument the client's launch line
  supplies. A launch argument naming the profile remains only for the key exception.
- A time-out is handled like a sign-out. The session ends, calls are refused with the
  existing refusal shape, and nothing of the MCP server's access is kept alive across it.
  The same holds when the MCP session's own lease lapses: the agent never renews it by
  authenticating, and a later call is admitted only by resuming a sign-in the person
  holds at that moment (amended 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`).
- The MCP server is bound to one profile for its life: the profile of its key, or of the
  sign-in it first resumes. If the signed-in profile later differs, every call is
  refused. It serves no installation acts and no act outside that profile (added
  2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`).
- The sign-in prompt stays state-based: the desktop shell's existing dialog. No signal by
  which another component requests the dialog is designed.
- The enrolled long-lived key issued against a profile remains, as the single exception.
  It authenticates without a signed-in person. The person issues it and configures it,
  by reference, in the server's launch configuration; no tool call presents or names it
  (amended 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`).
- Because a sign-in session has no grant to narrow it, what limits an MCP client beyond
  what limits the command line is only the named surface the person chose to serve that
  client; the default surface is every operation inside the bound profile, and
  authentication, session administration and acts outside the profile are not on any
  MCP surface (amended again 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`;
  before that the default surface was everything). (Amended 2026-10-12 under
  `2026-10-11-mcp-parity-full-parity-adr`; before that a per-operation admission list
  also limited it, and an operation with a human-only policy admitted the MCP frontend
  only behind the person's approval of the exact act, under the superseded
  `2026-10-10-mcp-parity-admission-rulings-adr`.)
- Activity by an MCP client does not extend the person's idle deadline. Cadrumo's accepted
  record says agent activity never prolongs the human sign-in; that property is kept when
  the MCP session becomes a sign-in session. Today nothing extends that deadline for
  anyone. The accepted sign-in record plans an extension on a submission, from a
  human-kind session, of an operation declared interactive
  (`.vault/adr/2026-10-04-application-sign-in-adr.md:97`). That rule is keyed on the kind
  of session alone, so when it is built it excludes the MCP frontend.

To confirm with the owner: the owner's words were that the key authenticates "without the
runtime and status". The key works without a signed-in person, but today it still goes
through the runtime, which is the only process that unlocks a profile under Cadrumo's
accepted record. This record reads the statement as "without a signed-in person" and
leaves the runtime in the path. On 2026-10-10 the owner confirmed the first half: the key
operates and opens a profile directly, without a logged-in person. Whether the runtime
stays in the path is not yet confirmed.

Affected prior rulings, each needing an amendment the owner approves: the accepted
profile-access record, which says automatic resume is for interactive surfaces and that
agents authenticate with enrolled keys or explicit delegation
(`.vault/adr/2026-09-26-mcp-purpose-authentication-profile-access-adr.md:203`); and the
accepted application sign-in record, which makes resume a default of interactive surfaces
(`.vault/adr/2026-10-04-application-sign-in-adr.md:91-93`). The proposed wording is
listed under Consequences. In code, the runtime gate that refuses the shared sign-in from
the MCP frontend changes.

Hypotheses: the MCP adapter gains a resume path and a way to start without a credential
reference; lifecycle notices are extended to the MCP frontend so the client hears of a
session ending; which Cadrumo process starts the MCP server for an agent; and that a
session of the human kind on the MCP frontend identifies an MCP client acting under the
person's sign-in, since a key session is a different kind, so the runtime can key the
sign-out and lock rulings on that pair without a new identity. The pair does not identify
the hosted assistant. An editor's MCP client that resumes the sign-in is the same pair,
and the frontend is declared by the client
(`.vault/adr/2026-10-04-application-sign-in-adr.md:93`), so a same-account process that
declares the command line is not caught by it. (Amended again 2026-10-12 under
`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`: MCP serves no sign-out and no lock at all, so
no ruling is keyed on that pair for them. Earlier that day, under
`2026-10-11-mcp-parity-full-parity-adr`: the sign-out and lock rulings were no longer keyed
on that pair, and the refusal of reserved operations to the hosted assistant, keyed on
its process tree, and the approval step that was to carry that fact through the relay are
withdrawn. The process tree still matters only for telling the assistant's own activity
apart from the person's, under the idle-deadline ruling recorded below.)

## Implementation

We will admit Cadrumo's MCP frontend to the shared sign-in resume, so that the MCP server
used inside Cadrumo holds the person's own session and loses it when the person signs out
or times out.

- The runtime accepts the resume method from the MCP frontend and refuses the password
  method there. (Amended 2026-10-12 under `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`. Earlier
  that day, under `2026-10-11-mcp-parity-full-parity-adr`, the password method was accepted
  there too; before that it stayed refused there.)
- The adapter resumes the sign-in when it has no credential reference, and reports the
  runtime's refusal unchanged when there is none to resume. For an assistant that Cadrumo
  hosts, the process that resumes and holds the session is the Cadrumo process serving
  the surface, not a client process started for one turn.
- The key exception is served from the launch configuration alone. The four enrollment
  and authentication tools are withdrawn from MCP, subject to the owner's confirmation of
  the enrollment flow recorded in `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`. (Amended 2026-10-12;
  before that they kept serving the key exception.)

## Rationale

The owner's rule is that every surface follows one login state and that implementations
evolve together. The command line and terminal interface already share one mechanism, held
by the runtime; using it for MCP removes the divergence at its single gate instead of
adding a parallel one.

## Consequences

- MCP inside Cadrumo works only while the person is signed in, and stops when they are
  not.
- The grant approval step disappears for in-app use. What it gave, a scope the person
  approved and a consent to disclose to an agent host, has to come from the surface the
  person chooses when starting the server and from a consent given elsewhere.
- Sensitive operations are reachable on MCP with no approval step. Their safeguards are
  the ones inside the operations, the same on every frontend. (Amended 2026-10-12 under
  `2026-10-11-mcp-parity-full-parity-adr`; before that guarding or closing them on MCP
  came first.)
- The session does not last longer by itself, and today it cannot be renewed. A sign-in
  session's expiry is fixed when it is admitted, at the sooner of the sign-in's idle and
  absolute deadlines, and refresh exists only for a root key session
  (`src/cadrumo_runtime/application/session_authority_admission.py:346`, `:371`,
  `:453-454`). The stored sign-in ends at the same instant, because nothing extends it
  after the password login that minted it
  (`2026-10-10-mcp-parity-sign-in-doors-reference`, section 14). At that idle deadline,
  15 minutes by default, the sign-in is over for every surface, the MCP server's session
  with it, and only a new password sign-in creates another. Starting an operation,
  delivering its secret and answering its review stay with the session that began them
  (`src/cadrumo_runtime/host/operation_host.py:315-317`, `:372-388`, `:517-532`),
  so an operation, its review and any approval of it settle within one sign-in. The key
  route's short lease is lengthened, not removed.
- A useful MCP session inside Cadrumo therefore depends on the lifetime work of the
  accepted sign-in record: the idle extension, with the receipt-sealing key held in the
  profile worker's memory beside the session's DEK only while a live session exists
  (`2026-10-04-application-sign-in-adr`, **Lifetime**). (Amended 2026-10-12 on the
  owner's ruling "i followw your recommedation"; before that where the sealing key lives
  was a named follow-on decision still to be made.) Until that is built, an
  agent run ends no later than the idle deadline counted from the password sign-in. When
  it is built, two things are settled with it: whether a live MCP session is re-clipped
  to the extended deadline or resumes a new session, and what becomes of an operation
  begun on the old one.
- Ruled by the owner on 2026-10-10, in the session that holds the integration records,
  and relayed here verbatim: the owner chose "Each message you send to the assistant
  counts as your activity; the assistant's own calls, commands and scripts do not. You
  stay signed in while present and typing. An answer that takes longer than the idle
  window after your last message is still cut." It is recorded there in the accepted
  `2026-10-10-cadrumo-integration-sign-in-deadline-adr`. Two things follow for Cadrumo
  once the extension is built: a message the person sends to the assistant reaches the
  runtime as that person's activity, and the assistant's own calls are told apart from
  the person's by more than the kind of session or the frontend.
- The question that ruling answered: what counts as the person's activity while they work only
  with a hosted assistant. Under the accepted rule only an interactive submission extends
  the sign-in, and under this record an MCP client's calls never do, so a person who
  talks to the assistant for longer than the idle deadline is signed out in the middle of
  the conversation. Excluding the MCP frontend does not reach the assistant's terminal:
  its commands declare the command-line frontend under the person's sign-in, so their
  interactive submissions would extend it. If the ruling is that the assistant's work
  does not count, the exclusion is keyed on the assistant's process tree as well.
- Two accepted records are amended. Amendments required once this record is accepted:
  - `2026-09-26-mcp-purpose-authentication-profile-access-adr`, line 203. "Automatic
    resume defaults to interactive surfaces. That is a client-side default, not an
    authority control: agents authenticate with enrolled API keys or explicit attended
    delegation" becomes "Automatic resume defaults to interactive surfaces and to the MCP
    server when it holds no enrolled credential reference
    (`2026-10-10-mcp-parity-shared-sign-in-door-adr`). That is a client-side default, not
    an authority control. With no signed-in person an agent authenticates with an
    enrolled API key. Attended delegation remains defined and is not used by the MCP
    server."
  - The same record's capability matrix gains a row: activity "MCP server without an
    enrolled key"; required authority "Resume of a bounded valid human receipt for the
    exact profile; never a password"; what it establishes "A human-kind session that ends
    with the sign-in, limited by per-operation MCP admission and the served surface".
  - The same record, enrollment step 1 (line 82). "Requesting private work without a
    matching key returns an authorization-required result" becomes "Requesting private
    work with neither a matching key nor a live sign-in to resume returns an
    authorization-required result".
  - The same record, line 138. "polling and API activity never prolong human login" gains
    "and neither does any submission on the MCP frontend". Its rejected option at line 36
    stands: the human login is not extended, and an MCP session ends with it.
  - `2026-10-04-application-sign-in-adr`, automatic reuse (line 91), gains "The MCP
    server resumes a live sign-in when it holds no enrolled credential reference. It
    never authenticates by password."
  - The same record, lifetime (line 97). "an operation submission from a human-kind
    session whose operation definition is declared interactive" becomes "an operation
    submission, on the terminal interface or the command line, from a human-kind session
    whose operation definition is declared interactive. A submission on the MCP frontend
    never extends it."
  - The same record, lines 62 and 248. "keeps non-interactive clients on API keys" and
    "which steers agents toward API keys" each gain "except the MCP server, which
    resumes the sign-in under `2026-10-10-mcp-parity-shared-sign-in-door-adr`".
  - The same record, the 2026-10-09 amendment (line 198). "Passwords, receipts and
    approved exact-profile MCP grants remain required" becomes "Passwords, receipts and
    enrolled keys remain required; an MCP connection presents a receipt proof or an
    approved exact-profile grant".
  - The same record, sign-out (line 109), "A human-kind session, or a presented proof,
    may request it", is worded with the owner's ruling on whether an MCP client may sign
    the person out. Its line 29 records the operator's choice of 2026-10-04 and stays as
    history; the amendment is dated and cites the ruling of 2026-10-10.
- Traced since, with locators in section 14 of the reference:
  - The worker's slide of its idle window reaches neither the lease nor the stored
    sign-in, so no MCP activity extends the person's deadline today.
  - After its session is retired the terminal interface clears its view, shows its login
    screen and waits; resume there is an action the person presses. The MCP server has
    no person at hand: it refuses with the existing refusal shape, and resumes when a
    later call finds a live sign-in.
  - On Windows, when the runtime's desktop can be witnessed, an MCP process started
    outside the desktop shell by the same account is bound to the same logon and
    resumes the same sign-in. Otherwise the peer's own logon is used, and a presenter
    from another logon of the same account is refused and the stored sign-in is deleted
    before its proof is checked, which signs the person out everywhere. The command-line
    frontend reaches that today; admitting MCP adds a door to it and not the behaviour.
    Whether a mismatched login should delete the sign-in at all is settled with the door.
- Still untraced: whether a long-lived session is bound through the worker's five-minute
  in-process idle window. If it is, a session with more than five quiet minutes between
  storage accesses is refused before its lease ends.
- Ruled by the owner on 2026-10-10: an MCP client may end only its own session ("agreed
  only self session"). It may not sign the person out or lock a session other than its
  own. Today it could, because those handlers are not keyed on frontend, so the handlers
  refuse both to a session on the MCP frontend. Superseded on 2026-10-11 by the owner's
  parity ruling in `2026-10-11-mcp-parity-full-parity-adr`, constraint 2: a session of
  the human kind signs the person out and locks other sessions on MCP exactly as on the
  command line, and the handlers are again keyed on the kind of session alone.
  Reversed on 2026-10-12 by the owner's ruling in `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`: an
  MCP client neither signs the person out nor locks any session, its own included,
  because the agent never manages authentication. Its session ends when the person's
  sign-in ends or its own lease lapses, and the server ends with its client.
- Reconsider if a narrower scope for the in-app agent is wanted after all; the delegated
  child session is then the route.
- Accepted 2026-10-10. The owner confirmed the door first-hand that day ("I confirm MCP
  should resume the shared sign-in like CLI and TUI") and authorized acceptance in
  advance: "if all findings converge we treat that as the approved state and continue
  onto plan writing". The three reviewing sessions the owner named agreed to this text,
  each within its scope. The points listed as to be ruled or to confirm stay open and
  gate the work that depends on them. Acceptance records the decision. It is not evidence
  that any of it is built.

Amended 2026-10-12 under `2026-10-12-mcp-parity-attended-live-sign-in-adr`: the delegated-child option rejected here is now the chosen door for one case only. An MCP connection with no key and no stored sign-in to resume asks to be attended by a person's held sign-in, and is admitted only by that person's approval of the exact connection. Resuming the shared sign-in stays the default and is unchanged.


## Active human lifetime refinement 2026-10-15

The authorized active-use amendment in `2026-10-04-application-sign-in-adr` replaces this record's fixed human idle/absolute lifetime wording only when actual person input renews a still-live human sign-in. The original-login absolute cap does not interrupt active work. Agent, polling and service traffic never renew it; idle expiry and explicit revocation still apply. Live human siblings on the same originating login follow that renewal, while attended children retain their existing bounded deadlines and approval-based reissue. This does not turn agent activity into human activity, expand scopes, or restore expired authority. Earlier observations that no human extension exists describe the pre-repair implementation.
