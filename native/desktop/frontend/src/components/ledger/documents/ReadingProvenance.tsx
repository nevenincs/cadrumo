import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { EvidenceDraft } from "../../../shell/ledgerDocumentOperations";
import type { Translate } from "../../../shell/strings";
import { provenanceOf, readValue, type ReadingField } from "./documentsModel";
import { doubtful, provenanceText, reasonLabel } from "./documentWords";

/** The finding that asks about a field, and how to go to it. */
export type Question = { words: string | null; go(): void };

/**
 * Where a value came from, as a glyph: its words are the tooltip and what a
 * screen reader hears, so the column stays one glyph wide. A field a
 * finding asks about is flagged, and its glyph goes to that finding.
 */
export function Provenance({
  t,
  draft,
  field,
  edited,
  question,
}: {
  t: Translate;
  draft: EvidenceDraft;
  field: ReadingField;
  edited: boolean;
  question: Question | null;
}) {
  const found = edited ? null : provenanceOf(draft, field);
  const [glyph, words] = edited
    ? [
        <Icon key="edited" name="edit" size="xs" />,
        t("desktop.ledger.documents.entered_by_you"),
      ]
    : found
      ? [
          doubtful(found) ? (
            <Icon key="doubt" name="alert" size="xs" className="text-warning" />
          ) : (
            <Icon
              key="read"
              name="tick"
              size="xs"
              className="text-muted-foreground"
            />
          ),
          provenanceText(t, found),
        ]
      : readValue(draft, field) === null
        ? [
            <Icon
              key="unread"
              name="pending"
              size="xs"
              className="text-muted-foreground"
            />,
            t("desktop.ledger.documents.not_read"),
          ]
        : [
            <Icon
              key="unknown"
              name="info"
              size="xs"
              className="text-muted-foreground"
            />,
            t("desktop.ledger.documents.no_provenance"),
          ];
  if (question)
    return (
      <IconButton
        className="ledger-provenance ledger-provenance-question text-warning"
        label={words}
        hint={t("desktop.ledger.documents.go_to_question", {
          reason: reasonLabel(t, question.words),
        })}
        side="right"
        onClick={question.go}
      >
        <Icon name="alert" size="xs" />
      </IconButton>
    );
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="ledger-provenance inline-flex size-icon-sm items-center justify-center text-sm text-muted-foreground">
          {glyph}
          <span className="sr-only">{words}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{words}</TooltipContent>
    </Tooltip>
  );
}
