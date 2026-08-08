---
tags:
  - '#audit'
  - '#error-code-registry'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:0380a8adfbeec265f3d8a708251d700ec8bf9cc45af74a147f9d76e4a518407d'
related: []
---

# `error-code-registry` audit: `refusal funnels`

## Scope

A refusal raised with only a `translated_message` renders that key as `str(exc)`. When one
key covers many distinct causes, every one of them produces a byte-identical failure line
and the discriminating cause survives only in `context`, which no traceback shows. Two
unrelated defects then present identically.

That cost two investigations in one session: a missing counterparty identification state
was triaged three times as an unrelated registry binding failure, because the matching
failure line plus temporal proximity was read as evidence when it carried none.

This audit measures how far that shape extends, whether a general fix is viable, and what
the exposed surface actually is. Read-only throughout except for two scoped fixes noted
below.

## Findings

### refusal-funnels | medium | the reason is lost for every refusal, not only the ones where it matters

`CadrumoError.__init__` computes `text = message or translated_message` and passes only
that to `super().__init__()`. `self.context` is stored and never rendered. So the
discriminating cause reaches neither `str(exc)`, `.args`, nor any test failure line — for
all 1248 raise sites carrying a `translated_message`, not just the ones investigated.

The distinction that matters is not which refusals lose the reason. It is which ones can
afford to. Where a key names one cause, the key is the diagnosis and nothing is lost.

### refusal-funnels | medium | 22 sites lose a cause the key cannot name

Measured by AST over production code: a raise supplying a string-literal `translated_message`
plus a `context` carrying a cause-naming key (`reason`, `cause`, `kind`, `issue`, `code`,
`status`, `error_kind`, `failure`) whose value is not a constant.

    population (raise sites with translated_message)  1248
    opaque context (unclassifiable, left unknown)       32
    pattern matches                                     36
      already supply a message, so str(exc) names it    14
      true defects                                      22

This is a floor, not a census. The cause-key list is not verified exhaustive; a site naming
its cause `blocker` or `refusal_kind` is missed.

### refusal-funnels | high | the first survey over-reported by 39 per cent, and the correction was on the same line

The first pass asked whether the cause was dynamic and in `context`, and stopped. It never
asked whether a `message` was also supplied — and a positional message puts the reason into
`str(exc)`, which is the entire property under investigation. Fourteen already-correct sites
were counted as defects.

One of them, the IVA wallet block, was routed as first-priority remediation off that number.
Both its raise sites already pass a message naming the reason: one inline, one through a
localised renderer. Nothing already-correct was edited only because the raise site was read
before being changed.

The general shape: the survey measured the presence of the symptom and never checked for the
remedy, which sat on the same line as the symptom.

### refusal-funnels | medium | severity is recoverability, not cardinality

An enum member behind a fixed key tells the reader nothing and sends them hunting for a
name. A rendered free-text cause explains itself once recovered. So an enum-backed funnel is
harsher than an unbounded free-text one despite lower cardinality, and ranking by
cardinality alone sequences the work backwards.

The worst confirmed funnel carried a sixteen-member enum through one key. Both enum-backed
funnels found are now fixed; the twenty remaining are free-text or self-describing.

### refusal-funnels | high | the test surface is not the exposed surface

Three measurements were taken of what a general fix inside the base class would disturb, and
the first two measured the wrong population.

The first counted assertions matching on refusal text — 2122 sites. Retracted: `pytest.raises`
uses `re.search`, not `fullmatch`, so appending to `str(exc)` cannot break an unanchored
pattern. Of 2128 such sites, 971 name classes a base-class change cannot reach, and of the
1146 reachable, zero are end-anchored. A residue of unresolvable exceptions and non-literal
patterns was classified by two agents independently, with different denominators and the
same verdict: escaped patterns are anchor-free by construction, variables resolve to
literals without trailing anchors, and no anchored literal reaches a match argument either
directly or through a parametrised pattern name.

The exposed surface is elsewhere. `resolve_error_message` prefers `translated_message` and
then falls back to `args[0]`. So for any error raised without a key, `args[0]` is the
operator envelope:

    message only (envelope is args[0])   4266
    translated_message only               570
    both                                  508

Demonstrated on a real production class rather than a constructed one: a message-only
browser error with context resolves to its message before an append and to the message plus
the appended cause after, and the two are not identical. A general append is therefore an
operator-facing change at four times the scale of the retracted figure.

### refusal-funnels | high | the redaction exposure survives narrowing the fix

Restricting the append to sites that already carry a `translated_message` answers the
envelope movement entirely — that population's envelope is provably unchanged. It does not
answer the second exposure, because `args[0]` reaches `str(exc)` through the CLI renderer,
tracebacks and observability sinks whether or not a key exists.

The redaction module states that raised exceptions interpolate operator-controlled
identifiers into `args[0]` — tax identifiers, OAuth tokens, session URLs — and that the
logging filter does not cover `str(exc)` on those paths. The stated mitigation is redaction
at the construction site.

Measured across the 846 keyed raise sites carrying a literal context:

    safe          537
    unclassified  979
    flagged       110
    opaque         47
    non-literal key 10

The flagged set was separated from keyword false positives by hand. The residue is real: six
landing URLs, three requested URLs, two selector URLs, one bare URL, one account email and
one session label — precisely the identifiers the redaction module names. The 979
unclassified would block the change independently, and classifying them by pattern would not
help, because the reason they are unclassified is that a key name does not tell you what its
value carries.

## Recommendations

Keep the scoped shape: pass both `message` and `translated_message` at the raise site. The
resolver prefers the key, so the operator envelope is byte-identical and only `str(exc)`
gains the cause. Verify per site rather than assuming: confirm no assertion matches on that
key, and that tests touching it assert on the attribute rather than the rendered string.

Do not take the general form, narrow or otherwise. Two independent findings block it and
either is sufficient. Two fallbacks were considered and declined: excluding the flagged
sites requires maintaining a list of which refusals may carry an identifier, which is the
allowlist shape that rots; and author-chosen key selection at 846 sites costs more than the
twenty scoped edits it would replace, for sites that mostly do not need it.

An architecturally significant follow-on, should the general form ever be revisited, must
decide one thing this audit deliberately does not: whether `args[0]` is permitted to carry
structured context at all, given that it is the field the redaction rule singles out as
outside the logging filter's cover. That is a decision about the boundary, not about the
message format.

Re-run the surveys before acting on any figure here. Four scripts were used and each is
re-runnable; every count in this document is a measurement of a stated population at one
point in a moving tree, and two of the three population choices made during this audit
turned out to be the wrong one.
