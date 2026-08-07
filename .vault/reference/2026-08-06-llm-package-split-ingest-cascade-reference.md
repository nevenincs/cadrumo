---
tags:
  - '#reference'
  - '#llm-package-split'
date: '2026-08-06'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:77292d521ead2e4cf8483a1482c564af8ce640c4ad85925709ac0c641e46f4c4'
related:
  - "[[2026-08-06-llm-package-split-adr]]"
---

# `llm-package-split` reference: `Ingest cascade blueprint, format coverage, and injection posture`

## Summary

The document-ingestion discovery this campaign executes lived in a scratch directory outside
the git tree. This is the durable record of what it found about format coverage, the missing
normalization seam, and the injection posture — the parts an executing team needs and cannot
reconstruct from the code alone. It is descriptive: the decisions are in the governing ADR, and
where this document says "must", it is restating a decision recorded there.

### Format coverage at the time of discovery

The media kind is a **closed two-member enum** (`PDF`, `IMAGE`) declared in
`application/ledger/_evidence.py`, derived at exactly two closed sites — plus a third,
unguarded door that is the source of the data trap below.

- **By file suffix** — `_resolve_media_kind` in `application/ledger/_evidence.py`, the
  **ingest-time** gate reached from the evidence-add service. Accepts `.pdf` and eight image
  extensions and refuses everything else.
- **By stored MIME** — `_media_kind_from_mime` in `application/ledger/_evidence_input.py`, the
  **read-time** gate. Maps the PDF type and any `image/` prefix, and raises on everything else.
- **The unguarded third door** — the document-link and folder-pull verbs store bytes through the
  attachment path with a *sniffed* MIME whose own docstring states the type is "provenance
  metadata, never a gate."

| Format | ingest via evidence add | via document-link / folder-pull | Net outcome |
|---|---|---|---|
| PDF with a text layer | accepted | accepted | read by regex, then the off-host branch |
| PDF, scan only | accepted | accepted | read by local vision |
| Common raster images | accepted | accepted | read by local vision |
| **ZUGFeRD / Factur-X** (XML embedded in a PDF) | **accepted as a plain PDF** | accepted | **silently mishandled** |
| **Facturae XML** (standalone) | **refused** | **stored**, then refused at read | accept-then-refuse |
| CSV, XLSX | refused | stored, then refused at read | accept-then-refuse |
| Plain text | refused | stored, then refused at read | accept-then-refuse |
| Email message | refused | stored, then refused at read | accept-then-refuse |

**Two distinct defects fall out, and they are not the same defect.**

**ZUGFeRD is silently mishandled.** The corpus fixture is a real reference invoice — a PDF
carrying a complete, exact, machine-readable XML invoice as an embedded file. The system reads
it as a **text layer** and never opens the embedded XML, which contains every field the
extraction draft wants, exactly, with no inference. The test covering it asserted only that
German rendered prose came back. Worse: because it *has* a text layer, this document took the
off-host branch — **the most machine-readable invoice format in the corpus was the one whose
bytes left the host, and the one a gestor was refused on.** No parser for any of these formats
existed anywhere in the tree.

**Accept-then-refuse is a data trap.** A non-PDF, non-image document reached through the
unguarded third door is fetched, encrypted, manifested, event-logged and linked to a
transaction — and is then **unreadable forever**. The refusal fires at read time, not at
ingest, so a folder sweep of a real supplier's Drive containing structured XML reports those
files as successfully fetched and every later extraction on them fails. The two gates disagree
about what the system accepts.

The campaign closes the trap **for the XML formats only**, by making them readable rather than
by tightening ingest. CSV, XLSX, plain text and email remain trapped; that residue is named in
the ADR's out-of-scope section rather than left to be discovered.

### There is no normalization seam

Nothing between raw bytes and a persisted record is stored anywhere, which is why every
operation re-does everything: extraction re-reads from secure storage and re-runs the parser on
each invocation, the draft itself is never persisted on either path, and confirming re-extracts
from scratch before writing.

The discovery specifies the shape the seam should take if it is ever built. It must be a
**single typed record, not a tagged union** — the current resolved-evidence type is a union and
rebuilding one under a new name would carry the defect across. It should carry the source
shape, the structured record when the exact path ran, the text otherwise, the page count, the
content address, and **per-field provenance** so a draft can always answer *how* each field was
recovered. And it must inherit the evidence-input custody discipline — the tripwires refusing
serialization — because normalized text of an invoice is every bit as sensitive as the invoice.

**That seam is the two-stage pipeline shape, and the governing ADR deliberately leaves the
shape open** because the measurement that would settle it was never run. This section is
recorded so that whoever eventually builds it inherits the constraints rather than rediscovering
them; it is not a licence to build it now.

### Injection posture — the guarantee does not cover extraction

This is the part most likely to be misread, because a test exists that looks like it proves more
than it does.

**What holds.** For **classification**, the model may only emit a category from a
registry-grounded allow-list. Injection cannot mint an invalid category. It can still steer the
model toward a wrong-but-valid one, and the human review loop is the mitigation there — a
reasonable posture.

**What does not hold.** For **extraction**, the draft's fields are amounts, dates and
identifiers, and **there is no allow-list they could be checked against.** The grounding
functions validate **shape only**: a checksum-valid tax identifier, a parseable date, a finite
decimal. Text injected into an invoice reading like a plausible taxable base and cuota passes
every one of those checks and becomes a draft field. The only remaining barrier is the operator
reading the draft. The existing test's own docstring is explicit that extraction returns hostile
text **verbatim as inert text** and that the extractor's job is merely not to crash.

**The posture gets worse under a naive two-stage build, and this is introduced by the refactor
rather than pre-existing.** Today hostile text on a page reaches the model as *pixels*, and the
output is constrained to a fixed small key set. If a normalization stage emits text which a
*separate* downstream extractor consumes as prompt input, the hostile content is promoted from
image content to **prompt content**, crossing a stage boundary that does not exist today.

**Mitigations, in order of strength:**

1. **Route the exact path first — the cascade ordering is itself a security control, not a cost
   optimisation.** A document carrying a structured record reaches **no model at all**, so for
   that document prompt injection is **categorically impossible** rather than mitigated. This is
   the strongest argument for the ordering and is recorded as a decision precisely so a later
   agent optimising step order does not discard it as a performance choice. The exact path
   carries a *different* risk — entity expansion, external entity resolution, quadratic blowup —
   addressed by parsing with entity resolution and external DTD loading disabled and with size
   and depth bounds.
2. **Fence untrusted content.** Document text enters any downstream prompt inside a delimited,
   explicitly labelled untrusted region, with the instruction stating the region is data to
   transcribe and never instructions to follow.
3. **Closed response schema.** Keep the strict-frozen pattern with forbidden extras and a fixed
   key set, so no injected key survives validation.

Mitigation 1 is implemented by this campaign. Mitigations 2 and 3 bind whoever builds the
two-stage shape; a regression gate for the promoted-text hazard is named in the ADR as a
**precondition** of any future record adopting that shape, and is deliberately not built here
because building it would adopt the shape by the back door.

### Sanitization exists and nothing calls it

The inbound sanitizer package is a competent PDF hardening pipeline — it refuses signed PDFs
and strips embedded file attachments, scripting, automatic actions, annotations, optional
content groups, form values, thumbnails, outlines, page labels, the structure tree, document
info and identifying metadata keys, then saves deterministically.

**It has zero production call sites**, and its own package docstring says why: it is
**fixture-preparation infrastructure**, not a runtime ingest guard. So it is *not* a mis-wired
control and nothing was bypassed — a framing worth stating plainly, because the obvious reading
is that a guard was skipped. The consequence nonetheless stands: **no ingest path sanitizes
anything.** An operator-supplied PDF is stored and later reopened by three separate C-backed
parsers with its scripting, automatic actions, embedded files and annotations intact. The
realistic exposure is parser-level rather than script execution — none of the three executes PDF
scripting — and all three currently fail loudly on malformed input, which is the right
behaviour.

Wiring sanitization into ingest is named out of scope with its reasoning: it carries its own
threat model, and a sanitiser that rewrites bytes changes the **content address the whole
evidence chain is keyed on.**

One irony the discovery flags and this campaign exploits: the sanitizer already contains a
working **embedded-file enumerator** — it strips them. That is precisely the machinery a ZUGFeRD
reader needs in order to *extract* them, which is why the campaign extracts that walker into a
reusable reader rather than writing a second one.
