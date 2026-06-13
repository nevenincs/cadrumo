---
tags:
  - "#audit"
  - "#aeat-cli-userdocs-hardening"
date: 2026-06-05
modified: '2026-06-05'
related:
  - "[[2026-06-04-aeat-cli-userdocs-hardening-plan]]"
  - "[[2026-06-04-aeat-cli-userdocs-hardening-adr]]"
  - "[[2026-06-04-aeat-cli-userdocs-hardening-research]]"
---

# `aeat-cli-userdocs-hardening` General-Audience Prose Audit

This audit records the 2026-06-05 content rollout pass over beginner and route
documentation. The pass focused on places where the docs used concrete internal
implementation language before giving a general reader a plain task model.

## Identification method

The audit used three inputs:

1. A text scan over user-facing Markdown for implementation nouns and support
   escape hatches: `work unit`, `calculation revision`, `registry revision`,
   `internal audit IDs`, `checksum`, `SHA-256`, `artifact`, `glossary`,
   `issue tracker`, `Missing Handbook Surfaces`, and related terms.
2. A zero-context editorial review of `docs/index.md`, `docs/getting-started.md`,
   `docs/how-to/index.md`, and `docs/tutorials/index.md` against the
   VaultSpec documentation prose and Diataxis rules.
3. A local Diataxis review of whether each occurrence belonged in a beginner
   route, task recipe, tutorial, explanation, or reference page.

Matches were not treated as automatic defects. A term was flagged only when it
appeared before the reader had a plain-language reason to care, replaced a
normal user outcome, or sent the reader to a glossary, issue tracker, or backlog
list instead of helping them continue.

## Findings applied in this pass

- `docs/getting-started.md` opened with "artifacts" and introduced work units
  and calculation revisions as core beginner concepts. The page now opens with
  the user outcome and uses "filing target" and "draft calculation" before
  linking to the advanced filing-spine explanation.
- `docs/tutorials/index.md` used an internal-ID title, sent readers to the
  glossary before the tutorial story started, exposed a repository fixture path
  as a prerequisite, used "Provision your tax form", and recorded the local
  filed marker before export. The page now uses a learning-outcome title,
  defines the needed terms inline, says the sample transaction file is included
  with the tutorial, starts the tax form in plain language, and exports before
  discussing the local marker.
- `docs/how-to/index.md` exposed backlog as "Missing Handbook Surfaces" and used
  title-case headings plus implementation-heavy route copy. The public backlog
  section was removed, headings were normalized to sentence case, and the
  standard workflow route now describes the user outcome.
- `docs/how-to/quickstart.md` used work-unit and revision wording in the main
  path. The main steps now say "start the local workspace", "save the draft",
  and "verify the draft"; exact IDs remain described as advanced ambiguity
  tools.
- `docs/how-to/reconcile.md` opened with "local work unit". The opening now
  uses "local filing record" and keeps exact work-unit IDs only in the advanced
  ambiguity sentence.
- `docs/how-to/classify-with-llm.md`, `docs/how-to/quickstart.md`, and
  `docs/how-to/reconcile.md` no longer route general readers to the issue
  tracker or glossary from their next-step blocks.

## Remaining tracked risks

- Lifecycle pages still contain necessary advanced terms such as work units,
  calculation revisions, registry revisions, selectors, and exact IDs. These
  are now tracked under plan step `W05.P09.S56` for a dedicated lifecycle prose
  rewrite, not treated as drive-by copy edits.
- The hidden Sphinx toctree still includes `glossary` as a project page. The
  public route copy no longer depends on it, but replacing glossary lookup with
  search/reference-backed term discovery remains a navigation backlog item.
- Model-specific pages (`modelo-303.md` and `modelo-390.md`) still expose
  internal audit IDs and revision wording. They need page-level
  `vaultspec-documentation` review before broad edits.
