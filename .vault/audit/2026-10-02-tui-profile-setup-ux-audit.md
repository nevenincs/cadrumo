---
tags:
  - '#audit'
  - '#tui-profile-setup-ux'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:01c9326f9316b005086c683762fd9fd2c327b334d0ac602d7ea7e8e4d8df7434'
related:
  - "[[2026-10-02-tui-profile-setup-ux-plan]]"
  - "[[2026-08-11-tui-interface-adr]]"
  - "[[2026-08-19-profile-setup-completion-adr]]"
---

# `tui-profile-setup-ux` audit: Profile setup and editing UX review

## Scope

Review S01 and S02 together from base `5f721a1d2e` through `ac028f030d` and the final profile working-tree changes. Scope covers registration, setup navigation, required question editing, explicit review and guarded completion, ordinary profile editing, four locale catalogues, and development capture fixtures. Accepted interface D6 and the accepted profile setup completion decision govern the change. Persistence schemas, requirement policy and filing readiness are unchanged.

## Findings

### integrated-flow | low | Scoped code review passes; final capture verification pending

The application projection remains the source of required answers, conditional requirements, saved values and setup completion. Presentation stages neither acquire data nor persist navigation state. Optional acquisition has an explicit Skip action; optional fields remain editable and do not block completion. Required blank answers stay in their question with a correction message. Cancel and Previous preserve saved answers. The full walk passes at 80x24 and 160x60 and reaches Review before the explicit Finish action; the completion shortcut now observes the same Review boundary. Success is shown only after a matching, completed projection with no missing required answers returns from the real completion door. Detail help is collapsible while the prompt, requirement status and actions remain available. Creation copy is shorter and its password/recovery explanation remains accessible in a localized disclosure.

Verification: the owning profile, registration and inventory selection passed 162 tests (exit 0), with a subsequent 23-test integration selection passing the final shortcut and help changes (exit 0). Results are in the local test-run logs dated 2026-10-02, runs `20261002T041840.675209Z-pytest-83584-834ff332` and `20261002T042235.844245Z-pytest-30536-b1bb1238`. Ruff lint, format and ty pass on the six S02 Python paths. Real encrypted synthetic capture fixtures prove saved editing, incomplete questions, completion, and fresh provisioning without mocked projections. The final four-language PNG matrix is still rendering, so the integrated verdict is PENDING until it completes and its manifests and served images are checked.

### baseline-gates | low | Repository-wide locale and vault checks retain unrelated failures

All four locale catalogues report zero missing, repair, or unresolved required values and zero placeholder mismatches. New setup and registration keys are enrolled. The locale command exits 1 for existing catalogue inventory issues, terminology translations and unavailable spelling tooling. An obsolete onboarding Ready key was detected and removed through the catalogue CLI after its call sites were replaced. The earlier repository-wide vault check reports 27 errors and 521 warnings in existing records. No unrelated corpus repair is included. Scoped feature structure and frontmatter are valid; generated ledger annotations and its feature index are repaired through their owning commands when S02 closes.

### final-verification | low | PASS for the integrated profile setup and editing change

The final working tree passes the 162-test owning profile, registration and visual-inventory selection (exit 0, run `20261002T042943.673031Z-pytest-60120-a6b007d2`) and all 39 owning profile/acquisition tests (exit 0, run `20261002T043123.394231Z-pytest-41376-f8ddc548`). Ruff lint, format and ty pass on all six changed S02 Python paths. The plan check exits 0. The final locale report has no findings for changed setup or registration keys; all four required catalogues are complete with zero placeholder mismatches. Repository-wide baseline locale and vault limitations remain as recorded above.

The final captures comprise 104 Spanish frames over 80x24, 120x40, 200x50 and 80x50 in dark and light, plus 26 small frames each in English, Catalan and Hungarian: 182 frames total, covering twelve real profile states and registration. All manifests match the current source fingerprint at both ends, account for the declared matrix, and contain no failures, skipped frames, missing artifacts, stale artifacts, geometry advisories or missing glyphs. PNG and text digests match every recorded file. HTTP state and representative PNG responses from the running review server match the final manifests and PNG digests in all four runs.

Visual inspection covers overview, skippable acquisition, required questions, expanded help, recoverable invalid answers, optional edits, ordinary and saved editing, review and affirmative completion across both appearances and the declared widths. The final editing page collapses optional import by default. Review uses folded saved sections, and Ready avoids a duplicate pinned success notice. No critical or high finding remains. This integrated review is PASS within the authorized presentation and capture scope.

## Recommendations

All scoped recommendations are complete. Keep the named profile runs available in the review server; future profile presentation changes must refresh their relevant capture states. Unrelated global locale and vault backlog remains outside this revision.
