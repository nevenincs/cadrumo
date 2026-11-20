import type {
  ReferenceServed,
  RetrievalHit,
} from "../../shell/referenceContract";

// What the bundled reference corpus answers, in the shape the product serves
// it, for the scenario host and the stories. SYNTHETIC: the passages, titles,
// sources and terminology are invented placeholders, not text of any
// provision, and the window draws exactly what is served.

/** The text that asks for an exact citation, and the one that matches nothing. */
export const CITATION_QUERY = "SYNTHETIC-CITATION-1";
export const NO_MATCH_QUERY = "synthetic-nothing";

const PROFILE = "0b4f6c2e-8f0a-4a8e-9a43-5b1a6e0d7c11";
const GENERATION = `sha256:${"0".repeat(64)}`;

const hit = (rank: number, title: string, text: string): RetrievalHit => ({
  chunk_id: `synthetic-chunk-${rank}`,
  corpus_ref: `synthetic/source-${rank}`,
  doc_title: title,
  text,
  score: 2 - rank * 0.5,
  rank,
  lexical_rank: rank,
});

const answer = (
  query: string,
  change: Partial<ReferenceServed["retrieval"]>,
  terminology: ReferenceServed["terminology"],
): ReferenceServed => ({
  result_version: 1,
  profile_id: PROFILE,
  output_language: "en",
  authority_generation: GENERATION,
  retrieval: {
    query,
    mode: "lexical_only",
    hits: [],
    citation: null,
    ...change,
  },
  terminology,
});

/** Ranked passages and a terminology concept for a free-text query. */
export const referenceFound = (query: string): ReferenceServed =>
  answer(
    query,
    {
      hits: [
        hit(
          0,
          "Synthetic source one",
          "Synthetic passage one, about the query.",
        ),
        hit(
          1,
          "Synthetic source two",
          "Synthetic passage two, about the query.",
        ),
      ],
    },
    [
      {
        concept_id: "synthetic-concept",
        preferred_label: "Synthetic concept",
        short_description: "Synthetic: what the concept names.",
        score: 3,
        matched_on: "synthetic term",
      },
    ],
  );

/** The verbatim evidence of an exact citation. */
export const referenceCitation = (query: string): ReferenceServed =>
  answer(
    query,
    {
      mode: "citation",
      citation: {
        citation_id: query,
        document_id: "synthetic-document",
        kind: "synthetic-kind",
        corpus_ref: "synthetic/source-citation",
        permalink: "cadrumo://corpus/synthetic/source-citation",
        article: "1",
        section: null,
        anchor: null,
        verbatim_text: "Synthetic verbatim text of the cited provision.",
      },
    },
    [],
  );

/** An answer that holds no passage, no citation and no terminology. */
export const referenceNothing = (query: string): ReferenceServed =>
  answer(query, {}, []);

/** What the scenario host answers for `query`. */
export function referenceFixture(query: string): ReferenceServed {
  if (query === CITATION_QUERY) return referenceCitation(query);
  if (query === NO_MATCH_QUERY) return referenceNothing(query);
  return referenceFound(query);
}
