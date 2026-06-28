---
tags:
  - '#audit'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` UX walkthrough audit (2026-05-14)

Manual operator-style exercise of the `aeat config google ...` CLI surface committed across P01. No tests, no code edits — subjective observations only, captured on a Windows host with the operator's `default` profile already configured and the CLI output language resolved to Spanish via that profile's `output.language` key.

## Top-level findings

1. **The Google integration is undiscoverable from curated help.** `aeat config --help` is a hand-curated document (rendered by `application/operator_surface.build_help_document`) that lists `profile`, `auth`, `repair`, and the `init` first-run command — but never mentions `google`. A new operator has zero discoverability into the integration unless they happen to type `aeat config google --help` blind. The `google` sub-app is registered with Typer at runtime, but the curated help is the operator's primary entry point and it's silent.
2. **Mixed-language UX.** The root landing (`aeat`) renders entirely in Spanish. The curated `aeat config --help` document renders entirely in English. The `aeat config google` Typer-default help renders in Spanish (because my P01 i18n keys resolved correctly). Typer's built-in error frames ("Usage: ...", "Try '... --help'", "Missing option ...", "Invalid value for ...") render in English regardless of locale. The operator sees three different language regimes in one command tree.
3. **No operator hand-holding for the prerequisite.** `aeat config google register` requires a Cloud Console Desktop OAuth client JSON file. The `--help` text says "Path to a Cloud Console Desktop OAuth client JSON file" but never explains how to obtain one. There's no `aeat config google setup` or `aeat config google how-to-register` surface. The operator needs out-of-band knowledge of Cloud Console UI navigation, OAuth consent screen configuration, and Desktop client creation. For a tax-CLI user this is a hard block.
4. **`login` hangs silently on a fake / unregistered / unreachable Cloud project.** Invoking `aeat config google login` after registering a fake client produced zero output and ran past a 20-second timeout. The CLI gave no indication that it was about to open a browser, no consent URL the operator could open manually, no progress message, no timeout. Even the real-flow path would benefit from a "About to open your browser to grant Drive + Sheets scopes for {account}" preface.
5. **Validation errors leak pydantic internals.** A JSON missing required `installed.*` fields produces a refusal that dumps the raw pydantic error list:
   ```
   Refused. client JSON at <path> failed schema validation:
     [{'type': 'missing', 'loc': ('client_secret',), 'msg': 'Field required', 'input': {...}},
      {'type': 'missing', 'loc': ('project_id',), ...}, ...]
   ```
   This is the kind of internal noise a developer can read but an operator cannot.
6. **No remediation hints surface in error output.** Every `GoogleAuthError` subclass carries a `suggestion=` field in its constructor (`"aeat config google register --client-json <path>"`, `"aeat config google login"`, etc.). The `login`-without-registered-client error renders as `Refused. no OAuth client registered for profile 'default'` with NO suggestion attached. The hand-off via `CliRefusedBoundaryError(str(exc))` discards the `suggestion` / `context` fields.
7. **`logout` reports "success" for non-actions.** `aeat config google logout` on a profile that never logged in echoes `token_removed=False / metadata_removed=False / client_preserved=True`. Technically correct. To an operator who never logged in, this reads like a confirmation that they did something.

## Pass-by-pass observations

### Pass 1: bare `aeat`

Lands the Spanish root landing. Quick-start list is profile → overview → ledger import → review → repair. No mention of Google. Acceptable — Google is an opt-in surface — but the operator has no breadcrumb to discover it.

### Pass 2: `aeat config --help`

Curated help in English. Lists: First run / Profile / Authentication / Diagnostics sections. **Google is absent from every section.** The integration is invisible at the operator's primary help entry point.

### Pass 3: `aeat config google` (bare)

Default Typer table-style rendering. Title line in Spanish: "Gestionar la integración OAuth de Google Desktop para Drive y Sheets". Command list in Spanish. Style inconsistent with the curated `aeat config --help` from Pass 2.

Missing onboarding sentence: no "Para empezar, ejecuta X después de Y" guidance. An operator landing cold has to guess that the dependency order is register → login → status.

### Pass 4: `aeat config google register --help`

Required `--client-json` path option with Typer's default `exists=True, file_okay=True` enforcement. Help text says "Path to a Cloud Console Desktop OAuth client JSON file". No link, no instructions on how to obtain one. An operator who has never been to Cloud Console is dead-ended here.

### Pass 5: `aeat config google register` (no flag)

Typer's English error frame: "Missing option '--client-json'." Clean and correct, but English-only inside an otherwise Spanish-localised help tree.

### Pass 6: `aeat config google status` (no client registered)

Returns instantly. Output: 4 TSV lines (operation / profile / client_registered=False / session_present=False). No "next step" guidance. Dense for the human-readable rendering — even on `--format text` the output reads like JSON-in-disguise.

### Pass 7: `aeat config google login` (no client registered)

Output: `Refused. no OAuth client registered for profile 'default'`. **No suggestion**, no remediation, no pointer to `register`. The error class carries a `suggestion="aeat config google register --client-json <path>"` but the renderer drops it.

### Pass 8: `aeat config google logout` (nothing to log out)

Reports `token_removed=False`, `metadata_removed=False`, `client_preserved=True`. Cosmetically a "success" output for a no-op. Operator could mistake this for confirmation that they had a session.

### Pass 9–10: register with a fake client JSON

Synthesised a `{"installed": {...}}` JSON with believable shape. `register` accepts it, prints `operation/profile/client_id/project_id`. **No next-step hint.** Status now reports `client_registered=True / session_present=False / client_id=...`. Good that the SecureObjectRepository persistence path works — but the operator has no idea what to do next.

### Pass 11: `login` with fake client

Hangs silently. No output. No browser-launch announcement. No consent URL. No timeout. Killed at 20s by an external timeout. A real operator would not know whether the CLI is broken, opening a browser, waiting on a daemon, or making them wait forever.

### Pass 12: `status` mid-failed-login

Status still shows the fake client — login hadn't reached the persistence path because the OAuth round-trip never completed.

### Pass 13: `logout` (with client, no session)

Same `client_preserved=True` cosmetic-success behaviour as Pass 8. At least the contract (logout preserves client) is observable.

### Pass 14: register malformed JSON

Output: `Refused. client JSON at <path> is not valid JSON: Expecting value`. Reasonable. Could be friendlier ("This file isn't a JSON document; download the Cloud Console client JSON and re-run.").

### Pass 15: register `{"web": ...}` Web Application JSON

Output: `Refused. client JSON at <path> is not a Cloud Console Desktop client; expected an "installed" wrapper key`. Good error message — names the actual shape mismatch and the operator can act on it.

### Pass 16: register JSON without `installed` wrapper

Same refusal as Pass 15. Consistent. Both cases say the same thing because the validator treats "not Desktop shape" as one category.

Register against non-existent path falls to Typer's English frame:
```
Invalid value for '--client-json': File '<path>' does not exist.
```
Again English-only inside the otherwise Spanish locale.

### Pass 17: register with missing inner fields

The pydantic ValidationError dump (described in finding #5). Brutal.

### Pass 18: `aeat --format json config google status`

Compact single-line JSON. Surfaces every field including `account_email=null`, `granted_scopes=[]`, `issued_at=null`. Suitable for scripting. Good.

### Pass 19: `--profile <name>` override path

`register --profile test-profile` persists under a separate SecureObjectRepository key. `status --profile test-profile` and `status` (default) return different states. Per-profile isolation works as ADR-0 §5 promised.

## Recommendations

- **D1.** Add `google` to the curated `aeat config --help` document with an inline "Google Drive + Sheets" line under a "Cloud Sync" (or similar) section. Without it, the integration is unreachable except by brute-force tab completion.
- **D2.** Add a `setup` / `instructions` operator-facing surface that prints the prerequisites: how to create a Cloud Console project, enable Drive API + Sheets API, configure the OAuth consent screen in Testing mode, create a Desktop OAuth client, and download the JSON. This is the documentation gap that out-of-band knowledge currently covers.
- **D3.** Localise Typer's built-in frames. Either patch Typer's text via a click-translation layer, or accept the mixed-language UX and document it. The current state surprises Spanish-locale operators.
- **D4.** `login` should print, before doing anything: "About to open your default browser to grant Drive + Sheets scopes for the {account}. Press Ctrl+C to abort." Then print the consent URL so operators can open it manually if the browser launcher fails.
- **D5.** `login` should accept a `--timeout <seconds>` flag (default e.g. 120) and fail loudly with a `GoogleAuthBrowserOpenError`-shaped refusal when the consent receiver doesn't see a callback in time.
- **D6.** `CliRefusedBoundaryError`'s renderer should surface the wrapped `GoogleAuthError`'s `suggestion` and `context` fields, not just `str(exc)`. Otherwise the entire suggestion-attached error hierarchy is decorative.
- **D7.** The pydantic ValidationError-dump path in `_coerce_client_json` should map field-missing errors to operator-readable lines: "The Cloud Console JSON at {path} is missing required fields: client_secret, project_id, ... Re-download the Desktop client JSON from the Cloud Console; partial JSONs typically come from a copy-paste that omitted fields below the fold."
- **D8.** Status / register / logout text output should carry a trailing `next:` line. After a successful `register`, print `next: aeat config google login`. After `logout` of an empty session, print `next: (already logged out; run aeat config google login to start a new session)`.
- **D9.** The TSV-style text output (`key\tvalue` lines) is denser than the rest of the CLI which uses `tag value` columns. Either standardise on the existing convention or document the divergence.
- **D10.** Add a `--print-url-only` flag to `login` that emits the consent URL without launching a browser, for remote-development and headless contexts. This is the workaround when D4's "open in browser" fails.

## Scaffold status

This audit confirms the user's "scaffold" classification of the P01 work. The CLI surface compiles and the structural plumbing (record persistence, error hierarchy, profile isolation) is observable. But the integration claim — that an operator with a Cloud Console Desktop client can run `aeat config google login` and end up with a usable Google Drive session — was never demonstrated end-to-end in this walkthrough because the `login` command hangs on the fake client and a real client requires Cloud Console manual setup that the CLI does not assist with.

Real end-to-end verification still requires:
- A real Cloud Console Desktop OAuth client (operator-created out-of-band, or `gcloud alpha iap oauth-clients create` once the alpha components are refreshed via scoop)
- A manual `register` + `login` invocation with browser interaction
- A `status` confirmation showing the real account email
- A `logout` confirmation clearing the persisted records
- The `test_oauth_live.py` + `test_google_drive_live.py` suites with `AEAT_LIVE_TESTS_ENABLED=1`

None of those happened in this audit. The work remains scaffold pending those gates.
