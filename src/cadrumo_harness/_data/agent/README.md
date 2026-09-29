# AEAT operator agent-harness data

This tree is the **operating layer** for an LLM tax-advisor agent that drives the
deterministic `aeat` CLI. It is reviewed product data shipped inside the wheel and
read through the bundled-data boundary (`aeat.agent`). It carries no code and no
secrets.

The `aeat` CLI is the **backbone**: it computes the tax deterministically. The
harness is the **operating layer**: the agent orchestrates, extracts, classifies,
narrates, and hands off — but never computes a tax value itself.

Subtrees:

- `rules/` — the operator operating contract: always-on behavioural boundaries the
  agent loads every session. These are the operator analogues of the engineer-facing
  project rules, re-cast for the agent that *uses* the tool.
- `personas/` — tax-advisor role definitions (coordinator and task-scoped roles),
  each given the operating rules; runtime access comes from an approved exact-profile
  grant, independently of the persona name.
- `skills/` — executable workflow playbooks (preconditions, command sequence, JSON
  success assertions) for the canonical end-to-end tax flows.

Start with MCP `status`, then `search` and `describe` for the operations permitted
to this session. Public tax queries use `authority`. If private access is absent,
prepare an authorization request for human approval; never paste a password or API
secret into the conversation. Approved protected credential references support
fresh admission while the grant, installation and login policy remain valid.

Check the local runtime with `aeat app runtime status`. Where the platform supports
configuration, `aeat app runtime enable` enables login startup and
`aeat app runtime disable` retains on-demand startup. Neither command grants an
agent access to a profile. `aeat app runtime start` explicitly starts an already
provisioned runtime. These controls are also available in the TUI runtime screen.

Configure MCP with the exact profile ID. Leave the credential reference empty for
first enrollment, use `authorization_prepare` and `authorization_request`, and
have the user review the requested operations, periods and disclosures in CLI or
TUI. `authorization_poll` completes protected delivery; `authenticate` uses the
returned nonsecret credential reference. Reuse that reference for later sessions
only while the grant remains valid. Session locking ends that session; revoking
the key or suspending the profile prevents renewed access under the affected
authority. An unattended grant does not override those controls.

For rotation, renewal or a scope change, pass the existing protected
`credential_reference` to `authorization_prepare`, then submit the change with
`authorization_request`. This binds the request to that key's existing grant.
Human approval is still required. Poll for the terminal receipt and authenticate
again afterward; rotation returns a new credential reference. An unresolved
reply retains the request ID for reconciliation and does not mean approval failed.

Stopping the shared runtime affects every profile and agent using it. The TUI
requires explicit confirmation; CLI requires
`aeat app runtime stop --acknowledge-all-profiles-and-work`. An accepted stop is not
proof that every operation settled. Retain operation receipts and reconcile
uncertain effects after reconnecting.
