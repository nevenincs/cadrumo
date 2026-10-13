---
tags:
  - '#reference'
  - '#provider-settings'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:731264de71f39f8134eec4b4233c0123e782c54943dbaec33e7541c54a3381de'
related:
  - "[[2026-10-12-desktop-agent-host-reference]]"
---

# `provider-settings` reference: `Provider settings seams in tui`

## Summary

Cadrumo reads provider keys only from the environment, with no profile record, settings view or session-bound resolver. The person-act dispatch rule and the Google OAuth token namespace are the precedents to extend. cadrumo-agent supports four credential kinds across twelve providers. It hosts only anthropic and claude, and today takes keys only from its environment.

## Provenance

Discovery for this feature ran on 2026-10-13 in the cadrumo-agent checkout against Cadrumo `main` at `813a607ed5`, 1308 commits behind `tui`. Its notes sit in the agent checkout's ignored `.tmp/2026-10-13-profile-settings/` folder. This record keeps only the findings the decision relies on, re-read in `tui` on 2026-10-13. Locators prefixed `agent:` are relative to `src/cadrumo_agent/` in the cadrumo-agent checkout.

## Cadrumo today

- Provider keys come from the process environment only. `cadrumo_llm_anthropic_api_key`, `cadrumo_llm_openai_api_key` and `cadrumo_llm_gemini_api_key` are `SecretStr` settings fields (`src/cadrumo/core/config_llm_fields.py:52-63`). The Anthropic one is described as "env only, never logged". No record governs this directly; the closest is the scope exclusion in `2026-10-04-canonical-environment-adr`, which says the product reads the process environment only.
- Extraction takes those cached `Settings` (`src/cadrumo/application/ledger/invoice_draft_extraction.py:86-87`, `:182`, `:210-211`), and `LLMClient` keeps whatever settings it is handed (`src/cadrumo/adapters/outbound/llm/client.py:318`). Neither is keyed by session or credential generation.
- Precedent for a profile secret: `GOOGLE_OAUTH_TOKEN_NAMESPACE` is SECRET, PROFILE_LOCAL and PROCESS_LOCAL, keyed `{profile}` (`src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:868-876`), and is enrolled in `namespace_registry.py:134`. It keeps the default `remote_mirror_policy` of `CIPHERTEXT_WITH_METADATA` (`secure_object_namespaces.py:91`). A namespace that must never be mirrored has to declare `StorageRemoteMirrorPolicy.LOCAL_ONLY` (`src/cadrumo/adapters/persistence/storage/namespace_taxonomy.py:57-62`).
- The approved repository door is `secure_object_repository_for_bucket` (`src/cadrumo/adapters/persistence/storage/runtime_repository.py:44`). It checks the current bucket's live authority, not an application-issued session generation. Its secure reads touch the session's idle time, so background polling must not use them.
- Person acts already have one owner. `src/cadrumo/application/operations/person_acts.py:76-82` decides that an operation needing a secret, or any access-administration operation, is the person's. The runtime refuses it on the MCP frontend when describing it (`src/cadrumo/entrypoints/runtime/profile_connection_operations.py:251-256`) and again at submission. An operation that needs no secret is refused only if its definition id is enrolled there.
- One profile is signed in at a time. The runtime ends every other profile's sign-in when it admits a person's sign-in (`src/cadrumo/entrypoints/runtime/profile_connection_sessions.py:126`). No hosted-agent controller observes that event yet.
- MCP launch already takes `--surface` with the surfaces `full` and `read-only-local` (`src/cadrumo_harness/mcp/main.py:31-44`, `src/cadrumo/application/operations/mcp_surfaces.py:46-48`). The October full-parity records exist in `tui`. The mismatch the discovery found on `main`, where cadrumo-agent expects `--surface full` and the app had no such flag, is therefore narrower in `tui`. What remains to align is the exact tool list cadrumo-agent pins.

## cadrumo-agent today

- Supported providers and their credential kinds:
  - **API key:** anthropic (`anthropic-api`, `CADRUMO_AGENT_ANTHROPIC_API_KEY`), openai (`openai-api`) and kimi (`kimi-code-acp`, with the key inside a per-run model definition).
  - **API key plus base URL:** Anthropic-compatible gateways under `<provider>-claude-agent-acp:<backend>`. These are zai, zhipu, deepseek, moonshot and minimax, each with a default base URL, and qwen, which has none.
  - **Claude:** `claude-agent-acp:<backend>`, with provider CLI sign-in or a person-entered OAuth token (`CADRUMO_AGENT_CLAUDE_CODE_OAUTH_TOKEN`).
  - **Provider CLI sign-in only:** codex (`codex-app-server`) and antigravity (`antigravity-cli`).
- Hosted mode admits only anthropic and claude (`agent:providers/lane_admission.py:609-616`).
- The gateway hands credentials to its worker by `os.environ.copy()` (`agent:control/worker_management.py:159-183`). `main()` reads nothing from standard input (`agent:api/app.py:908-925`). A standard-input frame does not exist in the agent yet.

## Gaps the decision closes

- No persisted provider credential, no settings view and no masked status.
- No resolver bound to the exact profile and login generation that both extraction and the assistant share.
- No hosted-agent controller tied to sign-out, lock, expiry or a profile switch.
- No way to hand a key to the agent except its environment.
