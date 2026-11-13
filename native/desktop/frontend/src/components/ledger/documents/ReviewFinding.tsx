import { useId } from "react";
import { NotesEditor } from "@/components/editors/NotesEditor";
import { TextEditor } from "@/components/editors/TextEditor";
import { Badge } from "@/components/ui/badge";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import type { ConfirmationBlockerProjectionV1 } from "../../../shell/ledgerDocumentReviewContract";
import { useTextLimit } from "../../../shell/ledgerLimits";
import type { Translate } from "../../../shell/strings";
import {
  DERIVED_FIELDS,
  resolutionOf,
  type FindingAnswer,
  type ReadingField,
} from "./documentsModel";
import { fieldLabel, reasonLabel } from "./documentWords";

/** One finding of the reading, answered by choosing a reading, supplying
 * the value, or saying why the value read is right. */
export function Finding({
  id,
  t,
  blocker,
  answer,
  onAnswer,
  printed,
}: {
  /** Where a flagged field's glyph goes. */
  id: string;
  t: Translate;
  blocker: ConfirmationBlockerProjectionV1;
  answer: FindingAnswer | undefined;
  onAnswer(answer: FindingAnswer): void;
  /** The value printed for a field the catalogue works out itself, as
   * shown; null for any other finding. */
  printed: string | null;
}) {
  const group = useId();
  const noteLimit = useTextLimit("confirm_note");
  const valueLimit = useTextLimit("confirm_label");
  const answered = resolutionOf(blocker, answer) !== null;
  const candidates = blocker.candidates ?? [];
  const current = answer ?? { action: "attest", value: "", note: "" };
  // The sentence the backend serves explaining the finding; a reading stored
  // before findings carried their words keeps its recorded explanation.
  const explanation = blocker.detail_words || blocker.detail;
  // A figure the catalogue works out is saved as worked out whatever is
  // answered: the finding says so, and only takes the reason it is accepted.
  const worked =
    blocker.field !== null && blocker.field !== undefined
      ? DERIVED_FIELDS.has(blocker.field as ReadingField)
      : false;
  if (worked)
    return (
      <li
        id={id}
        tabIndex={-1}
        className="ledger-finding grid scroll-m-3 gap-2 rounded-md bg-muted p-3"
        data-answered={answered || undefined}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Icon
            name={answered ? "check" : "alert"}
            size="sm"
            className={answered ? "text-success" : "text-warning"}
          />
          <span className="font-medium">
            {reasonLabel(t, blocker.reason_words)}
          </span>
          {blocker.field && <Badge>{fieldLabel(t, blocker.field)}</Badge>}
        </div>
        {explanation && <p className="text-sm">{explanation}</p>}
        <p className="ledger-finding-worked text-sm">
          {t("desktop.ledger.documents.worked_out", {
            field: fieldLabel(t, blocker.field!),
            printed: printed ?? "—",
          })}
        </p>
        <Field className="ledger-finding-note">
          <FieldLabel htmlFor={`${group}-note`}>
            {t("desktop.ledger.documents.why_right")}
          </FieldLabel>
          <TextEditor
            id={`${group}-note`}
            controlSize="sm"
            maxLength={noteLimit ?? undefined}
            value={answer?.action === "attest" ? answer.note : ""}
            onChange={(note) => onAnswer({ action: "attest", value: "", note })}
          />
        </Field>
      </li>
    );
  return (
    <li
      id={id}
      tabIndex={-1}
      className="ledger-finding grid scroll-m-3 gap-2 rounded-md bg-muted p-3"
      data-answered={answered || undefined}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Icon
          name={answered ? "check" : "alert"}
          size="sm"
          className={answered ? "text-success" : "text-warning"}
        />
        <span className="font-medium">
          {reasonLabel(t, blocker.reason_words)}
        </span>
        {blocker.field && <Badge>{fieldLabel(t, blocker.field)}</Badge>}
      </div>
      {explanation && <p className="text-sm">{explanation}</p>}
      <SegmentedControl
        aria-label={t("desktop.ledger.documents.answer")}
        value={answer?.action ?? ""}
        onValueChange={(action) =>
          onAnswer({
            action: action as FindingAnswer["action"],
            value: "",
            note: current.note,
          })
        }
        className="ledger-finding-action w-fit"
      >
        <SegmentedControlItem
          value="choose_candidate"
          disabled={candidates.length === 0}
          className="text-sm"
        >
          {t("desktop.ledger.documents.action.choose_candidate")}
        </SegmentedControlItem>
        <SegmentedControlItem value="supply_value" className="text-sm">
          {t("desktop.ledger.documents.action.supply_value")}
        </SegmentedControlItem>
        <SegmentedControlItem value="attest" className="text-sm">
          {t("desktop.ledger.documents.action.attest")}
        </SegmentedControlItem>
      </SegmentedControl>
      {answer?.action === "choose_candidate" && (
        <RadioGroup
          aria-label={t("desktop.ledger.documents.readings")}
          value={answer.value}
          onValueChange={(value) => onAnswer({ ...answer, value })}
        >
          {candidates.map((candidate) => (
            <label
              key={candidate.value}
              className="flex cursor-pointer items-center gap-2 text-sm"
            >
              <RadioGroupItem value={candidate.value} />
              <span className="font-mono">{candidate.value}</span>
              {candidate.note && (
                <span className="text-muted-foreground">{candidate.note}</span>
              )}
            </label>
          ))}
        </RadioGroup>
      )}
      {answer?.action === "supply_value" && (
        <Field className="ledger-finding-value">
          <FieldLabel htmlFor={`${group}-value`}>
            {t("desktop.ledger.documents.the_value")}
          </FieldLabel>
          <TextEditor
            id={`${group}-value`}
            controlSize="sm"
            maxLength={valueLimit ?? undefined}
            value={answer.value}
            onChange={(value) => onAnswer({ ...answer, value })}
          />
        </Field>
      )}
      {answer?.action === "attest" && (
        <Field className="ledger-finding-note">
          <FieldLabel htmlFor={`${group}-note`}>
            {t("desktop.ledger.documents.why_right")}
          </FieldLabel>
          <NotesEditor
            id={`${group}-note`}
            controlSize="sm"
            rows={2}
            maxLength={noteLimit ?? undefined}
            value={answer.note}
            onChange={(note) => onAnswer({ ...answer, note })}
          />
        </Field>
      )}
    </li>
  );
}
