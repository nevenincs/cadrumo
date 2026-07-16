---
tags:
  - '#audit'
  - '#protected-browser-certificate-auth'
date: '2026-07-16'
modified: '2026-07-16'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace protected-browser-certificate-auth with a kebab-case feature tag, e.g. #foo-bar.
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

# `protected-browser-certificate-auth` audit: `ADR-to-code hard-cut reconciliation`

## Scope

Audit the accepted protected-browser certificate-auth decision against its
research, the superseded certificate-auth corpus, the implementation and tests,
and the complete branch diff. The review specifically checks that the single
protected Playwright proof remains fail-closed; retired handshake, marker,
backend, configuration, compatibility, and borrowed-session paths are absent;
typed credentials and encrypted persistence remain intact; and browser
ownership has deterministic, retryable teardown.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### {topic} | {level} | {summary}

     followed by a paragraph carrying the detail. {topic} is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### reset-journal-error-registry | high | Reset journal exceptions cannot import

`ConfigResetJournalError` now derives from `AeatError`, but the error-code
registry has no matching declaration. Import-time subclass binding raises
`ValueError`, breaking the reset repository and reset workflow test modules
before collection. This is a branch-wide publication blocker even though it is
adjacent to, rather than part of, the certificate-auth hard cut.

## Recommendations

Resolve every critical, high, or medium finding before publication. Retain low
findings only when they are explicitly evidenced as non-blocking and do not
reintroduce a parallel authority or compatibility path.
