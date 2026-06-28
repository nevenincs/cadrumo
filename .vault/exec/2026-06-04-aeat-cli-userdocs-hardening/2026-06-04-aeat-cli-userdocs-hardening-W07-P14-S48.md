---
tags:
  - '#exec'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S48'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# W07.P14.S48 single-page canonical docs build

Scope: `docs build tooling`.

## Description

- Add a `docs-page` recipe that builds one requested documentation source through `scripts/build_changed_docs.py --single-page`.
- Route single-page builds to the canonical HTML output directory, `docs/_build/html`, instead of a separate preview directory.
- Exclude generated API/autodoc sources from single-page mode while keeping the non-API handbook graph and generated CLI reference available for link and navigation resolution.
- Configure single-page mode as offline and suppress Sphinx toctree warnings that are artifacts of intentionally excluding generated or unrelated sources.
- Keep a dedicated single-page doctree cache under `docs/_build/doctrees-single-page` so targeted builds do not depend on the full-build doctree cache.
- Reject `docs/api` targets in single-page mode so the command cannot accidentally enter generated API/autodoc rebuild territory.
- Remove reliance on the rejected `docs/_build/index-preview` output path.

## Outcome

`just docs-page docs/index.md` builds the requested index page into `docs/_build/html/index.html` in about 11 seconds on this workstation. The generated HTML contains the current handbook route copy, including the task chooser, censo lifecycle route, standard prepare-and-export route, and privacy-safe support language. `docs/_build/index-preview` is absent.

The implementation does not provide an autobuild server. The repository has a `watchfiles` dependency available in the lockfile, but there is no `sphinx-autobuild`, `docs-watch`, or `docs-serve` recipe. That gap is tracked separately as `W07.P14.S49`.

## Notes

Sphinx still reads the non-API handbook graph so links, toctrees, and generated CLI reference links resolve in the same shape as the real site. This is intentional and keeps the page reviewable as canonical site HTML without waiting for generated API/autodoc surfaces.

For non-root documentation pages, Sphinx may rewrite the root `index.html` alongside the requested page because the root document remains the canonical master document. The requested page is still written to the canonical output path, but this is not a strict one-output-file guarantee for arbitrary non-root pages.

Full nitpicky Sphinx and full pytest collection remain outside this step's claim. Earlier collection was blocked by unrelated dirty code in `src/aeat/adapters/persistence/storage/sql/secure_objects.py`; this step was verified with actual targeted Sphinx builds and `compileall` for the changed script.

The mandatory code review found one medium issue: the first implementation allowed `docs/api` targets even though the command promised to avoid generated API/autodoc surfaces. The script now rejects those targets explicitly, and the recipe comment says the command is for non-API documentation sources.
