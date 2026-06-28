---
name: docs-rewrite-adr
description: Architecture decision for the public-facing documentation rewrite (README + getting-started + architecture diagram + project-meta smoke test)
type: adr
tags:
  - "#adr"
  - "#docs-rewrite"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-docs-rewrite-research]]"
  - "[[2026-04-12-docs-rewrite-plan]]"
  - "[[2026-05-30-docs-architecture-adr]]"
issue: wgergely/aeat#67
status: superseded
---

# adr: docs-rewrite

> **Superseded (2026-05-30) by the `docs-architecture` documentation
> surface taxonomy and conventions ADR.** This ADR's markdown-only scope
> (it explicitly deferred Sphinx/API docs, a docs site, and translations)
> no longer matches the codebase, and its `tests/test_docs.py` pin was
> deleted. Its surviving intent — that the bootstrap documentation files
> exist — is retained as an interim obligation until the superseding
> epic's conformance test re-establishes the pin. Do not treat the
> decisions below as current authority.

## context

Per `[[2026-04-12-docs-rewrite-research]]`, the project has demoable
end-to-end coverage of the AEAT loop on `main`, but its public face
(README) still documents the GSuite bootstrap from issue #4. A fresh
visitor cannot answer "what does this project do?" or "how do I run
it?" in under 60 seconds.

## decision

1. **Scope is documentation-only.** No `src/aeat/` changes, no new env
   vars, no new Python modules. Only `README.md` (rewrite),
   `docs/getting-started.md` (new), `docs/architecture.md` (new), and
   one project-meta smoke test at `tests/test_docs.py`. `RELEASING.md`
   from #60 is left untouched — it is already authoritative.
2. **README structure** mirrors the issue body: one-line description →
   pre-alpha banner (no CI badge, local-gates-authoritative note) →
   "what it does" → "what it does not do" → quick start (single block:
   `git clone && cd && just bootstrap && aeat setup && aeat workflow
   next` with the in-flight callouts for #59 / #61) → architecture
   table of on-main subpackages → roadmap → contributing →
   license → disclaimer.
3. **getting-started.md** target audience is a Spanish autónomo who
   reads English but does not necessarily write Python. It walks
   prerequisites → install → configure → verify → first run → FAQ →
   next steps. Screenshots are deferred to a follow-up.
4. **architecture.md** ships the data-flow diagram from the issue body
   plus one paragraph per arrow. The diagram must reference at least 5
   on-main subpackages by name (verified in the smoke test).
5. **Project-meta test placement.** `tests/test_docs.py` lives at the
   repo-root `tests/` level, NOT inside any subpackage. This matches
   the existing pattern of `tests/test_config.py` and
   `tests/test_release_config.py`: tests that assert on repo-level
   invariants (config alignment, release-config alignment, doc-file
   presence) live at `tests/`, while subpackage unit tests are
   colocated under `src/aeat/<subpackage>/`. The test carries
   `@pytest.mark.unit`, uses no mocks/patches/stubs, and asserts:
   - `README.md` exists, is non-empty, contains the project name.
   - `docs/getting-started.md` exists, is non-empty.
   - `RELEASING.md` exists, references `just release`.
   - `docs/architecture.md` exists, references at least 5 on-main
     subpackages by name.
6. **No CI badge, no Actions reference.** The README's contributing
   section documents that local gates (`just lint && just typecheck &&
   just test && just hooks`) are authoritative and that GitHub Actions
   is permanently disabled on the repo. No new file under
   `.github/workflows/`.
7. **In-flight callouts.** Quick-start commands that depend on #59
   (`aeat workflow next`) and #61 (`aeat setup`) are annotated with
   "(merging in #59)" / "(merging in #61)" so the README documents
   the *intended* `0.1.0-pre-alpha` state without lying about today.
8. **Disclaimer is non-negotiable.** The README ends with the
   tax-automation disclaimer; the dry-run-by-default rule on
   submission is documented as a feature.

## consequences

- A first-time visitor can answer "what does this do?" and "how do I
  run it?" in under 60 seconds.
- Contributors have a single source of truth for the dev loop, the
  conventional-commits mandate, and the worktree workflow.
- The smoke test pins the four documentation files in place; an
  accidental deletion or rename trips the suite.
- Sibling in-flight branches' territory is untouched.
- Follow-ups: API docs (sphinx/mkdocs/pdoc), docs site, translations,
  CLI screenshots, logo, standalone CONTRIBUTING / SECURITY — all
  deferred per the issue's "out of scope" list.
