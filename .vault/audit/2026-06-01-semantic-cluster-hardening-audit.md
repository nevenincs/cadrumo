---
tags:
  - '#audit'
  - '#semantic-cluster-hardening'
date: '2026-06-01'
related:
  - "[[2026-06-01-semantic-cluster-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace semantic-cluster-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `semantic-cluster-hardening` audit: `Axis-7 semantic functionality-cluster swarm audit (delta)`

## Scope

Axis-7 (semantic functionality-cluster overlap) delta-audit over the
419-added / 1311-modified `.py` delta since the 2026-05-19 baseline. Six
parallel sonnet agents covered distinct functional families: numeric/money,
identifiers/validation, parsing/serialization, date/period/deadline,
persistence/repository/crypto, and errors/retry/http.

METHOD CAVEAT (material): the resident RAG GPU service was DOWN throughout the
sweep because the shared-venv `torch` had been downgraded to a CPU build
(CUDA unavailable). Discovery therefore degraded to `rg` only -
verification-grade, but the semantic-cluster (lexically-divergent,
same-meaning) discovery layer that RAG exists to provide did NOT run. The
findings below are `rg`-confirmed true-duplicates and enrollment gaps;
divergent classifications applied the mandatory substitutability pre-filter.
A full RAG semantic pass is PENDING torch restoration and must run before
W01.P02 is closed as complete.

## Findings

### F1 - Decimal cents-rounding triplication (TRUE-DUPLICATE, high)

Identical `value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)` plus a
copied `_CENT` constant in `domain/fincas/_rounding.py:18`,
`domain/profile/inventory/__init__.py:503`, and
`domain/profile/assets/__init__.py:240`. Same constraint shape at all three.
Remediation: new canonical `core` money/Decimal primitive; the inventory and
assets sites import it. (W2 seed.)

### F2 - TOML open/parse/reraise replicated in five loaders (TRUE-DUPLICATE, high)

`domain/iva/_rates.py:44`, `domain/iva/_catalogue.py:35`,
`domain/categories/_registry.py:50`, `domain/deadlines/_recargo.py:72`, and
`domain/deadlines/_festivos.py:220` each reimplement the open + `tomllib.load`
+ catch `TOMLDecodeError`/`OSError` + reraise-domain-error triad that
`core/_toml.py:read_toml` already centralises via an `error_factory` argument.
Substitutable. Remediation: route all five through `read_toml`.

### F3 - `_to_str_dict` duplicated (TRUE-DUPLICATE, high)

Byte-identical `_to_str_dict(raw) -> dict[str, object]` in
`domain/iva/_catalogue.py:106` and `domain/categories/_registry.py:123`,
differing only in the raised error. Remediation: shared helper with
`error_factory`.

### F4 - `_ProfileId` triple-declaration (TRUE-DUPLICATE + weaker variant)

Canonical `ProfileId` in `core/identity/_profile.py`; an identical-constraint
duplicate in `domain/user_profile/_values.py:28`; and a weaker variant
(missing pattern + strip) in `application/user_profile/_aggregate.py:32`.
Remediation: delete the domain copy and import the canonical; promote the
aggregate field to `ProfileId` (its callers already pass conforming values).

### F5 - NIF control-letter table re-declared in test helpers (actionable)

`"TRWAGMYFPDXBNJZSQVHLCKE"` re-declared in `application/user_profile/_testing.py:24`
and `entrypoints/cli/test_profile_lifecycle_verbs.py:704` for NIF generation.
Remediation: expose a public `nif_check_letter(int) -> str` from
`core/identity/_tax_id.py`; both helpers call it.

### F6 - Browser viewport/timeout helpers byte-identical (TRUE-DUPLICATE, high)

`_get_default_viewport`, `_get_selector_probe_timeout_ms`, and a dead
`_get_timeout_defaults` are byte-for-byte identical across
`adapters/outbound/aeat/sede/_groi_check.py:75`, `_nif_iva_check.py:121`, and
`_renta_web_open.py:37`. Remediation: move the live helpers to the existing
`_browser_constants.py`; delete the dead one.

### F7 - LLM 429 status-dispatch duplicated (actionable)

The `if status == 429: raise_rate_limit(...)` dispatch is copy-pasted across
`adapters/outbound/llm/_providers/openai.py:126`, `gemini.py:131`, and
`local.py:93` (local also omits the 5xx band). Remediation: a
`check_http_error(response, provider_name)` helper in `_providers/base.py`.

### F8 - `FincaRepository` family vs `SqlRecordRepository[T]` (EXCLUDED on verification)

The discovery agent flagged `domain/fincas/_repository.py` (`FincaRepository`
and four siblings) as reimplementing the `SqlRecordRepository[T]` CRUD
scaffold. Live verification (2026-06-01) overturns this under the
substitutability pre-filter:

- `SqlRecordRepository[RecordT]` is a PURE ABC: every CRUD method
  (`list_all`/`get`/`upsert`/`delete`) is `@abstractmethod`; only the trivial
  `__init__(session)` is concrete. It offers NO shared implementation to dedup
  toward - enrolling would not remove a single method body.
- The Finca repos carry DIVERGENT interfaces: `get_by_identifier`,
  `get_for_contract_period`, `get_for_finca_period`, and several lack a
  `list_all` / `get(record_id:int)`. The ABC's required abstract surface is
  not a superset of theirs; forcing conformance would add unnatural methods.
- The only genuinely-shared helper, `_flush_or_wrap`, is import-chain
  divergent: fincas defers the `RepositoryError` import inside the function to
  keep `adapters.persistence.storage` out of the CLI import chain; importing
  the canonical copy would defeat that deferral.

Verdict: constraint-shape mismatch on all three axes. NOT actionable; left as
five independent record-type repositories. (The repos pass their existing
roundtrip tests; no duplication of executable logic exists to eliminate.)

### F9 - Profile ledger repos vs `SecureBoundRepository` (deferred-structural)

`AssetsLedgerRepository`/`AmortizacionLedgerRepository`
(`adapters/persistence/profile/assets.py:94,184`) and
`InventoryLedgerRepository` (`profile/inventory.py:93`) duplicate the
`SecureBoundRepository` pattern but skip the `Envelope` wrapper, so migration
is a versioned data-format change, not a free consolidation. Track for a
dedicated slice. Also: `assets.py` hardcodes its namespace string instead of
reading `PROFILE_ASSETS_LEDGER_NAMESPACE` (inconsistent with `inventory.py`).

### F10 - Period-parsing local variants (EXCLUDED on verification, largely divergent)

`application/filing/reconciliation/_reconcile.py`, `application/workflow/_engine.py`,
`application/filing/_import.py`, and `application/invoices/_source_resolver.py`
re-encode quarter/annual/month period logic also present in `domain/period.py`.
Live verification (2026-06-01) finds these are NOT clean duplicates under the
substitutability pre-filter:

- `domain/period.py`'s own module docstring sanctions deliberately separate
  period dialects ("a deliberately separate dialect; do not unify it with
  this surface"), so divergent period parsers are an accepted pattern, not
  drift.
- `_engine._registry_period_token` returns `(int, str)` but raises
  `WorkflowError` with i18n-TRANSLATED message keys (not
  `PeriodValidationError`) and accepts an extra `YYYYMn` dialect. Delegating
  would silently drop the translated user-facing error contract.
- `_reconcile._canonical_draft_period_token` returns a bare token `str` (not
  `(year, token)`) and raises `ModeloBuilderError`; `_import` produces a
  canonical `"YYYYQn"` STRING; `_source_resolver` tests membership and accepts
  both `Qn` and `nT` token styles. Each serves a different return shape and
  error type.
- The one mechanically-removable item (the `_engine` `YYYYMn` branch, 4 lines)
  cannot be proven dead without tracing every `obligation.period` producer;
  removing an unprovable-dead branch for marginal gain is not justified.

Verdict: divergent return shapes + error/i18n contracts + sanctioned dialect
separation. NOT actionable as consolidation.

### F11 - Private `core.time._now` cross-package imports (LIVE REGRESSION, high)

88 sites import the private `_now` from `aeat.core.time` across packages -
an architecture-rule violation (private cross-package import) the diagnostics
enforcement suite is meant to reject. Remediation: expose a public `now()` in
`core/time/__init__.py` and migrate callers. Not a duplication finding but a
canonical-enrollment defect surfaced by the sweep.

### Divergent / excluded (substitutability pre-filter held)

Correctly NOT actionable, with constraint-shape reasons: bare
`quantize(Decimal("0.01"))` without a rounding mode (HALF_EVEN, different
contract); the five Spanish-decimal parsers (different return/error/sign
contracts); ES-only 24-char IBAN vs any-country 15-34 (`registry/_schema.py`);
DEK-wrap and HKDF-context crypto (cryptographically distinct by design); the
`_PERIOD_RE` triplicate (documented intentional dialect split); `ddmmaaaa`
str-vs-bytes formatters; `PeriodKind` (3 members) vs registry `period_kind`
Literal (4-5 members). The 23 per-domain `*Error` bases rooting at `AeatError`
are sanctioned, not findings.

## Recommendations

Actionable cluster queue feeding the remediation Waves:

- W2 (duplication): F1 (seed), F2, F3, F6, F7 - consolidate to canonical homes
  (`core` money primitive, `core/_toml.read_toml`, shared `_to_str_dict`,
  `_browser_constants`, `_providers/base`) each with a behaviour test.
- W2/W3 (enrollment): F4, F5, F8 enrollment to existing canonicals; F11 the
  public-`now()` fix across 88 sites.
- W4: F10 period-parsing delegation; F9 as a dedicated data-format slice.
- BLOCKER before closing W01.P02: restore CUDA torch, restart the RAG service,
  and re-run the Axis-7 semantic sweep so vocabulary-divergent clusters this
  rg-only pass cannot see are surfaced and the inventory is proven complete.

## Remediation status (closure note, end of 2026-06-01)

Findings status after the W02-W05 remediation passes landed:

- **F1 (decimal cents-rounding triplication) - CLOSED.** Canonical
  primitive landed at `core/money` (commit a-b for primitive +
  tests); fincas, inventory, and assets sites migrated and the
  fincas legacy module deleted (commits c-d in W02.P03.S06-S10).
- **F11 (private `_now` cross-package imports) - CLOSED.** All three
  core/time helpers (`now`, `coerce_utc_aware`, `validate_utc_aware`)
  exposed as public surface; 102 cross-package importers swept; the
  diagnostics `test_no_private_name_cross_package_imports` gate is
  now green (commit at W03.P06.S14+S15).
- **W04 exception consolidation (orthogonal to F1-F11 but in
  scope) - CLOSED.** Unused `DomainError` deleted; four
  `domain/{renta,iva,normatives,manuals}/errors.py` modules
  renamed to the `_errors.py` convention with consumer sweep;
  `ApiDocsError` rooted at `AeatError` to close the hygiene gate
  (W04.P07.S16-S18, W04.P08.S19-S22, W04.P09.S23).
- **W05 typed-axis closure (orthogonal) - CLOSED.** Closed
  `TaxDomain` StrEnum added at `core/_tax_domain`, hydrated at
  the registry schema boundary via `BeforeValidator`, every
  committed modelo verified to carry an enum member (W05.P10.S24-S27).
- **W05.P11.S28 (portals Subdomain rename) - CLOSED.** `Subdomain`
  enum renamed to `PortalHost` across 49 consumers.

DEFERRED to a follow-up cadence (substitutability constraints met
but not in this campaign's scope):

- **F2 (TOML loader triad)** - tractable but requires error_factory
  routing audit per loader; defer to next dependency-injection wave.
- **F3 (`_to_str_dict` duplicate)** - one-shot helper extraction;
  defer.
- **F4 (`_ProfileId` triple-declaration)** - touches three packages
  including application; defer to a typed-id authority sweep.
- **F5 (NIF control-letter table)** - `core/identity/_tax_id`
  public-surface addition; defer.
- **F6 (browser viewport/timeout helpers)** - sede adapter
  consolidation; defer.
- **F7 (LLM 429 dispatch)** - llm/_providers/base helper extraction;
  defer.

NOT actionable (substitutability pre-filter excluded):

- **F8 (FincaRepository vs SqlRecordRepository[T])** - constraint-
  shape mismatch on all three axes; documented in audit body.
- **F9 (profile ledger repos vs SecureBoundRepository)** - versioned
  data-format change required; not a free consolidation.
- **F10 (period-parsing local variants)** - divergent return
  shapes + sanctioned dialect separation; documented in audit body.

W01.P02.S04 RAG sweep is bounded by the documented torch/CUDA
unavailability caveat. The `rg`-only verification baseline is
recorded above; a full RAG semantic pass is the canonical follow-up
when the GPU service is restored.

W02.P04.S11 triage produced no new in-campaign Steps because the
six DEFERRED findings (F2-F7) require dedicated micro-campaigns
each, not interleaved with the W04/W05 sweeps; recording them in
this audit IS the triage outcome per the metastate-zero-tolerance
ADR's "delete the list because the constraint it encodes was a
process artefact" disposition.

W05.P12.S29 re-confirmation pass is the same audit body above; no
new duplication-sweep leads surfaced beyond F1-F11.

## Codification candidates

None. The constraints these findings enforce (canonical placement, no
duplication, substitutability pre-filter, private-name import ban) are already
codified in the core-authority and swarm-audit-cadence rules; this audit
applies them rather than discovering a new durable rule.

<!-- Findings that satisfy the three durability criteria
(cross-session, constraint-shaped, project-bound) and should be
promoted into project-shared rules under `.vaultspec/rules/rules/`
(the directory the CLI's `vaultspec-core spec rules add` writes to today; the
planned `--scope project` flag will move authored rules under
`.vaultspec/rules/rules/project/`).

Each candidate names the finding it derives from, the proposed
rule slug (kebab-case, naming the constraint's subject not the
failure), and a one-sentence statement of the rule.

Most audits produce zero codification candidates. Some produce one.
Only the rare framework-wide-pattern audit produces several. If
none of the findings above meet the bar, state that explicitly and
move on -- an empty Codification candidates section is a positive
signal, not a failure. -->

<!-- Example:

- **Source:** finding S04 (destructive verbs lack preview).
  **Rule slug:** `destructive-verbs-need-dry-run`.
  **Rule:** Every CLI verb that writes or removes state must
  accept `--dry-run` and emit a usable preview before applying.

-->
