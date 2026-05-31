---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace codebase-solidification with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#codebase-solidification'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-31'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-05-28-codebase-solidification-adr]]"
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `codebase-solidification` audit: `Wave 19 — zero findings across all 9 axes`

## Scope

Wave 19 swarm re-audit of `src/aeat/` (~1530 production Python files) across all nine drift axes established at the inaugural Wave 1 audit. Single consolidated 9-axis pass with mandatory substitutability pre-filter per the swarm-audit-cadence rule. The pass follows W18, which returned zero findings on 8 of 9 axes plus 2 actionable A8 cast-rationale token formalisations (both closed under W18.P50.S638 and W18.P50.S639). The aim is to confirm sustained-clean state and begin the strict three-consecutive-zero-fresh-findings counter that the recurring-hardening-epic ADR specifies as the close condition.

## Findings

**A1 — Centralized exceptions: zero findings.** Every production `raise ValueError` site is inside a pydantic `@field_validator` or `@model_validator` method (exempt by rule — pydantic requires `ValueError` from validators to produce `ValidationError`), inside `aeat.core.errors` registry internals (exempt), or carries a `BROAD-EXCEPT-RATIONALE-*` token (W17 closures at `core/parsing/_dates.py:59,90,105` confirmed in place). No bare `raise Exception` or `raise RuntimeError` in production code outside exempt zones.

**A2 — Centralized logging: zero findings.** Every non-test production stdlib-logging site is either the canonical `core/logging.py`, a documented circular-import survivor (`core/errors/_registry.py` aliased as `_logging_stdlib`, `entrypoints/cli/_stdio.py`, `entrypoints/cli/_log_levels.py`), or carries a `LOGGING-STDLIB-RATIONALE-*` token. The `sede/_browser_stage.py` import is `TYPE_CHECKING`-only with zero runtime exposure.

**A3 — Centralized locale: zero findings.** No bare `click.echo` or `print(` in operator-facing CLI production paths. Internal validator errors and `MACHINE-FORMAT-RATIONALE-*` sites are exempt by rule.

**A4 — Pydantic boundary models: zero findings.** Every `dict[str, Any]` at persisted-record, wire-payload, configuration, CLI input, MCP message, or LLM response boundary carries an exemption marker (`ANY-RETURN-RATIONALE-*`, `KWARGS-ANY-RATIONALE-*`, `ADAPTER-INTERNAL-ALIAS-RATIONALE-*`). W17 closures on Google OAuth staging and W16 closures on pre303 staging and invoices import staging both confirmed.

**A5 — Helper duplication: zero findings.** `format_decimal`, `coerce_decimal`, `_round_to_cents`, `file_stat_fingerprint`, `storage_path`, and the parsing helpers are each defined exactly once in their canonical homes. The substitutability pre-filter rejected the five W17 audit candidates as legitimate domain-specific wrappers carrying domain error translation or extended token sets; no shadow implementations have been introduced since.

**A6 — Stubs and dead code: zero findings.** `Protocol` and `ABC` `@abstractmethod` sites are exempt. `ResourceCacheRepository._load`/`all` and `_SecureRepository.extract_identifier` are intentional template-method-on-concrete-base extension points with explicit "subclasses MUST override" docstrings.

**A7 — Hardcoded values and enum bypass: zero findings.** `DEFAULT_CURRENCY` is the canonical `"EUR"` source; `Literal["EUR"]` annotations are type-system constraints not value defaults. `LATIN_1_ENCODING`, `UTF_8_ENCODING`, and `BOE_ENCODING_CHOICES` are the canonical encoding constants; the residual `"utf-8"` literals are serialization-call arguments not configuration. `CLASSIFIED_BY_MANUAL` closed the last enum-string-literal site in W16. The year literal `2025` inside `resolve_category_profiles(2025)` is documented as a corpus-year selector mapping to the named `CATEGORY_PROFILES_2025` constant in the resource-management-api audit and is exempt by prior review.

**A8 — Typecheck escape hatches: zero findings on canonical surface.** Every `cast()` site carries a `CAST-RATIONALE-*` token (W18 closed the last two prose-but-not-token sites at `_streams.py:155` and `_engine.py:1270`). Every `-> Any` return position carries `ANY-RETURN-RATIONALE-*`. Every `**kwargs: Any` site is covered by `KWARGS-ANY-RATIONALE-*`. The 77-site bare `# type: ignore` corpus remains a known structural gap awaiting a separate `TYPE-IGNORE-RATIONALE-*` inventory ratchet; it was deferred under W17 and is not actionable in this pass.

**P09 — Test-suite semantic integrity: zero findings.** All `pytest.skip` calls are behind `AEAT_LIVE_TESTS_ENABLED` or `AEAT_LLM_ANTHROPIC_API_KEY` live-test gates allowlisted in `test_no_skip_xfail.py`. The single `unittest.mock.patch` site in `test_except_clause_narrowing.py` is the documented exception-narrowing fixture allowlisted in `test_mock_inventory.py`. No tautological calculation assertions, no shape-only `assert is not None` as final value-assertion, no `assert True` or `assert 1 == 1`.

## Recommendations

The strict zero-fresh-findings counter advances to **1 of 3** required by the recurring-hardening-epic ADR close condition. Continue the cadence with Wave 20 (second consecutive confirmation) and Wave 21 (third consecutive). If both return zero across all nine axes, the epic close condition is met and the campaign may be archived via the feature-archive command with a closing audit summarising the full nineteen-wave trajectory.

The 77-site bare `# type: ignore` corpus should be addressed in a follow-up campaign rather than reopened under this epic. The proper sequence is to land an inventory ratchet (`test_type_ignore_rationale_markers.py` modelled on `test_cast_rationale_inventory.py`), enrol the existing sites with a `_KNOWN_VIOLATING_LINES` allowlist analogous to the W11 UTF-8 ratchet pattern, then drive the allowlist toward empty in incremental waves of a successor epic.

The substitutability pre-filter introduced after the W11 PROMOTE-001 false-positive lesson and explicitly briefed into every subsequent audit dispatch is functioning as intended. W17 rejected 7 of 12 candidates by the pre-filter; W18 rejected 2 of 4; W19 produced zero candidates requiring rejection because no false positives reached the report stage. The pre-filter rule in `aeat-swarm-audit-cadence.md` is durable repo-level guidance and should be preserved.
