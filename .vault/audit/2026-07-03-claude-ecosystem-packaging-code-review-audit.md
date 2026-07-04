---
tags:
  - '#audit'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# `claude-ecosystem-packaging` audit: `campaign code review`

## Scope

Independent code review of the `claude-ecosystem-packaging` campaign, covering roughly
thirty campaign commits from `56413eafd1` through `e40e67bbb4` plus `c7da92d2f1`, reviewed
at HEAD `67b6754760`. The review spans seven dimensions: the corpus-companion split-package
integrity gate, storage-root relocation safety, the wheel split build configuration, the
plugin and marketplace generator, the MCP CONFIRM annotation, the publish recipes plus
`RELEASING.md`, and cross-cutting rule conformance including exec-record honesty.

## Findings

### overall-verdict | low | Independent review returns STATUS PASS with zero critical and zero major findings

The reviewer's verdict is PASS. No CRITICAL and no MAJOR findings were raised against any
of the seven audited dimensions. Four MINOR, non-blocking notes were recorded (below); none
require revision before closure.

### corpus-companion-integrity-gate | low | Integrity gate confirmed clean and non-tautological

The corrupted-present-binary proof is real and non-tautological: a byte flip that preserves
file length still forces the SHA check to fire. An absent companion binary produces a loud
advisory (both warned and returned to the caller); an absent non-companion file still
raises. The citation-gate skip is scoped to `FileNotFoundError` only and is companion-scoped
— a present-but-unreadable file and a corrupt-present file both still fail. The
companion-corpus-binary classifier matches the wheel-exclude glob byte-for-byte, and all
five binary-reading verbs are guarded while citation verification behaves correctly when
unguarded. Research `F10` under-scoped the consumer set once (`validate_source_citations`
was missed); this was caught by the split-install smoke lane and fixed in commit
`0b60114d00`.

### storage-root-relocation | low | Storage root relocation confirmed clean with no data-loss risk

Checkout detection is worktree-aware (it reads the `.git` pointer file and checks
`.exists()`), and the encrypted substrate correctly re-roots under the platform base
directory. The `var/*` output-root fields left pointing at `PROJECT_ROOT` are vestigial
with zero live consumers. An anti-tautology proof confirms repository markers take
precedence over a populated `LOCALAPPDATA` value.

### wheel-split-build-config | low | Wheel split build configuration confirmed clean

A single exclusion pattern is shared consistently across all four sites that need it: the
wheel exclude glob, the companion classifier, the size-budget slice, and the build hook.
The version-parity and exhaustive-partition budget gates are non-tautological, and the
`_export_names` path-source resolution cannot mask a missing external dependency.

### plugin-marketplace-generator | low | Plugin and marketplace generator confirmed clean

A single authored source is held for the generated plugin and marketplace trees; the
emitted trees carry no secrets or tax data. The `uvx` pin is correct, never-mode holds and
is tested, and the coordinator denylist is correct.

### mcp-confirm-annotation | low | MCP CONFIRM annotation confirmed clean

The CONFIRM annotation is derived from the same `confirmation_for_tool` gate the server
enforces — the mapping is derived, not hand-listed, and the flag-to-CONFIRM-tier
correspondence is proven against real SDK objects.

### publish-recipes | low | Publish recipes and RELEASING.md confirmed clean

The CI, confirm, token, dirty-tree, and tag gates all refuse correctly, and the publish
token is never echoed or committed.

### cross-cutting-conformance | low | Cross-cutting rule conformance confirmed clean

Boundary data is typed, the CLI surfaces a closed enum as a click choice, tests live under
`tests/` directories, locale translations are real across all four catalogues with parity
preserved, and the campaign's exec records are honest.

### plan-checkbox-progress-lag | low | Plan checkboxes for S20-S22 remain unchecked while their work and exec records already landed

Steps S20 through S22 in the `W02.P06` split-install smoke lane have landed work and exec
records, but the plan checkboxes are not yet checked, understating actual progress. No
functional impact; check the boxes at campaign close.

### library-registry-advisory-tuple-discard | low | The library registry-load path discards the advisory tuple, surfacing only via warnings.warn

The library (non-CLI) registry-load path drops the returned advisory tuple and surfaces the
corpus-companion-absent signal only through `warnings.warn`. This is acceptable by the
ADR's own design for that call site, but is worth a short intent note documenting the
choice so a future reader does not mistake it for an oversight.

### persona-read-only-prose-parsing | low | `_persona_is_read_only` parses prose for a "read-only" prefix, a fail-open risk if reworded

`_persona_is_read_only` determines persona mode by parsing a "read-only" prefix out of
prose text. If that prose is ever reworded, the check fails open. This is defense-in-depth
only — the real refusal surface is the server-side persona gate — so the risk is bounded,
but the prose-parsing approach is fragile.

### vestigial-project-root-fields | low | Vestigial `var/*` `PROJECT_ROOT` fields remain a future cleanup candidate

The `var/*` fields still pointing at `PROJECT_ROOT` (noted under storage-root-relocation
above) have zero live consumers and are a candidate for a future cleanup pass, not a
correctness issue today.

## Recommendations

- No revision is required before closing the campaign; the review verdict is PASS and safe
  to close.
- Check plan steps S20 through S22 at campaign close to reflect the work and exec records
  that have already landed.
- Add a short intent note documenting the ADR-sanctioned advisory-tuple discard in the
  library registry-load path (M2), so the design choice reads as deliberate rather than
  incomplete.
- Track the `_persona_is_read_only` prose-parsing fragility (M3) and the vestigial
  `var/*` `PROJECT_ROOT` fields (M4) as optional low-priority follow-ups; neither blocks
  closure.
