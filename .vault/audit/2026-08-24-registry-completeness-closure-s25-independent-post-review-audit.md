---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:a119948a08b428dd9810efd78a0c588b60c87edf7587d540c22c483c6e7edb5b'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `S25 Modelo 840 independent post-review`

## Scope

Independent review of `W02.P03.S25` and its Modelo 840 disposition. The review
re-ran the hash, parser geometry, focused parser tests, the capability-worklist
gate, the semantic-map join, the fixed-width codec, and the actual application
filing renderer. It also traced the complete S25 commit: it changes vault
records only and introduces no production-code redeclaration.

## Findings

### live-emitter-canonicality | high | S25 names a non-substitutable codec as the required production emitter

The source hash and the three parser measurements are correct: `aeat-dr-840`
is `d0348a...4391a`; its records are 1,132, 1,165, and 1,067 bytes and each
ends with the stated ten-byte identifier plus one CRLF row. The semantic-map
join also correctly refuses an omitted terminal anchor, while the narrow
fixed-width codec can append its declared `line_ending`. However, ordinary
production filing reaches `render_layout_records` and
`_render_record_bytes` in `src/cadrumo/application/filing/_record_renderer.py:132`, which
independently maps `crlf` and `lf` before encoding. It supports producer,
binding, draft, computed, and projection fields; the codec accepts only
literal, filler, and casilla fields, so it is not a safe replacement under the
constraint-shape test. The S25 reference's instruction that the future M840
implementation must use the existing codec consequently omits the live
emitter and leaves the pre-existing terminator redeclaration unresolved. This
does not authorize an M840 writer: the correction belongs to the shared
export route.

## Recommendations

`W02.P04.S28` is the existing owner. Before it admits Modelo 840, it must make
one shared transport-terminator authority reach both the generated-layout
path and the production filing renderer (or record an ADR-backed alternative
that preserves one source of truth); retain the exact source-anchor bijection,
the three official lengths, and mutation proof for omission, spaces, and
doubled CRLF. It must not route around the application renderer or add an
M840-specific writer. The existing worklist remains correctly red: its
fourteen gaps include Modelo 840's terminal-row refusal.
