---
tags:
  - '#exec'
  - '#dehu-notification-legal-effect'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e4f0eaec2286ef707660b962747618c915c8c65b0934b0011b750fe885298da3'
step_id: 'S01'
related:
  - "[[2026-08-07-dehu-notification-legal-effect-plan]]"
---

# Reuse the campaign's already-primary-sourced BOE consolidated PDF for Ley 39/2015 at boe.es buscar pdf 2015 BOE-A-2015-10565-consolidado.pdf, art. 43 at page 35, rather than re-deriving it, taking the LAST version if the payload bundles historical redactions, never passing the text through a shell since a truncating heredoc silently loses text, and reading the committed file back before trusting it. The consolidated PDF does not annotate which articles were amended, confirmed by positive control against art. 28, so absence of a marker on art. 43 establishes only that this is todays operative text, and no unamended-since-2015 claim may be made anywhere downstream. Commit the HTML plus its extracted sidecars, verified by resolve_anchored_extracted_unit resolving the target anchor with no CorpusAnchorResolutionError

## Scope

- `src/cadrumo/_data/corpus/normatives/html/`

## Description

- Fetched the live BOE consolidated-legislation act page for Ley 39/2015
  (`BOE-A-2015-10565`) over HTTPS and located article 43 by its `id="a43"`
  bloque anchor, confirming the operative apartado 2 clause matches the
  campaign's already-primary-sourced text verbatim.
- Authored `ley-39-2015-art-43.html` following the established
  `ley-19-1994-art-43.html` excerpt convention: an HTML comment provenance
  header (document id, permalink, source, excerpt scope, retrieval date, and
  the amended-articles-not-annotated caveat) followed by the article's
  `h5.articulo` heading and its four `p.parrafo` apartados, copied verbatim
  from the fetched BOE markup.
- Generated the `.extracted.md`/`.extracted.json` sidecars through the
  production extractor (`dev.docs.preprocess._html.extract_html`), never
  hand-authored, so provenance (`source_sha256`, anchor `#a43`) is
  machine-derived from the committed HTML.
- Read the committed HTML and both sidecars back from disk and confirmed the
  full four-apartado text, including the "diez días naturales" phrase, is
  present with no truncation.

## Outcome

`src/cadrumo/_data/corpus/normatives/html/ley-39-2015-art-43.html` plus its
`.extracted.md` and `.extracted.json` sidecars are committed to the corpus.
No claim that art. 43 is unamended since 2015 is made anywhere in the file;
the comment header states explicitly that absence of an amendment marker
only establishes today's operative text (per the art. 28 positive control).

## Verification

Ran the gate the plan names directly against the committed sidecar:

    uv run --no-sync python -c "
    from pathlib import Path
    from cadrumo.core.corpus_text import resolve_anchored_extracted_unit
    sidecar = Path('src/cadrumo/_data/corpus/normatives/html/ley-39-2015-art-43.html.extracted.json')
    text = resolve_anchored_extracted_unit(sidecar, anchor='#a43', required_text=('diez días naturales',))
    print('RESOLVED OK, length', len(text))
    "
    RESOLVED OK, length 1289

`resolve_anchored_extracted_unit` resolved the `#a43` anchor to the single
matching unit with no `CorpusAnchorResolutionError`.

## Notes

None. The BOE fetch, excerpt authoring, and sidecar generation all completed
cleanly on the first attempt; no truncation or version-ambiguity issue was
encountered (the live act page carries only the current consolidated text,
not a multi-version historical payload).
