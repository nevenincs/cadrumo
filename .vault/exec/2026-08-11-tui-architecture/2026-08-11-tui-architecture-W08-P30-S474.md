---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:2c58f5ab4c9312d557967cc5a6935533e6656b6fa0a07bfa3ecb68c75b75134b'
step_id: 'S474'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Characterise the export tree drift precisely and correct the earlier wording, since every record fragment differs in bytes while none differs in parsed meaning and the provenance reds only because it records byte digests, which makes the owed regeneration a serializer rewrite rather than a change to any declaration

## Scope

- `dev/registry` (measurement only; nothing changed)

## Changes

NOTHING WAS CHANGED. This step sharpens S472's handover and CORRECTS ITS
WORDING.

S472 reported "no record layout fragment differs". That was read off the gate's
filtered `differing` list, and the gate deliberately forgives a byte difference
whose PARSED content matches. Measured directly instead of inferred from the
gate's silence:

    m303-2025        files differing in BYTES: 10   in MEANING: 1
    m151-2015-2022   files differing in BYTES: 14   in MEANING: 1

The one file differing in meaning is `_generation.provenance.json` in both.
EVERY OTHER FILE IN THE TREE DIFFERS BYTE-FOR-BYTE and parses to an identical
declaration. Nothing is unparseable.

So the accurate statement is not "the records are unchanged" but "every record
is rewritten and none of them means anything different". The provenance is the
only file that reds because it is the only one recording BYTE digests, and its
own two differing members say exactly that:

    loader_semantic_sha256   cfe37df0... -> ad8295d7...
    output_files[].sha256    one entry per record file, all changed

WHAT THAT MEANS FOR THE OWED WORK. The regeneration is a serializer rewrite
across every fragment of 27 trees, not a content change. That is a much larger
diff than "metadata-only" implied and a much smaller RISK: no exported
declaration moves. Whoever picks it up should expect every file in every tree to
change and should verify exactly the property measured here -- parsed equality
per fragment -- rather than eyeballing a diff that will be total.

## Notes

I INFERRED FROM A GATE'S SILENCE AND SAID IT AS FACT. The gate not naming the
record files was evidence that their MEANING matched, and I reported it as their
being unchanged. The two are different claims and only the weaker one was
supported. The measurement above is what the record should have carried, and
S473's lesson generalises: a gate's filtered output answers the gate's question,
not necessarily mine.

STILL STOPPED, for the reasons S472 gave and this does not change: the surface
has an active writer who is publishing export trees as I measure, and
`m390-2022` needs a `_CHECK_MODE_PENDING` reason that is an operator judgement
about an AEAT revision's official standing.

Unchanged: the three operator decisions -- the 125 `cli.*` extras, the 5
`application.*` extras, and the `tui.ledger.reconciliation.direction` spelling.
