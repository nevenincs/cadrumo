---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/audit/ location)
# Feature tag (replace en-es-ca-translation with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#audit'
  - '#en-es-ca-translation'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-28'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related: []
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `en-es-ca-translation` audit: placeholder-antipattern eradication

## Scope

Companion to #553 (hu translation campaign). All 127 CLI translation keys
across `en.yml`, `es.yml`, and `ca.yml` that carried their own dotted-path
as value (placeholder antipattern) were identified and replaced with real
translations. hu was used as the truth-anchor throughout.

Starting missing count: 127 (ca: 44, en: 43, es: 40).

## Findings

All 127 keys resolved. Final count: 0 missing entries confirmed by
`audit_cli_translations()`.

Sections translated:

- `cli.app.modelo.aggregate` — json_validation_error (en/es/ca)
- `cli.app.modelo.export.errors` — no_exportable_revision (en/es/ca)
- `cli.app.modelo.iva_wallet` — 10 seed_* keys (en/es/ca, some es already present)
- `cli.app.modelo.project` — 7 keys (en/es/ca)
- `cli.app.modelo.project_help` — (en/es/ca)
- `cli.app.modelo.work` — causante_ccaa_help (en/ca; es already present)
- `cli.config.profile` — import_invalid_bundle, import_label_taken_different_id, import_uuid_collision (en/es/ca)
- `cli.ledger.classify` — reaffirm_help, reaffirmed (en/es/ca)
- `cli.overview.calendar` — show_suppressed_help (en/es/ca)
- `cli.review.labels` — legal_refs (en/es/ca)
- `cli.review.queue` — explain_help (en/es/ca)
- `cli.review.show` — explain_help (en/es/ca)
- `cli.root` — 12 keys (app_app_help, app_help, app_help_help, debug_help,
  detail_help, format_help, help_help, language_help, profile_help,
  quiet_help, startup_import_error, unavailable_app_help, verbose_help,
  version_help) (en/es/ca)

No ambiguous keys parked for human input. All keys had sufficient context
from the `default=` argument in the `tr()` call site and/or the hu value.

## Recommendations

No follow-up required. The antipattern surface is fully eradicated for the
three locales in scope. Monitor with `audit_cli_translations()` on future
locale additions to prevent re-introduction.
