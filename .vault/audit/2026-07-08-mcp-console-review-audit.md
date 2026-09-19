---
tags:
  - '#audit'
  - '#mcp-console-review'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:15cf8a58ac1a3fba2105d8f96dd19503999fa9fcf125bbed5d92128890c92e09'
related:
  - '[[2026-07-08-mcp-progressive-discovery-adr]]'
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
---

# `mcp-console-review` audit: `MCP console cold-start discovery, CLI-coupling, and identity review`

## Scope

After the `mcp-progressive-discovery` and `mcp-protocol-hardening` ADRs were
implemented, an operator directive of 2026-07-08 asked for a fresh no-context
agent-based review of the shipped MCP console surface, focused on two questions:
whether the surface gives an agent sufficient tools to DISCOVER the CLI's domains
and correct usage without any hard-coded coupling to the CLI, and whether tool
calls are safely bound to the active taxpayer identity. Four independent,
no-prior-context agents were run: a CLI-coupling auditor, a cold-start
discovery-sufficiency reviewer (drove the real server end to end), an
identity-safety reviewer (drove the real server), and a senior-architect
adjudication pass that ruled on the findings and packaged the remediation. This
document persists their findings per `aeat-campaign-close-honesty-review`; each
actionable item is tracked as a Step in a follow-on plan with a verification
gate.

The load-bearing reframe from the adjudication pass: MOST of these findings are
CONFORMANCE DEBT against the two already-accepted ADRs, not new decisions.
`mcp-protocol-hardening` H3 ruled the risk axes "become declared data keyed by
command key ... with a parity gate"; the implementation shipped hand-listed
leaf-name frozensets instead. `mcp-progressive-discovery` P2 chose "FTS5 lexical +
model2vec semantic, RRF fusion"; the command index shipped lexical-only. So the
bulk of the remediation is a conformance wave under the existing ADRs, and only
the identity work is genuinely new (a new core tool, a new gate dimension, a core
envelope change) requiring a new ADR.

## Findings

### risk-classification-hand-listed | high | The per-command risk classification matches hand-listed leaf-name word sets, so a new mutating verb auto-approves and escapes handoff denial

The MCP risk classification matches destructive / idempotent / handoff /
live-write on the command key's trailing WORD against hand-listed frozensets in
`src/aeat/application/operator_surface/_classification.py` (lines 30-47). That
classification drives the MCP `destructiveHint`, the human-in-the-loop
confirm/block/auto-approve gate in `src/aeat/entrypoints/mcp/_hitl.py`, and the
per-persona handoff denial in `src/aeat/entrypoints/mcp/_persona_scope.py`. The
tests assert only internal COHERENCE (never both read-only and destructive), never
CORRECTNESS. A new verb whose leaf is `purge`, `wipe`, `terminate`, or `finalize`
falls through every set, classifies non-destructive, receives `AUTO_APPROVE`
(`_hitl.py:72-74`), and silently escapes the preparer/reconciler handoff denial
(`_persona_scope.py:256-290`). This is the one finding with a direct safety
consequence. It is also direct conformance debt against `mcp-protocol-hardening`
H3, which mandated declared per-command data plus a no-silent-default parity gate.
The verbs the current frozensets miss include the sandbox discard/prune, repair
quarantine, config reset, ledger stash, and the composite quickfile.

### manifest-has-no-per-command-risk-or-concept-field | high | The self-description carries per-family mutability only; the risk and grouping data the MCP layer needs is re-encoded downstream by hand

The operator-surface manifest (`MOUNTED_COMMAND_FAMILIES` in
`src/aeat/application/operator_surface/_contract.py`) is hand-authored Python whose
per-family `mutability` is checked for EXISTENCE against the live command tree by a
CI drift gate but never for factual correctness, and it carries NO per-command
risk field and NO per-verb concept tag. Because the single self-describing
authority is missing exactly the two things the MCP layer needs, both got
re-encoded downstream: the risk classification (above) and the toolset grouping.
An independent second declaration of "which verbs write" already exists in
`src/aeat/application/storage_write_policy.py` (`PROFILE_BOUND_WRITE_VERB_PATHS`),
which a parity gate can cross-check against the declared mutability in both
directions.

### command-search-lexical-only-mis-ranks | high | The command index is lexical-only and ranks an unrelated homonym above the correct command

Driving the real server, a cold agent searching "import a bank statement" got
`modelo.review_package.import_feedback` ranked ABOVE the correct `ledger.import`,
purely on the shared token "import". The command index in
`src/aeat/application/command_search/_index.py` is FTS5/BM25 lexical-only; the
model2vec semantic side was wired for the legal-corpus index but not the command
index. This is conformance debt against `mcp-progressive-discovery` P2 ("FTS5 +
model2vec, RRF fusion"). Related: CLI-verb phrasing ("file my quarterly VAT")
ranks worse than outcome phrasing ("calculate how much VAT I owe"), and the
composite `quickfile` is invisible under literal-verb queries — semantic backing
plus per-column BM25 weighting (command key and tool name over description over
help) and alias vocabulary in the quickfile doc are needed together.

### no-identity-assertion-tool-in-core | high | The core surface has no identity-assertion tool and the live gate has no identity dimension, so an agent can act under the wrong taxpayer profile

The CLI operates on a per-taxpayer profile. `config profile status` returns the
active-profile human label in clear text, and `overview status` (already core)
carries `active_profile.label` — but the command the docs and the golden-eval
treat as the canonical identity check (`config profile status`) is NOT in the
core surface, so an agent must `search` for it, i.e. already suspect it needs an
identity check to find the tool that performs one. The live confirmation gate
(`confirmation_for_tool` in `src/aeat/entrypoints/mcp/_hitl.py`) keys purely on
mutability with ZERO identity dimension; identity confirmation is only scored
offline by a golden eval, never enforced live. Concrete failure: a session with
Erik active, told "now do Erika's Modelo 130", runs `modelo work create/calculate`
against Erik's bucket if the agent forgets `config switch` — and the mutating
result cannot flag it because redaction (`src/aeat/core/redaction/__init__.py`)
collapses raw profile/bucket UUIDs to the CONSTANT literal `<profile-id>` /
`<bucket-id>` (not a per-value hash), so every mutation against every profile
echoes identical text.

### toolsets-undiscoverable | medium | The toolset-activation feature is functional but nothing tells an agent it exists or why to use it

The `toolsets` meta-tool works (activating `ledger` grew the advertised surface
14 → 81 tools in one session, live-confirmed) but nothing in `list`, `contract`,
or `harness_load` explains that it exists, why to activate a toolset instead of
using `execute`, or that only five domains have a toolset. A cold agent finds it
only by poking the bare name. Companion gap: `harness_load` teaches raw shell verb
strings (`aeat app modelo work create`) and never mentions `search` / `execute` /
`toolsets` or the verb-string-to-command-key translation, leaving that inference
to the reader.

### discovery-schema-and-overflow-gaps | medium | Search silently truncates, no describe-by-key path exists, and some schema fidelity is prose-only

`search` hard-caps at 20 results (`src/aeat/entrypoints/mcp/_meta_tools.py`) with
no `total_matches` or overflow signal, so a broad query silently hides commands.
There is no `describe_command(command_key)` tool, so the only way to re-fetch a
known command's schema is to re-run `search` and hope it re-surfaces in the top
20 (the `mcp-progressive-discovery` P2 ADR explicitly delegated the describe/schema
shape to the plan). Two schema-fidelity tails: `required[]` cannot express
one-of identifier combinations (`work_unit_id` OR `modelo+year+period` both show
empty `required`), and some closed value sets are prose-only, not JSON `enum`
(the `ledger.import` `provider` field), inconsistent with sibling fields that do
use enums.

### toolset-and-orientation-token-coupling | low | Toolset grouping and the orientation core key on hand-listed CLI tokens

Toolset membership keys on hardcoded tokens (`m036`, `censo`, `iva_wallet`,
`app.live.borrador.100`) in `src/aeat/entrypoints/mcp/_toolsets.py`, and the
orientation core is a hardcoded prefix/key pair in
`src/aeat/entrypoints/mcp/_surface.py`. Membership WITHIN a recognised token is
derived from the live surface; only the choice of tokens is hand-listed, so a
rename or a sixth tax-concept surface degrades discoverability (not safety, since
`search`/`execute` still reach everything). The adjudication ruled these
low-value to fully manifest-derive: keep the small hand-built declarations with
their against-live-keys gates rather than add a per-verb concept axis for five
groups.

## Recommendations

Adopt the adjudication pass's two-track packaging. TRACK 1 is a conformance wave
under the two existing ADRs (no new ADR): a declared per-command risk table keyed
by full command key co-located with the manifest, the frozensets deleted in the
same atomic commit, a no-silent-default parity gate plus a bidirectional
write-policy-vs-mutability parity gate plus a live-write leaf tripwire test
(safety, ships FIRST); then the semantic command index with a pinned retrieval
golden set, a `describe_command` tool, and a search overflow signal; then the
discoverability prose (harness_load long-tail section, toolset cross-references).
TRACK 2 is a new ADR `mcp-identity-linked-operation`: a `whoami` core tool over
the existing profile-health assessment, a block-first-mutation identity gate
re-armed on profile switch, an `active_profile` field on the shared envelope spine
(not per-result-model, keeping UUID redaction intact), and an elicitation identity
echo. Priority: Track 1 risk table first (safety and pure conformance debt), then
the identity ADR and plan (highest-stakes behaviour, needs approval and consumes
the risk table's mutating-set definition), then discovery quality, then prose.
Defer toolset auto-activation and any always-advertised manifest flag until the
discovery A/B measurement produces numbers.
