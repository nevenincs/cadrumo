---
name: modelo-locales-cli-authority
---

# Modelo Locale CLI Authority

## Rule

Manage modelo schema-local translation TOML only through `python -m aeat.locales modelo ...`; never hand-edit registry-local `locales/*.toml` files for routine scaffold, set, remove, audit, or coverage work.

## Why

The accepted ADR `2026-06-11-modelo-locales-cli-adr` makes the modelo locale CLI the authoring authority for schema-local labels and help text while preserving legally grounded Spanish schema labels as the fallback. The review log `2026-06-11-modelo-locales-cli-code-review-audit` also records a real migration failure caught during CLI-routed scaffold: direct TOML edits would have bypassed the regression test and recovery path. This rule prevents stale keys, missing keys, accidental Spanish-schema mutation, and fragmented campaign tracking.

## How

- Good: run `python -m aeat.locales modelo coverage en 130 2019-y-siguientes` before and after translation work to record per-modelo progress.
- Good: run `python -m aeat.locales modelo scaffold ca 303 2023-y-siguientes` to align a selected schema-local catalogue without overwriting translated leaves.
- Good: run `python -m aeat.locales modelo set hu 130 2019-y-siguientes labels 01 "Bevételek"` to update one translated leaf after registry-key validation.
- Good: leave Spanish schema-local TOML absent unless a future ADR explicitly changes the fallback model; the official Spanish `CasillaDefinition.label` remains the legal source.
- Bad: opening `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/locales/en.toml` in an editor to add or remove keys by hand.
- Bad: treating scaffold placeholders whose value equals the schema key as completed translations.
- Bad: moving official Spanish schema labels into locale TOML or replacing schema `label` values with translated operator-facing text.
