---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:68367b6842bdef4d0249e5224aaf4a45375f4f968fe3781bb70aafa6b77d2c27'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `s240 result frame expectation review`

## Scope

Reviewed the S240 sequence-source, parser property, central baseline, and conformance-test delta against the 17 offenders derived from S233, committed real transcripts, and the no-golden-refresh boundary.

## Findings

### semantic-result-assertions | resolved | Newly enrolled frames assert meaningful success or refusal outcomes

Structured success frames now assert stable operation, readiness, or recovery-enrollment fields; refusal frames assert exact error codes. Terminal help frames are explicitly limited to commands ending in `--help`, which have no JSON payload and remain covered by exact help snapshots plus a successful exit assertion. The negative property test proves an ordinary exit-only structured frame still fails.

### golden-ownership | resolved | S240 changes no generated transcript

The delta edits sequence contracts and the central property gate only. Existing live/golden divergence remains visible for S241 adjudication and S242 owning-CLI regeneration.

### dispatch-label-tautology | high | Three initial assertions proved only command routing

Formal review found that the first dependency, observation, and filing assertions checked only each result's `operation` label. Those labels could remain correct while the documented outcome was wrong, so they did not satisfy the semantic payload contract.

### dispatch-label-tautology-resolved | resolved | Outcome fields now prove dependency, observation, and filing meaning

The dependency frame now proves a single target and required clean-state evaluation; the observation frame proves the saved draft state; and the filing frame proves an internal, non-live filing marker. These values are grounded in the committed real transcripts and fail when the documented outcome changes.

## Recommendations

- Close S240 after independent review confirms the terminal-help exception is narrow and the baseline ratchet remains bidirectional.
