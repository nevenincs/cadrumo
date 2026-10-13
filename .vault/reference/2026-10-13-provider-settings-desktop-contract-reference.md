---
tags:
  - '#reference'
  - '#provider-settings'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:3716b78d8c2ff5eef03cab9e283d14f38897a0c90a4b82e1095bb993e99782c9'
related:
  - "[[2026-10-13-provider-settings-adr]]"
---

# `provider-settings` reference: `Provider settings desktop contract`

The contract the desktop's Tauri host and webview build against for provider settings, agreed with the desktop design sessions on 2026-10-13. The decision is `2026-10-13-provider-settings-adr`; this record fixes only the command surface, the shapes and the closed value sets. Every value below is a stable token the webview words in the chrome locale, except `display_name`, which is the provider's brand name in every locale.

## Channel

The host runs a digest-verified `aeat` child for each action, with the projected environment, a bounded deadline and settlement on every path, exactly as the sign-in view runs `aeat config login` (`native/desktop/src-tauri/src/shell/sign_in/mod.rs:183-216`, `shell/sign_in/process.rs:326-330,408-416,513-522`). A secret is written once, as one JSON object, to the child's standard input under `--secrets-stdin` and standard input is then closed (`src/cadrumo/entrypoints/cli/config/secure_input.py`). No secret is ever an argument. The child prints one JSON envelope on standard output. The shell holds no runtime connection and keeps no copy of a secret.

## Commands

| Action | Command | Standard input |
|---|---|---|
| Status | `aeat --format json config provider status` | none |
| Set or replace | `aeat --format json config provider set <provider> --expected-revision <revision> [--base-url <url>] --secrets-stdin` | `{"secret": "<value>"}` |
| Turn off | `aeat --format json config provider remove <provider> --expected-revision <revision>` | none |
| Reset | `aeat --format json config provider reset <provider> --expected-revision <revision>` | none |

`<revision>` is the value from the last status read; a provider with no record carries the revision `absent`. Set validates the value's form and stores it; it makes no call to the provider.

## Status result

One read lists every provider:

```json
{"providers": [
  {"id": "anthropic", "display_name": "Anthropic", "auth_kind": "api_key",
   "consumers": ["extraction", "assistant"], "mode": "key", "available": true,
   "source": "profile", "readiness": "not_verified", "reason": null,
   "base_url": null, "default_base_url": null, "revision": "<opaque>"}
]}
```

- `id`: `anthropic`, `openai`, `gemini`, `kimi`, `zai`, `zhipu`, `deepseek`, `moonshot`, `minimax`, `qwen`, `claude`, `codex`, `antigravity`.
- `auth_kind`: `api_key` | `api_key_with_base_url` | `oauth_token_or_provider_sign_in` | `provider_sign_in_only`.
- `consumers`: a subset of `extraction` | `assistant`.
- `mode`: `key` | `oauth_token` | `provider_sign_in` | `disabled` | `unset`.
- `source`: `profile` | `environment` | `none`. `environment` appears only in a development build, for a provider whose record is unset.
- `readiness`: `ready` | `not_verified` | `missing` | `disabled` | `sign_in_required` | `unusable`.
- `reason`: `null` when ready, else a closed code from the refusal list below or `not_configured`, `turned_off`, `sign_in_with_provider_tool`, `record_unreadable`.
- `base_url`: present only when the person stored one. `default_base_url`: the catalogue default, shown as a hint and never as a stored value; `qwen` has none.
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
- `person_act_required`: the request came from a frontend that may not change credentials.
- `unknown`.

## Reading status

There is no push. The webview reads status when the profile or agent panel opens, before an agent send, after the person's own change, and on a sign-in or profile change the shell already observes. It never polls. A change made elsewhere, for example from the CLI, appears at the next of these reads.

## Agent panel

The panel reads the same status. A provider whose `readiness` is not `ready` or `not_verified` is shown as unavailable with its reason and a pointer to profile settings, never as a failure. A provider key the provider rejects surfaces at first use as a typed agent refusal, distinct from any storage refusal.
