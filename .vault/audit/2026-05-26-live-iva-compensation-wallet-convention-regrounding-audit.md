---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---



# `live-iva-compensation-wallet` Code Review

CONVENTION-W10-SCOPE-001 | PASS | W10 plan wave added for repository-wide convention regrounding

The wallet plan now contains an explicit W10 wave for codebase convention
regrounding. The wave tracks the requested repository-level concerns as
first-class execution work: localised user-facing error messages, central AEAT
exception inheritance, exception swallowing diagnostics, centralized settings
and environment boundaries, shared enum/model reuse, duplicate-code hardening,
and non-tautological verification.

The wave is deliberately cross-domain. It applies to SecureStorage repair,
auth sessions, CLI commands, import/export, ledger, invoices, periodic IVA,
yearly IVA summaries, multiyear carry-forward, and AEAT remote-state
reconciliation rather than narrowing the rule to the IVA wallet slice.

CONVENTION-W10-P01-S01-CR-001 | PASS | SecureStorage base reuses central AEAT exception registry

Focused review found no critical or high issues in the W10.P01.S01
implementation. `SecureStorageError` derives from the central `AeatError`
registry pattern, has its own registered error code, and sits above the
existing `StorageError` and per-bucket lifecycle base. This preserves existing
storage catchers while adding the missing family-level SecureStorage catch
point requested by the operator.

Representative SecureStorage and bucket errors now render from registry locale
keys instead of raw positional detail strings. Tests assert registry binding,
family inheritance, empty positional args for localised representative errors,
safe context payloads, and locale-message resolution. Locale parity and
translation-honesty tests pass.

No live AEAT mutation, quarantine, deletion, import, export, submission, or
remote write behavior was added.

CONVENTION-W10-DISCOVERY-001 | MEDIUM | Several production exception classes still derive outside the central AEAT base

Initial host discovery found remaining production exception families that do
not obviously derive from `AeatError`: calculation wallet input/policy
`ValueError` classes, auth operator `ValueError` classes, bucket domain
`Exception` classes, calc-sheets `TranslationError`, snapshot `KeyError`, and
the workbook-parity internal conversion exception. Some may be intentionally
private implementation exceptions, but the current codebase does not yet carry
a complete reviewed classification.

Tracked by W10.P01.S02. The next execution wave must classify each family as
AEAT user/domain/application error, internal private control-flow exception, or
accepted non-AEAT library boundary. Any user-facing or cross-boundary exception
must migrate to the central hierarchy and registry.

CONVENTION-W10-DISCOVERY-002 | MEDIUM | Broad catches and suppressions need observability classification

Initial host discovery found many `except Exception` and `contextlib.suppress`
sites across config, diagnostics, workflow, CLI, SecureStorage, outbound AEAT,
Google adapters, parsers, and calculation registry code. Many already convert
to typed errors, re-raise, or have comments explaining best-effort cleanup, but
the rule is not yet enforced as a central inventory.

Tracked by W10.P02. The next execution wave must classify broad catches as
typed conversion, expected cleanup, explicit control flow, or likely swallowing.
Likely swallowing sites need at least debug-level logging with redacted context
or a typed diagnostic result.

CONVENTION-W10-DISCOVERY-003 | PASS | Centralized settings already has a partial static guard, but W10 keeps it in scope

Initial host discovery found an existing static test for direct `AEAT_*`
environment reads outside the settings boundary. That means the environment
rule is not completely unenforced today. However, the current W10 scope remains
valid because it must review allowlists, non-AEAT operational variables,
bootstrap exceptions, writes/mutations, and hidden path/config fallbacks across
SecureStorage, auth, repair, live-read, and IVA calculation surfaces.

Tracked by W10.P03. The wave should extend or tighten the existing guard rather
than replacing it.

CONVENTION-W10-P01-S02-CR-001 | PASS | Production bare exception families now route through the central hierarchy

Focused review found no critical or high issues in the W10.P01.S02
implementation. Production exception families that crossed AEAT
application/domain/operator boundaries were migrated away from bare
`Exception` or `ValueError` roots and now derive through `AeatError` or
`DomainError` while retaining builtin compatibility only where callers already
depend on it.

The central registry covers the migrated auth operator, IVA compensation
calculation, bucket domain, and calc-sheets translation families. The new static
exception-base hygiene gate classifies the remaining direct builtin roots as
the central `AeatError`, a structural snapshot `KeyError` mixin with concrete
AEAT subclasses, and a private workbook conversion sentinel caught inside its
backend. Direct discovery now reports no unclassified production bare exception
families.

CONVENTION-W10-P01-S02-CR-002 | PASS | Locale catalogue repair is now executable through the locale CLI

The locale catalogue update for this slice was performed via
`uv run python -m aeat.locales scaffold --sync-locale-parity`, not by
hand-editing locale YAML. The locale CLI now has a dynamic namespace parity
sync path, and `uv run python -m aeat.locales audit` reports all locale files
as clean.

The added parity regression test uses abstract catalogue files and abstract
translation-key values only. It does not declare concrete language surfaces or
language-specific prose, and it asserts before/after catalogue behavior rather
than reasserting the helper's own return value.

CONVENTION-W10-P01-S02-CR-003 | LOW | Locale CLI scaffold placeholders remain operator-readable fallbacks, not complete translations

The locale scaffold path emits abstract placeholder values for newly discovered
keys. The i18n renderer humanises unresolved placeholders, so CLI output does
not leak raw namespace keys, and the translation-honesty test now separates
abstract self-key placeholders from copied English prose. This is acceptable
for the current convention gate, but real translated catalogue text remains a
follow-up localization quality task.

Tracked by W10.P01.S03/W10.P01.S04 for broader user-facing message auditing
and static enforcement.

CONVENTION-W10-P01-S02-CR-004 | PASS | Review regression in locale CLI diagnostics was fixed before handoff

Code review found that routing the locale CLI audit messages through newly
scaffolded `tr(...)` keys initially humanised unresolved placeholders and
dropped diagnostic payload such as filename and drift counts. The CLI now keeps
all messages routed through `tr(...)` while supplying interpolation defaults,
so `uv run python -m aeat.locales audit` again reports each catalogue filename
and status.

No critical or high issues remain open for W10.P01.S02.

CONVENTION-W10-P01-S03-CR-001 | PASS | Live IVA wallet adapter no longer raises raw positional Sede errors

Focused review found no critical or high issues in the W10.P01.S03 wallet
slice. The live IVA wallet adapter now raises wallet navigation and parser
failures with abstract `translated_message` keys instead of raw positional
strings. Wallet auth-gate, representation-gate, execute-gate, missing-table,
row-parse, malformed-year, malformed-amount, and page-shape failures all route
through the IVA wallet adapter locale namespace.

The tests assert the contract without defining concrete language catalogues:
they verify empty positional args, abstract translation-key identity, and
redaction of malformed wallet values from exception strings and context. The
slice did not add any live AEAT mutation, filing, represented-taxpayer action,
quarantine, import, export, or delete behavior.

CONVENTION-W10-P01-S03-CR-002 | PASS | Wallet error context is now redacted for malformed captured values

The prior wallet parser could surface captured row values through f-string
exceptions when AEAT returned malformed wallet cells. The current implementation
records value length and SHA-256 fingerprints rather than the raw value, and
the regression test proves a malformed wallet cell is absent from both the
exception string and structured context.

CONVENTION-W10-P01-REMAINING-RAW-ERRORS-001 | MEDIUM | Raw exception-message construction remains broad outside the wallet adapter

The W10.P01.S03 AST inventory found no remaining raw positional
`SedeNavigationError` or `SedeParseError` construction in the live IVA wallet
adapter, but the broader repository still contains many raw positional
exception messages. The largest clusters are `domain.calculations` (596),
`adapters.outbound` (299), `adapters.persistence` (191), `application.filing`
(81), `application.modelo` (73), `application.ledger` (68),
`adapters.inbound` (61), `domain.transactions` (55), `domain.iva` (54),
`application.live` (53), `domain.modelos` (46), and `domain.invoices` (43).

This is not closed by the wallet-focused slice. W10.P01.S04 must turn the
inventory into an enforceable static gate with an allowlist for internal
validation/control-flow exceptions, while future domain slices migrate the
remaining user-facing boundary errors to registered locale keys or direct
`tr(...)` rendering.

CONVENTION-W10-P01-S04-CR-001 | PASS | Wallet localization boundary now has a static regression gate

Focused review found no critical or high issues in the W10.P01.S04 targeted
gate. The wallet test suite now parses the production wallet adapter AST and
fails if a future `SedeNavigationError` or `SedeParseError` call adds a raw
positional literal or f-string without `translated_message`. This protects the
live IVA wallet read surface from reintroducing unlocalized user-facing error
messages.

The static gate is deliberately scoped. The broader raw-message inventory
remains a medium-severity migration backlog because many legacy internal
validation and registry errors need classification before a repository-wide
allowlist can be enforceable.
