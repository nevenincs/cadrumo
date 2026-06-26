# Testimonial — docs/explanation/index.md

- **Doc path:** `docs/explanation/index.md`
- **Persona:** A naive first-time reader landing on the Explanation section index, checking that every link works and that the overview honestly previews the pages it lists.
- **Date:** 2026-06-18

This page is a navigation/overview hub, not a workflow page. It prints no `aeat`
commands, so there is no CLI walkthrough to run. My job was to (1) verify every
link resolves, (2) judge whether the overview accurately previews each listed
page and orients a reader, and (3) flag dead links or mismatched descriptions.

---

## Walkthrough (link + accuracy verification)

### Check 1 — Intra-section links to the five cluster members

- **Action:** Verified each relative link target exists under `docs/explanation/`.
- **Expected:** All five pages introduced (records→figures, editing/verifying, building-on-earlier, reviewing/exporting, recording-a-filing) resolve to real files.
- **Actual:** All present —
  `from-records-to-figures.md`, `editing-and-verifying.md`,
  `building-on-earlier-filings.md`, `reviewing-and-exporting.md`,
  `recording-a-filing-and-the-boundary.md`. The page links
  `recording-a-filing-and-the-boundary.md` three times and
  `editing-and-verifying.md` twice (once in its own section, once from the
  "What verify and file mean here" section); every occurrence resolves.
- **Verdict:** OK.

### Check 2 — Cross-section links

- **Action:** Verified the four out-of-section relative links.
- **Expected:** `../how-to/index.md`, `../how-to/quickstart.md`, `../tutorials/index.md`, `../how-to/troubleshooting.md` all exist.
- **Actual:** All four resolve.
- **Verdict:** OK.

### Check 3 — Sphinx role/directive targets

- **Action:** Checked the two non-markdown references: `{term}`justificante`` and `{doc}`glossary </_generated/glossary>``.
- **Expected:** `justificante` is a defined glossary term and `/_generated/glossary` is a real doc.
- **Actual:** `docs/_generated/glossary.rst` exists and contains `justificante` (term defined, 2 occurrences). The `{doc}` path is absolute-from-docs-root (`/_generated/glossary`), which is the correct MyST form. Both resolve.
- **Verdict:** OK.

### Check 4 — Section descriptions vs. actual target content

- **Action:** Read the H1 and opening of each target page and compared to the description and link text on the index.
- **Expected:** Each "See [...]" link text matches the target's real title, and each paragraph previews what the page actually covers.
- **Actual:** Strong match across all five:
  - "How your records become tax figures" → target H1 identical; target opens on bank-movement→box-figure idea, exactly as previewed (sorting into categories, business-share adjustment, readiness check, fill boxes, save draft).
  - "Editing and verifying a calculation" → target H1 identical; target covers "a calculation is a saved version, not a final answer" and the completeness check — matches the index's "adjust figures, re-run, keep saved versions, completeness check."
  - "How filings build on earlier ones" → target H1 identical; target covers carrying earlier figures forward and what it leaves you to check — matches "carries earlier numbers forward… tells you when an earlier filing isn't ready."
  - "Reviewing your numbers and producing the upload file" → target H1 identical; target's "two outputs, not one" (review surface + portal file) matches "review every figure… trace it back… produces the official upload file."
  - "Recording a filing, and why the tool never files for you" → target H1 identical; target's "the boundary is permanent / you file yourself / record the justificante" matches the index's promise and recording sections.
- **Verdict:** OK.

### Check 5 — toctree vs. introduced sections

- **Action:** Compared the hidden `{toctree}` entries to the five sections introduced in prose.
- **Expected:** The toctree lists the same five members in the same order they are introduced.
- **Actual:** Exact match and exact order:
  `from-records-to-figures`, `editing-and-verifying`,
  `building-on-earlier-filings`, `reviewing-and-exporting`,
  `recording-a-filing-and-the-boundary`. The page states "The five sections that
  follow introduce them in order" and they genuinely are in order — no drift.
- **Verdict:** OK.

### Check 6 — Orientation quality (mermaid journey + "the one promise")

- **Action:** Read the overview prose, the mermaid pipeline diagram, and the "What verify and file mean here" box as a first-time reader.
- **Expected:** A reader unfamiliar with the tool comes away knowing the shape of the journey and where to go to act.
- **Actual:** Excellent orientation. The single mermaid graph (Bank movements → Sorted/tax-ready → Readiness check → Numbered boxes → Edited/double-checked → File you upload → Recorded) maps cleanly onto the five sections. The "one promise" (runs locally, never files for you) is stated up front and repeated where it matters. The "verify"/"file" glossary-of-two-words box pre-empts the most likely confusion for a newcomer. Every section ends with a "See [...]" pointer, and the closing "How to use this cluster" tells you to read straight through or jump, plus where to go when something breaks (Troubleshooting / Quickstart / Tutorial).
- **Verdict:** OK.

---

## Findings

No blocking, major, or minor issues. Two nits only.

1. **[NIT] [DOC]** The mermaid node labels are deliberately plain-language
   ("The numbered boxes of a form", "The file you upload") rather than the tool's
   own vocabulary (casilla, fichero/BOE export). That is a reasonable choice for
   a naive reader, but a reader who then opens a how-to guide meets the technical
   terms cold. *Suggested fix:* optionally append the glossary term in parentheses
   on one or two nodes (e.g. "The numbered boxes of a form (casillas)") to bridge
   the overview vocabulary to the how-to vocabulary. Low value; the diagram is
   already clear.

2. **[NIT] [DOC]** The index uses the `{term}` role only once (`justificante`),
   while sibling pages in the same cluster (e.g. `building-on-earlier-filings.md`)
   richly cross-link `modelo`, `casilla`, `AEAT`, etc. via `{term}`. The index
   prose mentions "autónomo", "AEAT" (spelled out inline instead), and "modelo"
   without linking them to the glossary. *Suggested fix:* for consistency with the
   rest of the cluster, consider `{term}` links on the first mention of AEAT and
   autónomo. Purely a polish/consistency point — every such word is also defined
   inline or in the linked glossary, so nothing is unreachable.

---

## Testimonial

As a first-timer I knew nothing about the tool, and this page oriented me fast:
the one-way journey diagram, the "it never files for you" promise, and the plain
explanation of what "verify" and "file" narrowly mean here all landed before I
had to make any decision. Every single link I clicked worked — all five cluster
pages, all four cross-section links, the glossary doc, and the justificante term —
and every "See [...]" description honestly matched what the target page actually
covers, in the same order the toctree lists them. Nothing tripped me; this is a
clean, well-built index whose only gaps are cosmetic consistency nits.

---

## Scorecard

- **Doc clarity:** 5 / 5
- **App capability:** N/A (overview page — no commands to execute)
- **Findings by severity:** BLOCKER 0 · MAJOR 0 · MINOR 0 · NIT 2
