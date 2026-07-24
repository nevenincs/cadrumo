---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S35'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Splice attach_descendant_group into the shared setup definition builder with the count page defaulting to zero descendants, pinning the group live on both frontends

## Scope

- `src/cadrumo/application/wizard/_commands.py`

## Description

- Splice `attach_descendant_group` as the outermost decorator of the shared `_setup_flow_definition` builder, making the descendant group live on both frontends from one call site.
- Give the `descendientes-count` page an explicit default of zero descendants so a walk that never mentions descendants stays token-compatible; production non-interactive alignment flows through the scripted-answer projection, which fills visible pages from the canonical map or the page default.
- Realign the injected test runners over the live definition through a shared helper mirroring the production projection's visibility law; leave the shared token fixture and the peer-owned flows substrate untouched.
- Pin the group live: the count page, the group, and the adoption validator id asserted on the real definition; instance pages revealed at count two; a scripted walk with two descendants projecting the documented fact shape and submitting; a bad adoption date refusing at the real submit gate.

## Outcome

Landed as `2daac900b9`; wizard and flows suites at committed HEAD 416 passed, zero failed, including both profile-language provenance parametrizations. Code review verdict: clean pass, no critical or high findings. The decisive data-loss question — whether a quiet edit omitting descendant flags could receive the defaulted zero count as answered and silently wipe declared descendants — resolved SAFE-BY-CONSTRUCTION on three concordant traces: the quiet edit routes through the true-patch path over explicitly supplied flags only, the count page has no CLI flag so it can never enter a patch, and the clearing guard lives solely on the create-mode checkpoint store gated on a count answer being present. The adoption flow-validator is now live on the shipped definition, discharging the condition the earlier benign verdict was load-bearing on.

## Notes

- The dispatch brief's mechanism claim was falsified by the executor with grounding: the scripted driver's defaults map never consults a page default (queue-first; mid-walk pages never starve), so the correct alignment is the scripted-answer projection on the production path and a projection-mirroring helper for injected test runners. The wrong premise is superseded here, loudly.
- Review medium, tracked as its own open step: the shared definition now renders descendant pages in interactive edit, but the edit persist seam drops their answers — a silent no-op on write. Existing descendant facts survive (nothing clears on edit); the gap is write-side only. Fix or gate before the descendant surface is considered edit-complete.
- Review lows: the test realignment helper pads or truncates a malformed fixture silently (test-maintenance exposure only); the checkpoint-store protocol lacks two members its concrete implementation provides (pre-existing, protocol-versus-concrete reconciliation follow-up).
