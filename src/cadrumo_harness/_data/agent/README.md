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
- `reference/`: generated documents a rule sends the agent to. `command-operations.md`
  lists, for every command a skill names, the tools that do its work through MCP: the
  registered operations the command submits, which `execute` runs, and every other
  route, which is an operation for `execute` or a query for `authority`. A command
  whose work is the person's own act says so instead: signing in or out, locking,
  sessions, keys, passwords and other secrets, recovery, and installation work such as
  the profile list, storage, repair and resetting every profile. Only the four
  commands that print help or start the terminal interface have no route at all.

You work only inside the one Cadrumo profile the person is signed in to, or the
profile a key the person issued and configured for this server is for. Start with
MCP `status`. It says whether a session admits this server: its session is
`sign_in` when the person's own sign-in is resumed, `key` when the configured key
admitted it, or `none`, and it names the surface the connection serves. With
`none`, every tool but `status` is refused, reference data and operation discovery
included, and the reply's `remedy` says what to do: ask the person to sign in to
Cadrumo, then call again. Under a session, `search` and `describe` find the
registered operations and `authority` answers public tax queries. Every operation
the command line can run inside the profile is among them, with the same results.

You never sign in, sign out, lock, list or deny sessions, request or approve a key,
change or reset a password, enrol recovery, or act outside your profile, and you
never ask for a password, a key or any other secret. No tool takes one. An operation
whose contract needs a secret or administers keys is the person's own act: it is
refused with `person_act_required`, and its `remedy` says to ask the person to do it
in Cadrumo. Tell the person what is needed and stop that step.

The session resumed from the person's sign-in ends when the person signs out,
locks, signs in to another profile, or the sign-in reaches its deadline, which by
default is 15 minutes after the password was entered. Activity through MCP does not
extend it. A refused call after that is answered with the same remedy; a call made
after the person signs in again resumes the new sign-in. If the person signed in to
another profile, the remedy says this agent session is over: the person starts a new
one.

To work while nobody is signed in, the person issues a key for the profile with
`aeat config profile automation` and starts the MCP server with `--profile-id` and
`--credential-reference`. The server authenticates with that key on every call while
its grant, the installation and the login policy remain valid. Revoking the key or
locking the profile ends that access. Requesting, renewing, rotating or changing the
scope of a key is the person's act in Cadrumo, never yours.

A lost reply is not proof that an operation failed or settled. Retain operation
receipts and reconcile uncertain effects after reconnecting.
