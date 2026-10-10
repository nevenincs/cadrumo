# AEAT operator agent-harness data

This tree is the **operating layer** for an LLM tax-advisor agent that uses
Cadrumo's profile-bound MCP server. It is reviewed product data shipped inside
the wheel and read through the bundled-data boundary (`aeat.agent`). It carries
no code and no secrets.

The Cadrumo engine computes tax deterministically for both CLI and MCP. The
harness is the **operating layer**: the agent orchestrates, extracts, classifies,
narrates, and hands off — but never computes a tax value itself.

Subtrees:

- `rules/` — the operator operating contract: always-on behavioural boundaries the
  agent loads every session. These are the operator analogues of the engineer-facing
  project rules, re-cast for the agent that *uses* the tool.
- `personas/` — tax-advisor role definitions (coordinator and task-scoped roles),
  each given the operating rules; runtime access comes from the connection's session
  (the person's sign-in or an approved exact-profile grant), independently of the
  persona name.
- `skills/` — executable workflow playbooks (preconditions, command sequence, JSON
  success assertions) for the canonical end-to-end tax flows.

Start with MCP `status`, then `search` and `describe` for the operations permitted
to this session. Public tax queries use `authority`. A connection is either under
the person's own Cadrumo sign-in or under an enrolled key, and `status` says which:
its session is `sign_in`, `key` or `none`, and it names the surface the connection
serves. Never ask for or accept a password, and never paste a password or API
secret into the conversation.

Under the person's sign-in, a profile tool is refused with `authentication_required`
when nobody is signed in to Cadrumo. Tell the person to sign in to Cadrumo, then
call again. The session ends when the person signs out, locks, or the sign-in
reaches its deadline, which by default is 15 minutes after the password was
entered. Activity through MCP does not extend it, and you can end only your own
session. To work while nobody is signed in, prepare an authorization request for
human approval, which enrolls a key.

Under an enrolled key, configure MCP with the exact profile ID and the credential
reference. Approved protected credential references support fresh admission while
the grant, installation and login policy remain valid. Leave the credential
reference empty for first enrollment, use `authorization_prepare` and
`authorization_request`, and have the user review the requested operations,
periods and disclosures in CLI or TUI. `authorization_poll` completes protected
delivery; `authenticate` uses the returned nonsecret credential reference. Reuse
that reference for later sessions only while the grant remains valid. Session
locking ends that session; revoking the key or suspending the profile prevents
renewed access under the affected authority. An unattended grant does not
override those controls.

For rotation, renewal or a scope change, pass the existing protected
`credential_reference` to `authorization_prepare`, then submit the change with
`authorization_request`. This binds the request to that key's existing grant.
Human approval is still required. Poll for the terminal receipt and authenticate
again afterward; rotation returns a new credential reference. An unresolved
reply retains the request ID for reconciliation and does not mean approval failed.

A lost reply is not proof that an operation failed or settled. Retain operation
receipts and reconcile uncertain effects after reconnecting.
