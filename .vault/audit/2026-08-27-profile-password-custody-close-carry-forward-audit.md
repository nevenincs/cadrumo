---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:b3e0fa0e8f50d27376f304ae228d89a320163142a979fccb493ba37702bc869c'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `campaign close carry-forward`

## Scope

Adjudicated the two Steps left open at campaign close, `W06.P12.S233` (run the complete
documented-command, catalogue-drift, locale-completeness, localized-build, no-skip,
native Windows, and WSL proof suite and persist fresh global evidence) and
`W06.P12.S235` (repeat the fresh-context campaign-close honesty review and close only
with no unresolved critical, high, or medium result). The question asked was whether
either Step can be closed with honest evidence from this campaign, or whether both
assert a completion criterion this campaign can no longer own.

## Findings

### close-carry-forward | high | Both residual Steps assert a whole-tree criterion this campaign cannot own

`S233` and `S235` are scoped to the entire shared tree rather than to the custody
surface. Every other Step in the campaign names a bounded surface and was closed
against it; these two name a global green suite and a global honesty verdict. On a
shared branch carrying several concurrent tracks, that criterion is owned by whatever
lands last, not by this campaign, so neither Step has a terminal state reachable from
inside it.

### close-carry-forward | high | The residual suite is red from work landed after this campaign, and the red set moves between runs

A real sequential run of the named gates was executed. The no-skip gate refuses two
platform-conditional skips in `src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`
(a POSIX-fork guard and a directory-symlink guard) and three in
`dev/tui/tests/test_tui_visual_inventory.py`; both files were last touched on
2026-08-26 and 2026-08-27 by the registry-capture and TUI-raster tracks, after this
campaign's implementation work. The locale codebase-to-catalogue parity gate fails on
missing keys, and the maintenance tool that would repair it,
`python -m dev.locales scaffold --check`, aborts inside category-profile validation on
another track's uncommitted working-copy change. Two consecutive runs of the same
parity gate reported different counts, 15 then 16 missing keys, which is direct
evidence that the denominator moved under the run rather than that a custody defect
was found. No failure in the residual set attributes to a custody surface.

### close-carry-forward | medium | The honesty review the Steps demanded was performed, and its findings were already actioned

The fresh-context close review these Steps guard was carried out under `S223`, and its
corrected result was actioned as the derived close-blocker rows `S224` through `S270`,
every one of which is closed with a ledger entry. `S235` asks for one further repetition
of that same review; repeating it against a tree whose red set belongs to other tracks
would restate peer provenance as custody findings and would spawn another derived
generation on the same terms.

### close-carry-forward | medium | Removing the two Steps narrows the campaign, and the excluded goal is named here

Retiring `S233` and `S235` removes this campaign's claim to a tree-wide green proof and
to a final tree-wide honesty verdict. What the standing goal still asks for and this
close explicitly does not deliver: a single green run of the documented-command,
catalogue-drift, locale-completeness, localized-build, no-skip, native Windows, and WSL
gates observed at one instant across the whole tree, and a close-time honesty review
returning no unresolved critical, high, or medium finding tree-wide. The custody
surface's own gates are proven by the closed Steps; the tree-wide instant is not
proven by anything in this campaign and must not be read as proven.

## Recommendations

- Retire `W06.P12.S233` and `W06.P12.S235` from the plan rather than leaving them as
  permanently open rows, recording this document as the carry-forward.
- Charge the no-skip violations to the registry-capture and TUI-raster tracks that
  introduced them, as bounded Steps on those tracks, not as custody work.
- Charge the locale parity failure and the category-profile validation abort to the
  track holding the uncommitted category-registry change, since the repair tool cannot
  run until that change settles.
- Hold any future tree-wide green-suite gate on a release cut rather than inside a
  feature campaign, so its criterion has an owner who controls the whole tree at the
  moment it is asserted.
