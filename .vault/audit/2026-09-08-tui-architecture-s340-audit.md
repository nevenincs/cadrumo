---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:690d50ba95dbd99d6e0ce737f33b3015184e12359c73d89f24e8274ec594b111'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
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

# `tui-architecture` audit: `S340 supervised Google Sheets export`

## Scope

<!-- What was audited and why -->

The supervised Google Sheets export command, its terminal error projection, effect truth, asynchronous transport boundary, and journal-and-lease acceptance evidence were reviewed against S340 and the binding ADR amendment.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### S340 supervised Google Sheets export | {level} | {summary}

     followed by a paragraph carrying the detail. S340 supervised Google Sheets export is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### error-owner-allowlist | critical | CLI duplicated canonical error ownership

The first implementation filtered registered codes by declaring-module prefixes and missed valid Google authentication subclasses. Remediated by resolving stable codes directly through the canonical ErrorCode registry.

### actionable-message-loss | high | Instance-only credential failures lost actionable messages

OAuth client, token, and authentication-dependency failures previously shared broad exception classes with instance-specific messages. Remediated with specific registered export precondition errors at the composition boundary.

### preflight-effect-truth | high | Configuration failures could settle with unknown effect

Credential and root-folder resolution occurred after the apply effect became unknown. Remediated by preparing the transport before entering the irreversible section.

### blocking-async-transport | high | Google I/O blocked the supervisor event loop

The synchronous transport was called directly from the async executor. Remediated by moving preparation, preview, and apply calls through `asyncio.to_thread`.

### acceptance-evidence | high | Tests did not exercise the changed command or a live lease

The first proof observed only a released lease after direct supervisor execution. Remediated with command-level success and error projection coverage plus inspection of the lease while the command is held running.

### profile-error-classification | medium | Admission and subject corruption shared one error

Active-profile drift and subject/payload contradiction used one ERROR category. Remediated with separate REFUSED admission and ERROR invariant classes.

### canonical-code-validation | medium | Public failure codes accepted unregistered tokens

Receipt and projection validation checked shape but not registry membership. Remediated with one canonical stable-code resolver and negative validation coverage.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

Retain the prepared-transport boundary, canonical ErrorCode lookup, split profile errors, and live-lease command test as regression gates. Close S340 only after the final SOL review and focused verification pass.
