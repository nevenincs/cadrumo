---
tags:
  - '#audit'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:b9b5b93f14383316caf84d3f05f80a827552e05350a51706fe37aa3a2b29ec24'
related:
  - '[[2026-07-13-data-output-standardization-adr]]'
  - '[[2026-07-13-data-output-standardization-research]]'
  - '[[2026-07-13-data-output-standardization-plan]]'
---

# `data-output-standardization` audit: `AEAT env-var ownership adjudication`

## Scope

Per-field ownership adjudication for every `aeat_*`-prefixed `Settings` field
across `core/config.py`, `core/_config_runtime_fields.py`,
`core/_config_timeouts.py`, and the `AEAT_IVA_CATALOGUE_ROOT` seam threaded
through `core/resources/_repos/iva_catalogues.py`, at HEAD of
`chore/eliminate-shims`. Grounds ADR ruling R6 (env-var prefix adjudication)
and research findings F1.2 (env-var prefix split) and F6.2 (env-var prefixes /
unresolved ownership seams). Method: read every field's declaration and
docstring, classify by referent per the `cadrumo-product-authority-names`
doctrine (ownership/referent decides the prefix, not spelling), then measure
blast radius with a targeted `rg` sweep across `src/cadrumo` and `docs` per
field group. This table is the authorising input for Steps S18 (execute the
renames) and S19 (sweep docs/locales/error-registry/harness), which the plan's
parallelization notes gate behind S17 landing first.

Total field count: 49 (`config.py` 33, `_config_runtime_fields.py` 5,
`_config_timeouts.py` 11 -- corrected at S18 execution time; the original
summary arithmetic here undercounted both `config.py` and
`_config_timeouts.py` by one field each, though every individual field below
already carried a complete, correct verdict). Every field maps to exactly
one of three referent
buckets per R6: **authority referent** (AEAT's own URL, template path, or
verbatim bundled content — stays `AEAT_*`), **app-owned control** (a Cadrumo
policy knob, timeout, selector, or location the application owns — migrates to
`CADRUMO_*`), or **identity-adjacent** (`aeat_certificate_*` /
`aeat_clave_*_dni_*`/`_nie_*`/`_password` — adjudicated per-field below, since
R6 explicitly withholds a blanket verdict for this bucket).

Env var name is the uppercased field name in every case (no `env_prefix` is
set on `Settings.model_config`; `Settings.__doc__` confirms the field-name-to-
env-var mapping is direct, e.g. `aeat_base_url` reads `AEAT_BASE_URL`).

## Findings

### authority-referent-urls-and-templates | low | 7 fields stay AEAT_: base URL, sede/status/Cl@ve template paths

`aeat_base_url` (AEAT sede electrónica base URL), `aeat_clave_sede_access_url_template`,
`aeat_clave_permanente_sede_access_url_template`, `aeat_sede_expedientes_path`,
`aeat_status_detail_url_template`, `aeat_status_notificaciones_path`, and
`aeat_certificate_verify_url` (the mTLS smoke-test target, itself an AEAT sede
URL) are all URLs or path templates whose referent is AEAT's own web surface —
the field describes AEAT infrastructure, not an app-owned control. Verdict:
**KEEP AEAT_** for all 7. Consumer count (combined `rg` sweep across
`src/cadrumo`, deduplicated file set): 30 files, 118 occurrences. `docs`:
covered entirely by the auto-generated `docs/reference/environment-overrides.md`
(regenerate via `dev.docs.env_reference`, no hand-sweep). No locale or
error-registry hits for this group.

### authority-referent-bundled-corpus | low | 2 corpus roots stay AEAT_, one hand-authored catalogue root migrates

`aeat_manuals_root` ("Root directory for the structured AEAT Manual práctico
corpus") and `aeat_normatives_root` ("Root directory for the bundled legal
normatives corpus") both root VERBATIM bundled AEAT/BOE text — the referent is
the authoritative source document itself, not an app policy. Verdict: **KEEP
AEAT_** for both. `aeat_iva_catalogue_root` roots a "hand-reviewed IVA taxonomy
catalogue" — its own docstring names it hand-authored, i.e. an
application-maintained derivative, not verbatim AEAT text; ADR R6 explicitly
names `AEAT_IVA_CATALOGUE_ROOT` in the migrating bucket. Verdict: **RENAME to
CADRUMO_IVA_CATALOGUE_ROOT**. This is the ownership/referent distinction the
doctrine requires: two roots hold AEAT's own words, one holds the app's
analysis of AEAT's rules. Consumer count: 36 occurrences across 17 files
(all three roots combined); the `AEAT_IVA_CATALOGUE_ROOT` seam in
`core/resources/_repos/iva_catalogues.py` threads the constructor `root`
parameter only, no literal env-var string in that file to sweep.

### corpus-loading-policy-flags | low | 2 fields migrate: manuals review strictness and HTTP timeout are app-owned behaviour, not corpus content

`aeat_manuals_review_required` ("When True, manual corpus verification rejects
any Manual/Section/Rule record missing definition-review metadata; when False
the rejection is downgraded to a warning") and `aeat_manuals_http_timeout_s`
("HTTP timeout (seconds) for AEAT manual PDF downloads") are both APP
BEHAVIOUR controls layered on top of the manuals corpus, not the corpus
content itself — the app owns how strict its own validation is and how long it
waits on a download, independent of what the corpus root points at. Verdict:
**RENAME both to CADRUMO_MANUALS_REVIEW_REQUIRED /
CADRUMO_MANUALS_HTTP_TIMEOUT_S**. Consumer count: covered within the 36-file
corpus-root sweep above (these two fields co-occur with the roots in
`resources/_registry.py`, `application/registry/_corpus.py`,
`domain/manuals/_verify.py`, `domain/manuals/_loader.py`,
`domain/manuals/_fetch.py`, and their test siblings).

### domain-terminology-language-directive | low | 1 field stays AEAT_: authoritative language for AEAT's own vocabulary

`aeat_authoritative_language_aeat_terms` ("Authoritative language for domain
terminology (modelos, registry definitions, references)") describes which
language AEAT's OWN domain vocabulary is authoritative in — the field's
referent is AEAT terminology itself, not an app policy choice about how the
app behaves. Verdict: **KEEP AEAT_**. Consumer count: 8 files (mostly
`core/external_constants.py` and its test, plus scattered i18n consumers).

### browser-automation-controls | low | 11 fields migrate: Playwright channel, headless, locale, timezone, viewport, and all navigation/interaction timeouts

`aeat_browser_channel`, `aeat_browser_headless` (`config.py`);
`aeat_browser_locale`, `aeat_browser_timezone`, `aeat_browser_viewport_width`,
`aeat_browser_viewport_height` (`_config_runtime_fields.py`);
`aeat_browser_navigation_timeout_ms`, `aeat_browser_form_interaction_timeout_ms`,
`aeat_browser_ver_click_timeout_ms`, `aeat_browser_buscar_settle_ms`,
`aeat_browser_selector_probe_timeout_ms`, `aeat_browser_close_timeout_ms`
(`_config_timeouts.py`) are all APPLICATION-OWNED Playwright driver
configuration — which browser channel, whether headless, what locale/timezone
the app's own browser context presents, and how long the app's own automation
waits at each stage. None of these describe AEAT infrastructure; they
configure Cadrumo's browser automation layer. Verdict: **RENAME all 11 to
CADRUMO_BROWSER_***, matching ADR R6's explicit "browser control" migrating
bucket. Consumer count: 47 occurrences across 12 files (`_browser_constants.py`,
`browser/session.py`, `browser/profile.py`, `auth/_clave_movil.py`, plus test
siblings); `docs/reference/environment-overrides.md` auto-regenerates; no
locale or error-registry hits.

### proxy-and-rate-policy | low | 5 fields migrate: proxy URL/credentials/bypass and the inter-request delay

`aeat_proxy_url`, `aeat_proxy_username`, `aeat_proxy_password_secret`,
`aeat_proxy_bypass`, `aeat_rate_limit_delay_seconds` all configure the app's
OWN outbound HTTP behaviour (which proxy it routes through, how it
authenticates to that proxy, how long it waits between its own requests) —
none describe AEAT infrastructure. Verdict: **RENAME all 5 to CADRUMO_PROXY_*
/ CADRUMO_RATE_LIMIT_DELAY_SECONDS**, matching R6's explicit "proxy/rate
policy" migrating bucket. Consumer count: 15 occurrences across 2 files
(`browser/session.py`, `config.py`) — the narrowest blast radius of any group.

### auth-timeouts-and-provider-policy | low | 6 fields migrate: auth timeout, provider selector, Cl@ve preference and timeouts, live-IVA surface timeouts

`aeat_auth_timeout_ms`, `aeat_auth_provider` (`config.py`);
`aeat_clave_prefer_non_qr`, `aeat_clave_movil_timeout_ms`,
`aeat_clave_permanente_timeout_ms` (`config.py`); and the five live-IVA-surface
timeouts `aeat_live_iva_surface_timeout_ms`,
`aeat_live_iva_declaration_capture_timeout_ms`,
`aeat_live_filed_register_walk_timeout_ms`,
`aeat_live_iva_cancellation_drain_ms`, `aeat_live_iva_cli_watchdog_timeout_ms`
(`_config_timeouts.py`) are all APP-OWNED policy/behaviour: how long the app's
own probes wait, which provider the app auto-selects, whether the app prefers
the non-QR Cl@ve fallback. None select or describe AEAT-owned infrastructure;
they tune the app's own patience and defaults. Verdict: **RENAME all 11 to
CADRUMO_AUTH_* / CADRUMO_CLAVE_PREFER_NON_QR / CADRUMO_CLAVE_MOVIL_TIMEOUT_MS
/ CADRUMO_CLAVE_PERMANENTE_TIMEOUT_MS / CADRUMO_LIVE_IVA_* /
CADRUMO_LIVE_FILED_REGISTER_WALK_TIMEOUT_MS**, matching R6's explicit "auth
timeout/policy flags" migrating bucket. Consumer count: 102 occurrences across
34 files for the auth-timeout/provider/Cl@ve-flag subgroup (the single largest
blast radius of any group in this table — every Cl@ve/certificate auth adapter
and its tests reads at least one of these) plus the live-IVA timeout subgroup
already counted within that total (`application/live/_iva_remote_state.py`,
`application/live/_filed_data_capture.py`, `entrypoints/cli/_app_live.py`).

### identity-adjacent-certificate-fields | medium | 4 of 5 aeat_certificate_* fields migrate; the verify URL stays AEAT_

Per-field reasoning (R6 withholds a blanket verdict for this bucket):
- `aeat_certificate_path` — filesystem location of the OPERATOR'S OWN PKCS#12
  bundle on their machine. The certificate's issuer is AEAT-adjacent (a
  Spanish accredited CA), but the SETTING is an app-owned "where do I look"
  location control — the same class as the already-migrated
  `cadrumo_wallet_diagnostic_dump_dir` precedent research F6.2 cites. Verdict:
  **RENAME to CADRUMO_CERTIFICATE_PATH**.
- `aeat_certificate_password_secret` — the passphrase unlocking that local
  file; an app-owned secret input, not an AEAT referent. Verdict: **RENAME to
  CADRUMO_CERTIFICATE_PASSWORD_SECRET**.
- `aeat_certificate_friendly_name` — a cosmetic operator-chosen display label
  for the certificate; purely app-owned. Verdict: **RENAME to
  CADRUMO_CERTIFICATE_FRIENDLY_NAME**.
- `aeat_certificate_backend` — selects which INTERNAL Cadrumo backend
  implementation handles certificate auth (`playwright_context` vs
  `httpx_fallback`); a pure app-internal selector with zero AEAT referent.
  Verdict: **RENAME to CADRUMO_CERTIFICATE_BACKEND**.
- `aeat_certificate_verify_url` — the mTLS smoke-test TARGET, which is
  literally an AEAT sede URL. Verdict: **KEEP AEAT_CERTIFICATE_VERIFY_URL**
  (already counted in the authority-referent-urls-and-templates finding
  above).

Consumer count: 118 occurrences across 30 files for the four migrating fields
combined (`application/auth/_operator_scope.py`, `_operator_probes.py`,
`_operator.py`, `_certificate_sources_operator.py`,
`_certificate_secret_backend.py`, `adapters/outbound/aeat/auth/_authenticator.py`
(22 occurrences, the single hottest file), plus 12 test files); one locale/
error-registry hit set: none found for the certificate group specifically
(the Cl@ve DNI/NIE group below carries the locale hits).

### identity-adjacent-clave-dni-nie-fields | medium | all 5 aeat_clave_*_dni/nie/password fields migrate; user-facing string sweep required

Per-field reasoning:
- `aeat_clave_movil_dni_nie` — the taxpayer's own DNI/NIE, a Spanish national
  identity number, configured so the app knows WHICH identity to present to
  the Cl@ve Móvil auth broker. Cl@ve is a cross-government identity
  federation (not AEAT-owned infrastructure); the DNI/NIE value itself has no
  AEAT referent at all — it is the operator's own government identity,
  supplied to configure an app-owned choice ("which identity do I use"), the
  same ownership shape as `aeat_certificate_path` ("which credential do I
  use"). Verdict: **RENAME to CADRUMO_CLAVE_MOVIL_DNI_NIE**.
- `aeat_clave_movil_dni_fecha` — DNI validity/expiry date paired with the
  above, same reasoning. Verdict: **RENAME to CADRUMO_CLAVE_MOVIL_DNI_FECHA**.
- `aeat_clave_movil_nie_soporte` — NIE support number paired with the above,
  same reasoning. Verdict: **RENAME to CADRUMO_CLAVE_MOVIL_NIE_SOPORTE**.
- `aeat_clave_permanente_dni_nie` — same identity-selection reasoning for the
  Cl@ve Permanente provider. Verdict: **RENAME to
  CADRUMO_CLAVE_PERMANENTE_DNI_NIE**.
- `aeat_clave_permanente_password` — the Cl@ve Permanente login password
  paired with the identity above; an app-owned credential input, not an AEAT
  referent. Verdict: **RENAME to CADRUMO_CLAVE_PERMANENTE_PASSWORD**.

Consumer count: 93 occurrences across 28 files for the combined group
(`adapters/outbound/aeat/auth/_clave_movil.py`, `_clave_permanente.py`,
`_clave_movil_page_flow.py`, and 15 test files). Distinct from the other
groups, this rename has a CONFIRMED user-facing string sweep obligation:
`aeat_clave_movil_dni_nie`'s literal env-var name `AEAT_CLAVE_MOVIL_DNI_NIE`
is quoted verbatim in operator-facing prose in all four locale catalogues
(`src/cadrumo/locales/{en,ca,es,hu}.yml`, 4 occurrences each, 16 total) —
error messages telling the operator which env var to set. S19 MUST route
these 16 catalogue leaves through `python -m aeat.locales set` per-locale
(never hand-edited) when the rename executes, or the operator-facing guidance
will cite a dead variable name. No error-registry (`core/errors/registry/`)
or agent-harness (`_data/agent/`) hits were found for any `AEAT_*` env-var
literal in this campaign's full sweep — those two surfaces are clear for
every group in this table.

## Recommendations

- **S18 scope, corrected at execution time**: rename 39 of 49 fields to
  `CADRUMO_*` (all of browser-automation-controls, proxy-and-rate-policy,
  auth-timeouts-and-provider-policy, corpus-loading-policy-flags, the four
  migrating identity-adjacent-certificate-fields, all five
  identity-adjacent-clave-dni-nie-fields, and `aeat_iva_catalogue_root`). Keep
  10 fields `AEAT_*` total (`aeat_base_url`, the 6 sede/status/Cl@ve URL
  templates already counted under authority-referent-urls-and-templates,
  `aeat_certificate_verify_url` — 7 total URL/template fields — plus
  `aeat_manuals_root`, `aeat_normatives_root`, and
  `aeat_authoritative_language_aeat_terms`). Recount, corrected: 49 total =
  10 KEEP + 39 RENAME (33 `config.py` fields minus 10 KEEP = 23 migrate from
  `config.py`; all 5 `_config_runtime_fields.py` fields migrate; all 11
  `_config_timeouts.py` fields migrate; 23 + 5 + 11 = 39). The original
  "47 total / 37 migrate" arithmetic undercounted by 2 (a `config.py` field
  and a `_config_timeouts.py` field were both present in the per-field
  findings above with correct verdicts, but omitted from the summary
  addition); every individual field verdict in the Findings section above
  was already correct and complete, so S18 executes against the corrected
  count with no re-adjudication needed.
- Every rename in S18 is hard-cut per `no-legacy-compatibility`: no dual-read,
  no alias, add the retired `AEAT_*` name to `_LEGACY_PRODUCT_DOTENV_NAMES`
  only where the field was ever product-state-selecting (none of these 37
  are; they are runtime policy/location knobs, not identity/storage-selection
  state, so no new dotenv-exclusion entries are needed per this audit's
  reading of R6's "product-state-selecting" qualifier — S18's executor should
  re-confirm this against the exclusion set's existing rationale before
  landing).
- S19 MUST regenerate `docs/reference/environment-overrides.md` via
  `python -m dev.docs.env_reference` (generated file, never hand-edited) and
  MUST route the 16 locale-catalogue `AEAT_CLAVE_MOVIL_DNI_NIE` citations
  through `python -m aeat.locales set` per the locales-cli rule. No
  error-registry or agent-harness sweep is required for this campaign (zero
  hits confirmed across all groups).
- The `aeat_iva_catalogue_root` seam in
  `core/resources/_repos/iva_catalogues.py` threads a `root: Path | None`
  constructor parameter with no literal env-var string; S18 only needs to
  rename the `Settings` field and its `resources()` factory call site, not
  this repository file.
