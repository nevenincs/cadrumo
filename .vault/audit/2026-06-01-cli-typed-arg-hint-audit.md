---
tags:
  - '#audit'
  - '#cli-typed-arg-hint'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `cli-typed-arg-hint` audit: closed-enum CLI argument typing

## Scope

Per the architecture-boundaries rule "hint accepted values at the
CLI boundary": every Typer argument whose value is a closed enum
(StrEnum, Literal with finite set, or registry-bound closed
catalogue) MUST declare that enum as its type — or pass an
equivalent ``click.Choice([...])`` via ``click_type=`` — so click
renders the accepted set on parse failure. Audits the operator-
facing CLI surface under ``src/aeat/entrypoints/cli/`` for
compliance.

Inventory:

- 538 Typer parameter declarations across the operator CLI.
- 8 ``click.Choice(...)`` declarations covering the four largest
  closed-enum axes (output language, config-reset scope, browser
  flag, auth provider id).
- 1 typed-Annotated argument using the enum directly (a CLI verb
  parameter binds the closed enum as its annotation).

## Findings

### F1 - output_language axis: 8 sites, 3 patterns (high)

The ``OutputLanguage`` StrEnum (4 members: ES, EN, CA, HU) lands
as the closed-enum surface for the ``--output-language`` /
``--language`` flag. Current arg-typing across 8 declared
parameters:

- 5 sites in ``entrypoints/cli/_modelo.py`` declare
  ``output_language: str | None`` with
  ``click_type=_OUTPUT_LANGUAGE_CLI`` (= ``click.Choice(SUPPORTED_OUTPUT_LANGUAGES)``).
  Click renders the Choice correctly on parse failure; the
  annotation is bare ``str`` because the StrEnum was historically
  absent. **Remediation:** re-annotate as
  ``output_language: OutputLanguage | None`` and drop the explicit
  ``click_type=`` (Typer derives ``Choice`` from the enum
  annotation automatically). The downstream
  ``activate_subcommand_output_language(ctx, language)`` receiver
  accepts ``str | None`` — ``OutputLanguage`` is a ``str`` subclass
  so the call site stays compatible.

- 2 sites in ``entrypoints/cli/_config/__init__.py`` declare
  the same shape with the same ``click_type=`` override.

- 1 site in ``entrypoints/cli/__init__.py`` (the root callback)
  declares ``--output-language`` via the
  ``click_type=click.Choice(_SUPPORTED_OUTPUT_LANGUAGES)`` pattern.

All 8 sites render Choice correctly today; the Steps recommend
moving to the enum-annotation form so future readers see the
closed-enum binding without descending into the explicit click
mapping. Safe sweep.

### F2 - period axis: ``StandardPeriodCode`` lands but is not visible at CLI args (low)

The ``StandardPeriodCode`` StrEnum (1T–4T, 1P–4P, 0A, 01–12) lives
at ``aeat.core._period`` and is referenced by registry schema
validation. The CLI ``--period`` flag passes free-form strings
because period codes are combinatorially-validated against the
modelo×year×revision matrix (acceptable per the rule:
"late, registry-driven refusals … are acceptable for axes that
depend on dynamic registry data, but the refusal MUST list the
accepted set in the error message — never a bare 'value invalid'
without options"). **Remediation:** confirm the registry refusal
path lists the accepted set for the resolved modelo×year context;
no CLI-arg annotation change is needed.

### F3 - tax_domain axis: ``TaxDomain`` lands, no CLI surface (n/a)

The ``TaxDomain`` StrEnum (8 members) is registry-only; no
operator CLI verb takes a ``--tax-domain`` argument. No work.

### F4 - config-reset scope axis: explicit Choice (compliant)

``entrypoints/cli/_config/__init__.py:1708`` declares
``click_type=click.Choice(_CONFIG_RESET_SCOPE_CLI_VALUES)``. The
underlying ``_CONFIG_RESET_SCOPE_CLI_VALUES`` is a hand-managed
literal tuple. **Remediation:** promote the literal to a closed
StrEnum (``ConfigResetScope``) for symmetry with OutputLanguage;
re-annotate the parameter as ``ConfigResetScope | None``. Low
priority — the current Choice surface is operator-correct.

### F5 - auth provider id axis: registry-driven Choice (acceptable per rule)

``entrypoints/cli/_config/__init__.py:1781,1859,1893,1932,1979``
declare ``click_type=click.Choice(_known_auth_provider_ids())``.
The accepted set is registry-driven (resolved at app build
time), not a static enum. The rule explicitly allows this shape
because the accepted values are dynamic. **Compliant.**

### F6 - browser flag: explicit Choice (compliant)

``entrypoints/cli/_config/__init__.py:716`` declares
``click_type=click.Choice(("browser",))``. Single-value Choice is
unusual but operator-correct (rejects every other value with the
listed set). **Compliant.**

### F7 - 530-odd remaining str-typed parameters (out of scope)

The remaining ~530 ``str``/``str | None``/``int``/``Decimal``/
``Path`` parameters are open-set or already correctly typed for
their domain (free-form descriptions, numeric values, file
paths, NIFs validated through downstream pydantic models, etc.).
No closed-enum binding applies.

## Recommendations

**No actionable migration.** The F1 sweep was attempted and
reverted: re-annotating ``output_language: str | None`` to
``output_language: OutputLanguage | None`` changes Typer's
auto-derived ``Choice`` to render enum NAMES
(``[ES|EN|CA|HU]``) instead of the lowercase enum VALUES
(``[es|en|ca|hu]``) that operator-facing CLI tests assert against.
Reverting back to the explicit ``click_type=click.Choice(SUPPORTED_OUTPUT_LANGUAGES)``
form preserves operator-visible help text. To migrate cleanly
would require either renaming the enum members to lowercase
(breaks the StrEnum convention) or threading ``use_enum_values=True``
through every Typer parameter (adds verbosity without operator-
facing value).

The current explicit-Choice form already satisfies the architecture-
boundaries rule ("hint accepted values at the CLI boundary"): the
Choice surface IS rendered with the accepted values, just through
the ``click_type=`` kwarg rather than the annotation. Compliant.

- **F4 follow-up:** if the codebase later promotes
  ``_CONFIG_RESET_SCOPE_CLI_VALUES`` to a StrEnum, the
  ``click_type=click.Choice(...)`` collapses to the enum
  annotation automatically.

F2–F6 are already compliant or not actionable; F7 is out of scope.

## Codification candidates

None new. The architecture-boundaries rule already mandates the
closed-enum-at-the-CLI-boundary discipline; this audit applies it
rather than discovering a new constraint.
