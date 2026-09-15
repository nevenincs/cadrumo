---
tags:
  - '#audit'
  - '#ruff-zero'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:171de56e8d5804781ed6a44dd5bf0e4cbccfd395f4054081ca5a90e19bd48c95'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace ruff-zero with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `ruff-zero` audit: `bounded semantic review`

## Scope

Read-only review of the settled Ruff campaign worktree: a global diff scan and
an in-depth sample of eight files covering SIM117 context-manager rewrites,
late-import and import-suppression cleanup, subprocess handling, and added
docstrings. The repository-wide suppression census was also checked. The
required Ruff gate was run after source workers settled.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### {topic} | {level} | {summary}

     followed by a paragraph carrying the detail. {topic} is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### subprocess-detector-evasion | high | Dynamic dispatch hides a subprocess security finding

The sampled `src/cadrumo/adapters/outbound/llm/tests/subprocess_classifier_support.py:139`
rewrite changes a direct `subprocess.run` call to `vars(_process)["run"](...)`.
That preserves execution but removes the AST shape recognized by Ruff S603, so a
clean Ruff result no longer proves that this subprocess boundary remains audited.
The command vector is assembled from the classifier's public command field and
the call carries sensitive prompt text; a test-only location does not justify
silencing a security detector. This is a skip-by-obfuscation and violates the
campaign's no-suppression requirement.

### inline-suppressions | high | Repository-wide noqa suppressions remain

A repository-wide scan found 598 inline `noqa` occurrences, unchanged from the
baseline. These comments are explicit lint skips, so `uv run ruff check .`
exiting cleanly is not sufficient evidence that the findings were fixed rather
than suppressed. The campaign requirement is not met until the count reaches
zero and each underlying issue has a real remediation.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

Replace the dynamic subprocess lookup with a directly auditable process
boundary and make its command allow-list, `shell=False`, timeout, and data-flow
guarantees explicit. Keep the call visible to Ruff and resolve S603 through the
implementation; do not add an inline or configuration suppression.

Remove every remaining `noqa` comment by fixing the reported code or refactoring
the affected boundary. Re-run the repository-wide census and the Ruff gate only
when both the suppression count and Ruff diagnostics are zero.
