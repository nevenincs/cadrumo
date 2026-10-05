---
tags:
  - '#reference'
  - '#operator-deferred-actions-runbook'
date: '2026-07-04'
modified: '2026-10-05'
body_hash: 'sha256:f4cc709835815c44a025a74879c0de2a6974e75c90da0182f678527616c09cc6'
related: []
---

# `operator-deferred-actions-runbook` reference: `operator deferred actions runbook`

## Summary

Consolidated runbook for five items that are genuinely gated on an operator
action this repository's automation cannot and must not take: outward
publishing, a GitHub repository-settings toggle, a live external-service call
requiring credentials this environment does not hold, or a physical
document/resource the operator alone can supply. For each item this document
records the verified current state at HEAD, the exact single operator action,
and the acceptance signal that closes it. No outward action (push, tag,
publish, GitHub setting change, live external call) was taken while preparing
this document; every verification below was read-only or local.

Issue numbers below are the real GitHub issue numbers for this repository
(`nevenincs/aeat`); they differ from the `#110`-`#115` placeholder numbers used
to commission this runbook, which do not correspond to these five items in this
repository's tracker.

## Item 1 — cut the next release (issue #382)

**Verified autonomous surface: exhausted.**

- `just release` (`justfile:459` POSIX, `justfile:489` Windows) invokes
  `npx release-please@16 release-pr --dry-run --debug`. The `--dry-run` flag
  means this step never opens a PR, never pushes, never tags — it only writes
  a preview log to `var/release/release-please.log`. Fully local.
- `just release-apply` (`justfile:521`/`justfile:553`) does not mutate any
  file automatically. It asserts the branch is `main` and the tree is clean,
  then PRINTS a seven-step manual checklist (bump the manifest, `pyproject.toml`,
  `__init__.py`, prepend the changelog, stage, commit, tag) and explicitly ends
  with "When ready (human decision only), push with: `git push origin main --tags`".
  No push happens inside this recipe.
- `RELEASING.md` documents the full seven-step per-release checklist: version
  + changelog (local), gates (local), push (human decision, step 3), publish
  `aeat-cli` to PyPI (step 4, outward), publish the two data companions (step 5,
  outward), regenerate + push the Claude plugin/marketplace (step 6, outward),
  announce (step 7).
- Release-readiness gates confirmed green at HEAD:
  - `src/cadrumo/tests/test_release_config.py` — 5/5 passed (config well-formed,
    manifest well-formed, changelog non-empty, the three version surfaces
    (`pyproject.toml [project].version`, `src/cadrumo/__init__.py __version__`,
    `.release-please-manifest.json`) agree at `0.1.1`, and no
    `.github/workflows/release-please.yml` exists — GitHub Actions stays
    permanently disabled on this repo).
    — 2/2 passed (both `packaging/aeat_data_manuals/pyproject.toml` and
    `packaging/aeat_data_official/pyproject.toml` read `0.1.1`, matching root).
  - `just check-dependencies` (deptry) — clean, zero findings.
  - `just packaging-smoke-dependencies` — clean (24 project deps, 8 optional
    extras, 14 optional deps, 53 dev deps, registry extras anthropic/browser/google).
- `CHANGELOG.md` already carries a hand-curated `## [0.2.0] - 2026-07-02`
  section "Prepared per issue #382" summarizing the work landed since the
  `0.1.0` baseline (the registry/calculation-grounding hardening campaign and
  the hexagonal-architecture restructure, issue #476). That section's own
  "Notes" record that the three version files were deliberately left
  untouched pending the human-gated `release-apply` step. Since that section
  was written, a `0.1.1` patch release was cut and applied on top (dated
  2026-07-04, chronologically after the `0.2.0` prep date), so the version
  files currently read `0.1.1`, not `0.1.0`. This means a fresh `just release`
  dry-run is needed at cut time to let release-please walk the full commit
  history since `0.1.1` and reconcile the hand-curated `0.2.0` summary against
  its own per-commit delta, exactly as the `0.2.0` section's own note anticipates.

**No further autonomous prep is possible.** Every remaining step needs either
a human decision (push) or outward network calls with credentials this
environment does not hold (PyPI token, plugin marketplace push).

**Operator action:** from a clean `main` checkout, in order:

Regenerate and push the plugin/marketplace tree; update `docs/updates.md`    if the release changes filing behaviour.

**Acceptance signal:** the new version tag exists on the pushed `main`,
`pypi.org` renders the new `aeat-cli` version page, and
`uvx --from aeat-cli==X.Y.Z aeat --version` resolves on a machine without the
checkout.

## Item 2 — confidential vulnerability disclosure channel (issue #100, closed; residual is a repo-admin toggle)

**Verified autonomous surface: exhausted.**

- `SECURITY.md` (repo root) is complete and names all three disclosure paths:
  primary is GitHub private vulnerability reporting (the `Security` tab,
  `Report a vulnerability`); a documented fallback path (open a regular issue
  asking to be contacted privately, omitting technical detail) when the
  primary is unavailable; and an explicit maintainer-follow-up note recording
  that private vulnerability reporting is a per-repository
  `Settings -> Code security -> Private vulnerability reporting` toggle, that
  it is normally free on a public repository but requires GitHub Advanced
  Security on a private one, and that the three concrete options are: make the
  repository public, enable GitHub Advanced Security, or publish a secondary
  security-contact email as the working primary channel.
- The document also carries the full threat model (assets protected, trust
  boundaries, in-scope/out-of-scope), the security posture (local-only
  processing, no live AEAT submission, encrypted-at-rest sensitive data,
  master-key handling), and a pointer to the bundled-data disposition at
- README.md and CONTRIBUTING.md were checked for a disclosure-channel
  cross-reference. No `CONTRIBUTING.md` exists in this repository (contributor
  guidance lives in the README's "For contributors" section and in
  `CLAUDE.md`). README's "Getting help" section had no pointer to `SECURITY.md`;
  this was not a contradiction (nothing in README stated a different channel),
  only a missing cross-link. A one-line fix was landed as safe, non-outward
  prep: "Getting help" now also reads "Report a security vulnerability
  privately instead, per `SECURITY.md`."
- Note (not a defect): README, `docs/index.md`, `docs/updates.md`, and
  `pyproject.toml`'s author entry all consistently point at
  `github.com/operator/aeat`, while the current `origin` remote and `gh repo
  view` both resolve to `nevenincs/aeat`. This is a deliberate, consistent
  choice across every doc surface (not a one-off typo), most plausibly the
  intended eventual/canonical public URL versus the current interim hosting
  location. It was left untouched — silently rewriting it would be an
  out-of-scope guess about intended public identity, and every reference
  agrees with every other reference, so there is no actual inconsistency to
  reconcile.

**No further autonomous prep is possible.** The private vulnerability
reporting toggle is a GitHub repository-settings change this task is
forbidden from making (SAFETY: never toggle repo settings).

**Operator action:** one of:

1. Go to `Settings -> Code security -> Private vulnerability reporting` on
   `https://github.com/nevenincs/aeat` and enable it (works immediately if the
   repository is public, or if GitHub Advanced Security is enabled on this
   private repository).
2. If neither is available, publish a secondary security-contact email address
   in `SECURITY.md`'s "Secondary channel (not yet available)" paragraph.

**Acceptance signal:** the repository's `Security` tab shows a
`Report a vulnerability` button (Option 1), or `SECURITY.md`'s secondary
channel section names a real, monitored email address (Option 2).

## Item 3 — live-auth end-to-end verification (issues #300, #311)

**Verified autonomous surface: exhausted.**

- The offline safety and read-gate surface is complete at HEAD:
  - `core.access_gate.AeatAccessGate` — `require_live_read()` refuses a
    pytest-driven live read unless `CADRUMO_LIVE_TESTS_ENABLED` is exactly
    `"1"`;
    `require_live_write()` always raises `LiveSubmitForbiddenError`
    unconditionally (no code path can ever perform a live AEAT write).
  - `adapters.outbound.aeat.export._submitters` is a deliberately empty
      namespace — no remote submitter implementation exists anywhere in the tree.
  - `core.external_constants.AeatDomains` is a strict, frozen pydantic model
    (every hostname field `Field(min_length=1)`) holding every AEAT/Cl@ve/BOE
    origin as registry data, not scattered literals.
  - `src/cadrumo/tests/live_gate.py` provides the one shared
    `requires_live_enabled()` / `requires_live_google_enabled()` gate every
    `aeat_live`-marked test calls; both read `core.config.Settings` (never a
    raw `os.environ` re-implementation).
  - The `aeat_live` marker is registered in `pyproject.toml`, is skip-by-default
    (the default `addopts` selects `-m 'unit'`), and is documented in
    `src/cadrumo/tests/README.md` (marker taxonomy, live-read opt-in, banned
    imports for live-test files).
- Live-marked modules cover certificate and Cl@ve authentication, OAuth, Google
  Drive, declaration/notification/expediente reads, browser evasion, NIF/IVA
  and GROI checks, IVA compensation wallet, Renta WEB Open capture replay, and
  other real external reads.
- `src/cadrumo/adapters/outbound/aeat/auth/tests/test_authenticator_live.py`
  contains the certificate acceptance oracle. Its synchronous case checks
  certificate health and subject-derived identity. Its asynchronous case uses
  the production Playwright browser factory and accepts authentication only
  when navigation succeeds at the exact protected resource
  `https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`, with the
  final URL and parsed identity bound to the active session. A direct TLS or
  mTLS handshake, a public page, a context marker, or historical session
  metadata is not live authentication proof.
- Full-tree collection is clean at HEAD: `uv run --no-sync pytest
  --collect-only -q src/cadrumo` collects without collection errors; the
  default unit-only marker filter does not execute `aeat_live` tests.

**No further autonomous prep is possible.** Exercising the live path requires
a real AEAT certificate + password and a real network round-trip against the
AEAT sede, which this environment does not hold and must not perform.

**Operator action:** provision `CADRUMO_CERTIFICATE_PATH` +
`CADRUMO_CERTIFICATE_PASSWORD_SECRET` for a real FNMT/AEAT certificate, then
run:

```
CADRUMO_LIVE_TESTS_ENABLED=1 uv run pytest -m aeat_live
```

or a narrower slice, e.g.
`CADRUMO_LIVE_TESTS_ENABLED=1 uv run pytest -m aeat_live
src/cadrumo/adapters/outbound/aeat/auth/tests/test_authenticator_live.py`.

**Acceptance signal:** the `aeat_live` suite runs (not skipped) and passes —
in particular `test_authenticator_live.py` proves certificate health and the
full browser authentication flow at the exact protected resource. Lower-level
handshake success is neither required nor sufficient.

## Item 4 — real-PDF specimens for provisional `declaracion_pdf` extraction profiles (issues #332-#337)

**Verified autonomous surface: exhausted.**

- The `provisional_pending_specimen` acknowledgement mechanism
  (`.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`, the
  2026-05-26 amendment) is fully implemented and enforced at registry-build
  time: `domain.calculations.registry._validate_extraction_profiles
  .validate_declaracion_pdf_specimen_gate` fails the build for any
  `declaracion_pdf` profile that is neither marked
  `provisional_pending_specimen = true` nor backed by a corpus fixture PDF, and
  the companion `validate_declaracion_pdf_round_trip_gate` fails the build for
  a profile that has a fixture but neither `corpus_round_trip_verified` nor
  `provisional_pending_specimen` is set.
- At HEAD, only ONE `declaracion_pdf` profile carries
  `provisional_pending_specimen = true`: Modelo 202
  Its own in-file comment names the reason precisely: it is the only profile
  using `bbox_anchored` matching (anchor on the printed box number, read the
  value to its right), because the bundled AEAT Diseño de Registro confirms
  the box numbers are printed inline but not their exact on-page position or
  column — a real specimen is needed to confirm (or correct) the anchor
  strategy. The in-file comment also names the tracking issue (#325) for
  real-corpus acquisition for this modelo family.
- The five OTHER modelos named in the commissioning prompt (M036, M232 both
  revisions, M369, M720, M840) do NOT carry the provisional flag at HEAD. Each
  has a corpus fixture PDF under `src/cadrumo/tests/fixtures/justificantes/<modelo>/`,
  each is stamped `corpus_round_trip_verified = true` and
  `verification_source = "synthetic_from_aeat_published_text"`, and each
  fixture's sidecar honestly declares `"provenance": "synthetic_generated"`
  (per `fixture-provenance-declared-in-sidecar`). These profiles use
  `named_label`/`numeric_casilla` matching confirmed against the printed
  casilla numbering already visible in the bundled AEAT Diseño de Registro —
  a strategy the bundled DR alone can validate, unlike M202's `bbox_anchored`
  strategy. They are honestly synthetic-corpus-only, not silently unverified;
  the registry gate would fail the build if they were unacknowledged.
- Modelo 037 (issue #333) is confirmed genuinely wontfix, not a residual gap:
  `core._modelo.Modelo.M037` exists as an enum member with an explicit
  docstring noting it is "retired ... censo simplificada, suppressed by Orden
  HAC/1526/2024" and is a member of `NON_REGISTRY_MODELOS` — no registry
  directory exists for it (`src/cadrumo/_data/registry/aeat/modelos/037` is
  absent) and none may be created; a gate test in
  `core/tests/test_modelo.py` pins this. This is a real-world regulatory
  retirement (AEAT suppressed the form), not application code legacy — the
  `no-legacy-compatibility` carve-out for genuinely-retired-by-AEAT modelos
  applies. Issue #333's body (a 2026-04-22-dated "Definition of Done" asking
  for `formulas/_rulesets` and `models/_citation_registry`) references a
  project structure that predates the current hexagonal layout and is stale.
- A live-gated impersonation-style "confirm this specimen against a live
  fetch" harness is not applicable here: specimen acquisition is inherently a
  physical/manual step (the operator must possess or obtain a real filed PDF
  for each modelo), not something a probe script or a live external call can
  substitute for.

**Small buildable prep landed:** none needed beyond what already exists —
the acknowledgement + gate mechanism is the correct, complete structural
answer; there is no partial automation to add. Attempting to fabricate a
"specimen-like" fixture would violate `fixture-provenance-declared-in-sidecar`
(provenance must be truthfully declared) and would not lift the M202 flag,
since the gate correctly requires `provisional_pending_specimen` removal to be
paired with a real specimen confirming (or correcting) the anchor strategy —
that confirmation cannot be faked without misrepresenting provenance.

**Operator action, per modelo:**

- **Modelo 202 (the one flagged profile):** obtain a real M202 declaración-copy
  PDF (own filing, redacted per the L2/consent-log pattern used elsewhere in
  the corpus, or hash-pinned as an L1 public anchor). Confirm the printed
  layout for casillas `01`, `03`, `04`, `34` matches the `bbox_anchored`
  guessed anchor positions (or correct them), widen the profile to the full
  liquidación casilla set if the specimen supports it, then flip
  `provisional_pending_specimen = false` and set the fixture's sidecar
  `"provenance": "real_corpus"`.
- **M036 / M232 (both revisions) / M369 / M720 / M840:** already build-clean
  and honestly synthetic; a real specimen is optional hardening, not a build
  blocker. If supplied, replace the synthetic fixture, set
  `"provenance": "real_corpus"` in its sidecar, and re-confirm the
  `named_label`/`numeric_casilla` patterns against the real printed labels.
- **Modelo 037:** no action — confirmed wontfix (regulatory retirement); close
  issue #333 as such if not already reflected on the board.

**Acceptance signal:** for a lifted modelo, the registry build (`uv run
--no-sync pytest src/cadrumo/domain/calculations/registry -m unit`) still passes
with `provisional_pending_specimen = false` and a real-corpus-provenance
sidecar in place; `python -m aeat.locales modelo audit`-style provenance
reports (or a direct `rg 'provisional_pending_specimen = true'` sweep) no
longer name that modelo.

## Item 5 — live service-account impersonation test (issue #591)

**Verified autonomous surface: exhausted, and one gap closed as safe prep.**

- All six planned slices for issue #591 are landed at HEAD (commits
  `83b537d64c` core resolver + ADR, `54a15ab1ed` multi-cert source resolution,
  `a8a9692da3` certificate expiry/rotation, `9747eed820` cert-secret backend
  abstraction, `f8e0108b44` per-profile persistence + factory dispatch,
  `daea273b90` ADC-freshness auto-remediation, plus `815e5d8742` locale parity
  and `0ae49c4c4e` which lands the CLI verb family):
  - `adapters.outbound.google._impersonation.GoogleImpersonationConfig` /
    `GoogleCredentialSourceSelection` — strict frozen pydantic records.
  - `resolve_impersonated_credentials()` — real ADC discovery via
    `google.auth.default()`, eager source-credential freshness check
    (`GoogleAuthAdcStaleError` vs `GoogleAuthImpersonationRefusedError`,
    correctly distinguished remediations), real impersonation wrapping and one
    eager `.refresh()` to fail loudly on a misconfigured grant.
  - Per-profile persistence (`GoogleCredentialSourceSelection`, no long-lived
    secret — only the target SA email + scopes) and `build_google_credentials`
    factory dispatch on the persisted selection, defaulting to the existing
    OAuth-Desktop path byte-for-byte when no selection is persisted.
  - CLI verb family: `aeat config google credential-source set|show`
    (registered under `aeat config google`), confirmed live via `--help`
    (renders correct Spanish locale help text; requires an unlocked secure
    profile to run for real, which correctly stopped at the passphrase prompt
    rather than an import/registration error).
  - Locale strings scaffolded and translated across all four catalogues
    (`en`/`es`/`ca`/`hu`), including the two new error codes
    (`FAIL_GOOGLE_ADC_UNAVAILABLE`, `REFUSED_GOOGLE_IMPERSONATION`).
  - Hermetic test coverage: `src/cadrumo/adapters/outbound/google/tests
    /test_impersonation.py` (unit-marked) exercises the real
    `DefaultCredentialsError` failure path (pointing
    `GOOGLE_APPLICATION_CREDENTIALS` at a nonexistent file — a genuine,
    hermetic reproduction, no mocks) and every typed-record contract;
    `test_session_store_roundtrip.py` and `test_factory.py` cover persistence
    and dispatch; `test_google_credential_source_cli.py` (integration-marked)
    covers the CLI surface. All green at HEAD (impersonation-specific
    modules pass in isolation).
- The ADR (`.vault/adr/2026-07-04-google-sa-impersonation-adr.md`) and the
  module docstring both explicitly name the one deferred piece: "a live-gated
  integration test analogous to the certificate-source live probes", gated on
  `AEAT_LIVE_TESTS_GOOGLE` (the same opt-in the sibling
  `test_oauth_live.py` uses) — deferred because a live IAM token-exchange call
  against a real, provisioned target SA needs real GCP project state this
  environment does not hold.

**Small buildable prep landed:** a live-gated test skeleton,
`src/cadrumo/adapters/outbound/google/tests/test_impersonation_live.py`
(`pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]`),
mirroring `test_oauth_live.py`'s established shape exactly. It skips
unconditionally without `AEAT_LIVE_TESTS_GOOGLE=1` (confirmed:
`pytest ... -m aeat_live` → `1 skipped`) and, once opted in, resolves the
target principal from a new `AEAT_IMPERSONATION_TARGET_PRINCIPAL` environment
variable, calls `resolve_impersonated_credentials()` for real, and asserts the
minted credential is valid, unexpired, and carries a token — the exact
residual the ADR names, now committed and ready for the operator to exercise.
This closes the "author the live test" portion of the residual; only running
it against a real SA remains.

**Operator action:**

1. Provision a target service account in a GCP project and grant the ADC
   identity on this host `roles/iam.serviceAccountTokenCreator` on it
   (`gcloud iam service-accounts add-iam-policy-binding
   <target-sa-email> --member=<adc-identity> --role=roles/iam.serviceAccountTokenCreator`).
2. Ensure ADC is discoverable on this host (`gcloud auth application-default
   login`, or `GOOGLE_APPLICATION_CREDENTIALS` pointed at a service-account
   key, or an attached workload identity).
3. Run:

```
AEAT_LIVE_TESTS_GOOGLE=1 AEAT_IMPERSONATION_TARGET_PRINCIPAL=<target-sa-email> \
  uv run pytest -m aeat_live src/cadrumo/adapters/outbound/google/tests/test_impersonation_live.py
```

**Acceptance signal:** the test passes (not skipped), proving a real,
short-lived, valid impersonated access token was minted for the named target
principal — no error, and no unrelated `GoogleAuthAdcStaleError` or
`GoogleAuthImpersonationRefusedError` was raised.

## Non-outward prep landed while preparing this runbook

- `README.md` — added one line to "Getting help" cross-linking `SECURITY.md`
  for vulnerability reports (item 2).
- `src/cadrumo/adapters/outbound/google/tests/test_impersonation_live.py` — new
  live-gated (`aeat_live`, skip-by-default) test closing the "author the live
  SA-impersonation test" portion of item 5's residual.

Verified before landing: `uv run --no-sync pytest --collect-only -q src/cadrumo`
collects cleanly (12,560 tests, 0 errors); the new live test collects and
skips correctly without opt-in; `ruff check` is clean on the new test file;
the impersonation focused suites pass. No outward action (push, tag, publish, GitHub setting
change, live external call) was taken.
