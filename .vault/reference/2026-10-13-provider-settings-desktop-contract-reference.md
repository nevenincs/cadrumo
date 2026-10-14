---
tags:
  - '#reference'
  - '#provider-settings'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:f19e42da6558fe621698f6ca95e54cdcd3bf227fda9c240b05cb127c507b2043'
related:
  - "[[2026-10-13-provider-settings-adr]]"
---

# `provider-settings` reference: `Provider settings desktop contract`

The contract the desktop's Tauri host and webview build against for provider settings, agreed with the desktop design sessions on 2026-10-13. The decision is `2026-10-13-provider-settings-adr`; this record fixes only the command surface, the shapes and the closed value sets. Every value below is a stable token the webview words in the chrome locale, except `display_name`, which is the provider's brand name in every locale.

## Summary

The desktop manages provider settings through four `aeat config provider` commands, reads one status listing every cadrumo-agent lane, and never sees a key after it is entered. The sections below fix the channel, the commands, the shapes and the closed value sets.

## Channel

The host runs a digest-verified `aeat` child for each action, with the projected environment, a bounded deadline and settlement on every path, exactly as the sign-in view runs `aeat config login` (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:183-216`, `shell/sign_in/process.rs:326-330,408-416,513-522`). A secret is written once, as one JSON object, to the child's standard input under `--secrets-stdin` and standard input is then closed (`src/cadrumo/entrypoints/cli/config/secure_input.py`). No secret is ever an argument. The child prints one schema-2 JSON envelope on standard output, under the command names `config.provider.status`, `config.provider.set`, `config.provider.remove` and `config.provider.reset`. The shell holds no runtime connection and keeps no copy of a secret.

## Commands

| Action | Command | Standard input |
|---|---|---|
| Status | `aeat --format json config provider status` | none |
| Set or replace | `aeat --format json config provider set <provider> --expected-revision <revision> [--base-url <url>] --secrets-stdin` | `{"secret": "<value>"}` |
| Turn off | `aeat --format json config provider remove <provider> --expected-revision <revision>` | none |
| Reset | `aeat --format json config provider reset <provider> --expected-revision <revision>` | none |

`<revision>` is the value from the last status read: 64 lowercase hexadecimal characters. A provider with no record carries 64 zeros. Set validates the value's form and stores it; it makes no call to the provider.

The base URL is stored with `--base-url <url>`, reverted to the catalogue default with `--clear-base-url`, and kept when neither is given. An empty field in the webview maps to `--clear-base-url`. Changing only the base URL still takes the key, because the record is written as one unit.

Every command resumes the person's persisted sign-in. A held sign-in that was never persisted (`config sign-in-hold`) cannot serve another process, so these commands answer `not_signed_in` while only a held sign-in exists.

## Status result

One read lists every provider. `development` says whether the environment fallback applies, so the webview can word it and Reset:

```json
{"development": false, "providers": [
  {"id": "claude_api", "provider": "claude", "transport": "api", "display_name": "Claude",
   "auth_kind": "api_key", "consumers": ["assistant"], "mode": "key", "available": true,
   "source": "profile", "readiness": "not_verified", "reason": null, "cli_state": null,
   "base_url": null, "default_base_url": null, "revision": "<64 hex>"}
]}
```

There is one entry per cadrumo-agent lane, generated from cadrumo-agent's own source (`dev/provider_catalog/generate.py`, checked by `just check-provider-catalog`):

| id | provider | transport | display_name | auth_kind |
|---|---|---|---|---|
| claude_api | claude | api | Claude | api_key |
| claude_cli | claude | cli | Claude | oauth_token_or_provider_sign_in |
| codex_api | codex | api | Codex | api_key |
| codex_cli | codex | cli | Codex | provider_sign_in_only |
| antigravity_cli | antigravity | cli | Antigravity | provider_sign_in_only |
| kimi_cli | kimi | cli | Kimi Code | api_key |
| zai_cli | zai | cli | Z.ai | api_key_with_base_url |
| zhipu_cli | zhipu | cli | Zhipu AI | api_key_with_base_url |
| deepseek_cli | deepseek | cli | DeepSeek | api_key_with_base_url |
| moonshot_cli | moonshot | cli | Moonshot AI | api_key_with_base_url |
| minimax_cli | minimax | cli | MiniMax | api_key_with_base_url |
| qwen_cli | qwen | cli | Qwen (Alibaba Model Studio) | api_key_with_base_url |

- `id`: `<provider>_<transport>`, matching `^[a-z][a-z0-9_]{0,39}$`; the commands take it.
- `provider`: cadrumo-agent's identity; every lane of an identity carries the same `provider` and `display_name`, the product name. The webview adds the transport and the icon.
- `transport`: `api` | `cli`.
- `consumers`: `assistant` only; provider keys serve cadrumo-agent's lanes, not Cadrumo's own features.
- `mode`: `key` | `oauth_token` | `provider_sign_in` | `disabled` | `unset`.
- `source`: `profile` | `environment` | `none`; `environment` appears only when `development` is true, for a lane whose record is unset.
- `readiness`: `ready` | `not_verified` | `missing` | `disabled` | `sign_in_required` | `unusable`.
- `reason`: `null` when ready, else a closed code from the refusal list below or `not_configured`, `turned_off`, `sign_in_with_provider_tool`, `record_unreadable`.
- `cli_state`: for `cli` lanes `installed_signed_in` | `installed_signed_out` | `not_installed` | `unknown`; `null` for `api` lanes. Every `cli` lane reports `unknown` until a safe check exists; show it as not checked, never as not installed.
- `base_url`: present only when the person stored one. `default_base_url`: the catalogue default, a hint and never a stored value; `qwen_cli` has none.
- `revision`: the guard every change sends back.

No field ever carries a secret, a fragment of one, or a value derived from one.

## Change results and refusals

A successful change returns the provider's new status entry. A refusal returns `{"refused": "<code>"}` with one of:

- `not_signed_in`: no signed-in profile.
- `profile_locked`: the profile is locked.
- `invalid_key_format`: empty, too long, non-printable, or a masked placeholder.
- `base_url_rejected`: not `https`, or not allowed for this provider.
- `revision_conflict`: the record changed since the status read; read again.
- `committed_readback_failed`: the change is stored but could not be read back; show it as saved with unknown status and read again.
- `catalog_unavailable`: cadrumo-agent could not report its providers, so nothing was read or changed.
- `runtime_unavailable`: no runtime took the request, so nothing was read or changed; check the background-services manager and retry. A change the runtime already took and then lost reports `unknown` with its `operation_id`, never this code.
- `person_act_required`: the request came from a frontend that may not change credentials.
- `unknown`.

## Reading status

There is no push. The webview reads status when the agent panel's settings open, before an agent send, after the person's own change, and on a sign-in or profile change the shell already observes. It never polls. A change made elsewhere, for example from the CLI, appears at the next of these reads.

## Agent panel

The panel reads the same status. A provider whose `readiness` is not `ready` or `not_verified` is shown as unavailable with its reason and a pointer to profile settings, never as a failure. A provider key the provider rejects surfaces at first use as a typed agent refusal, distinct from any storage refusal.
