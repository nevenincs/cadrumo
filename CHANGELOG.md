# Changelog

All notable changes to this project are documented here. This file is
maintained by [release-please](https://github.com/googleapis/release-please)
driven locally via `just release` — see [`RELEASING.md`](RELEASING.md) and
[`.vault/adr/2026-04-12-release-please-adr.md`](.vault/adr/2026-04-12-release-please-adr.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Run `just release` to preview the next release. Run `just release-apply`
to land the version bump and CHANGELOG entries on `main` (human-gated,
no push).

## [0.1.0] - 2026-04-12

Initial scaffolding release. Backfilled from conventional-commit history
on `main` through 2026-04-12. Merge commits and non-conventional messages
are omitted.

### Features

- **auth:** PKCS#12 client certificate authentication for AEAT (#8, #58)
- **testing:** synthetic filing-history fixtures + loader (#14, #56)
- **inbox:** AEAT notifications inbox (#46, #55)
- **normatives:** typed BOE-linked Spanish tax normatives catalogue (#45, #53)
- **status:** AEAT live status reader (#43)
- **google-fixtures:** Google Workspace test fixture surface (#13, #29)
- **submission:** dry-run-default filing submission engine (#42, #49)
- **filing:** typed `FilingDraft` + `Modelo130Builder` PoC + CLI (#39)
- **deadlines:** filing-deadline computation engine (#38, #47)
- **manuals:** Manual práctico schema, loader, CLI skeleton, raw-PDF manifests (#25, #35)
- **sync:** self-healing live-to-local sync runner (#11, #37)
- **storage:** scaffold SQLite + SQLAlchemy + Alembic storage layer (#10, #28)
- **browser:** Playwright anti-bot evasion (#16, #26)

### Bug Fixes

- **status:** apply code-review and round-2 findings (#43)
- address review feedback: NFC normalization, type safety, fallback config

### Documentation

- **audit:** PR #28 storage retrospective + reviewer hardening (#32, #40)

### Miscellaneous Chores

- **ci:** add GitHub Actions workflow for Ubuntu/Windows parity (#31, #34) — later superseded when GitHub Actions was permanently disabled on the repo
- **dev-scaffolding:** full `gsuite-bootstrap` pipeline + CLI + doctor (#4, #18)
- base module structure scaffolding (#19)
