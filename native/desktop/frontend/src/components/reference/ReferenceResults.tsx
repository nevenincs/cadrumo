import { useStrings } from "../../shell/strings";
import type {
  CitationResolution,
  ReferenceServed,
  RetrievalHit,
  TerminologyHit,
} from "../../shell/referenceContract";

/** One block of the answer: its heading and what it holds. */
function Block({
  name,
  heading,
  children,
}: {
  name: "passages" | "citation" | "terminology";
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={heading}
      data-reference={name}
      className="flex flex-col gap-2 rounded-lg border bg-card p-3"
    >
      <h3 className="text-base font-semibold text-foreground">{heading}</h3>
      {children}
    </section>
  );
}

/** The verbatim text of an exact citation, under the identity and place the
 * product resolved it to. */
function Citation({ citation }: { citation: CitationResolution }) {
  const t = useStrings();
  const place = [
    citation.article === null
      ? null
      : t("desktop.reference.article", { article: citation.article }),
    citation.section === null
      ? null
      : t("desktop.reference.section", { section: citation.section }),
  ].filter((part) => part !== null);
  return (
    <div data-reference-citation={citation.citation_id} className="text-sm">
      <p className="font-medium text-foreground">
        <code>{citation.citation_id}</code>{" "}
        <span className="text-muted-foreground">{citation.kind}</span>
      </p>
      {place.length > 0 && (
        <p className="text-muted-foreground">{place.join(" · ")}</p>
      )}
      <p className="text-muted-foreground">
        {t("desktop.reference.source", { source: citation.corpus_ref })}
      </p>
      <p className="text-muted-foreground [overflow-wrap:anywhere]">
        <code>{citation.permalink}</code>
      </p>
      <blockquote className="mt-2 border-l-2 pl-3 whitespace-pre-wrap text-foreground">
        {citation.verbatim_text}
      </blockquote>
    </div>
  );
}

function Passage({ hit }: { hit: RetrievalHit }) {
  const t = useStrings();
  return (
    <li data-reference-hit={hit.chunk_id} className="flex flex-col gap-1">
      <h4 className="text-sm font-medium text-foreground">{hit.doc_title}</h4>
      <p className="text-sm whitespace-pre-wrap text-foreground">{hit.text}</p>
      <p className="text-xs text-muted-foreground [overflow-wrap:anywhere]">
        {t("desktop.reference.source", { source: hit.corpus_ref })}
      </p>
    </li>
  );
}

function Term({ hit }: { hit: TerminologyHit }) {
  const t = useStrings();
  return (
    <li
      data-reference-term={hit.concept_id}
      className="flex flex-col gap-0.5 text-sm"
    >
      <span className="font-medium text-foreground">{hit.preferred_label}</span>
      {hit.short_description !== "" && (
        <span className="text-foreground">{hit.short_description}</span>
      )}
      <span className="text-xs text-muted-foreground">
        <code>{hit.concept_id}</code> ·{" "}
        {t("desktop.reference.matched_on", { term: hit.matched_on })}
      </span>
    </li>
  );
}

/**
 * What the bundled corpus answered, as it served it: the exact citation
 * when the query named one, the ranked passages, and the terminology the
 * query names. A search that matched no passage and no citation says so; an
 * answer is never drawn as nothing found where the search itself failed.
 */
export function ReferenceResults({ served }: { served: ReferenceServed }) {
  const t = useStrings();
  const { retrieval, terminology } = served;
  const passages = retrieval.hits;
  return (
    <div data-reference-results="" className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {t("desktop.reference.results", { query: retrieval.query })}
      </h2>
      {retrieval.citation !== null && (
        <Block name="citation" heading={t("desktop.reference.citation")}>
          <Citation citation={retrieval.citation} />
        </Block>
      )}
      {retrieval.citation === null && (
        <Block name="passages" heading={t("desktop.reference.passages")}>
          {passages.length === 0 ? (
            <p
              data-reference-empty=""
              className="text-sm text-muted-foreground"
            >
              {t("desktop.reference.empty", { query: retrieval.query })}
            </p>
          ) : (
            <ol className="flex flex-col gap-3">
              {passages.map((hit) => (
                <Passage key={hit.chunk_id} hit={hit} />
              ))}
            </ol>
          )}
        </Block>
      )}
      {terminology.length > 0 && (
        <Block name="terminology" heading={t("desktop.reference.terminology")}>
          <ul className="flex flex-col gap-2">
            {terminology.map((hit) => (
              <Term key={hit.concept_id} hit={hit} />
            ))}
          </ul>
        </Block>
      )}
    </div>
  );
}
