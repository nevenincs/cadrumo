import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { listed } from "../../../shell/compose";
import { servedNextStep, type LedgerNextStep } from "../../../shell/ledger";
import type { LabelReadingFallbackProjectionV1 } from "../../../shell/ledgerDocumentContract";
import { provisionActionOf } from "../../../shell/provisioningRecovery";
import { useStrings } from "../../../shell/strings";
import { SetupOffer } from "../../setup/SetupOffer";
import { fieldLabel } from "./documentWords";
import { ServedStep } from "./ServedStep";

/** How the last reading or confirmation went, when it needs saying. */
export type ReviewNotice =
  | { kind: "changed" }
  /** `recovery` is the setup action the refusal names, if any; `words`
   * the sentence the backend served for it, if any; `step` the step it
   * served for putting it right, if any. */
  | {
      kind: "refused";
      code: string;
      recovery: string | null;
      words: string | null;
      step: LedgerNextStep | null;
    }
  | { kind: "unknown" }
  | { kind: "failed"; code: string }
  | { kind: "checked"; saved: boolean };

/**
 * What the review says above the reading: a reading that changed, a
 * refused, failed or unknown outcome and its check, and the fields the
 * reading model could not read.
 */
export function ReviewNotices({
  notice,
  busy,
  fallback,
  onCheck,
}: {
  notice: ReviewNotice | null;
  /** A read, confirmation or check is in flight. */
  busy: boolean;
  fallback: LabelReadingFallbackProjectionV1 | null | undefined;
  /** Learns what an unknown outcome came to. */
  onCheck(): void;
}) {
  const t = useStrings();
  return (
    <>
      {notice?.kind === "changed" && (
        <Alert tone="warning" role="alert" icon={<Icon name="alert" />}>
          {t("desktop.ledger.documents.reading_changed")}
        </Alert>
      )}
      {(notice?.kind === "refused" || notice?.kind === "failed") && (
        <Alert tone="danger" role="alert" icon={<Icon name="refused" />}>
          <AlertTitle>{t("desktop.ledger.documents.not_done")}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            {notice.kind === "refused" && notice.words && (
              <span className="ledger-draft-refusal">{notice.words}</span>
            )}
            {notice.kind === "refused" && (
              <SetupOffer action={notice.recovery} />
            )}
            {notice.kind === "refused" && <ServedStep step={notice.step} />}
          </AlertDescription>
        </Alert>
      )}
      {notice?.kind === "unknown" && (
        <Alert tone="warning" role="alert" icon={<Icon name="unknown" />}>
          <AlertTitle>{t("desktop.ledger.documents.unknown")}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            {t("desktop.ledger.documents.unknown_note")}
            <Button
              size="xs"
              variant="outline"
              className="ledger-draft-check"
              disabled={busy}
              onClick={onCheck}
            >
              {t("desktop.ledger.documents.check")}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {notice?.kind === "checked" && (
        <Alert icon={<Icon name="info" />} className="ledger-draft-checked">
          {notice.saved
            ? t("desktop.ledger.documents.checked_saved")
            : t("desktop.ledger.documents.checked_not_saved")}
        </Alert>
      )}
      {fallback && (
        <Alert
          tone="warning"
          icon={<Icon name="pause" />}
          className="ledger-draft-unread"
        >
          <AlertTitle>{t("desktop.ledger.documents.unread")}</AlertTitle>
          <AlertDescription className="grid gap-2">
            <span>
              {listed(
                t,
                fallback.unread_fields.map((field) => fieldLabel(t, field)),
              )}
            </span>
            {fallback.refusal_words && (
              <span className="ledger-draft-unread-refusal">
                {fallback.refusal_words}
              </span>
            )}
            <SetupOffer
              action={provisionActionOf(fallback)}
              className="justify-self-start"
            />
            <ServedStep
              step={servedNextStep(fallback)}
              className="justify-self-start"
            />
          </AlertDescription>
        </Alert>
      )}
    </>
  );
}
