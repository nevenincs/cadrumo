import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { failureCode } from "../../errors";
import { uploadRefusalWords } from "../../shell/agentStaging";
import { useStrings, type Translate } from "../../shell/strings";
import { refusalWords } from "./agentRefusalWords";

/** A Libro movement handed to the column, in the conversation it was handed
 * to: still being stored, staged under the name it was stored as, or
 * refused with the words that say why. */
export type HandedMovement = {
  reader: string | null;
  conversation: string | null;
} & (
  | { kind: "storing" }
  | { kind: "staged"; name: string }
  | { kind: "refused"; words: string }
);

/** Refusals of the storage itself, which the attachment words say. */
const STORAGE_REFUSALS: readonly string[] = [
  "agent_attachment_too_large",
  "agent_attachment_format_refused",
  "agent_attachment_name_refused",
  "agent_attachment_unreadable",
  "agent_gateway_attachment_too_large",
  "agent_gateway_attachment_format_refused",
  "agent_gateway_attachment_quota_exceeded",
];

/** Why a movement was not stored, in words: the sentence the ledger served
 * for its refusal, as served; else the words for the agent's code. */
export function movementRefusalWords(
  t: Translate,
  error: unknown,
  maxFileBytes: number | null,
): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "refusal_words" in error &&
    typeof error.refusal_words === "string" &&
    error.refusal_words.trim() !== ""
  )
    return error.refusal_words;
  const code = failureCode(error);
  if (code === "agent_movement_unreadable")
    return t("desktop.agent.movement_unreadable");
  return STORAGE_REFUSALS.includes(code)
    ? uploadRefusalWords(t, code, maxFileBytes)
    : refusalWords(t, code);
}

/**
 * What the column says over the composer of a movement the Libro handed it:
 * that it is being added; once staged, what the attachment holds, that
 * nothing goes until the person sends, and who reads it when it does where
 * that is off this computer; or why it was refused.
 */
export function MovementNotice({
  shown,
  sharedWith,
  onDismiss,
}: {
  shown: HandedMovement;
  /** The provider the selected lane sends to, where it reads off this
   * computer; null where it reads here. */
  sharedWith: string | null;
  onDismiss: () => void;
}) {
  const t = useStrings();
  if (shown.kind === "storing")
    return (
      <p
        role="status"
        data-movement-notice="storing"
        className="text-sm text-muted-foreground"
      >
        {t("desktop.agent.movement_storing")}
      </p>
    );
  if (shown.kind === "refused")
    return (
      <p
        role="alert"
        data-movement-notice="refused"
        className="flex items-start gap-2 text-sm"
      >
        <Icon name="alert" className="mt-0.5 text-destructive" />
        <span className="min-w-0 flex-1">{shown.words}</span>
        <IconButton
          label={t("desktop.agent.movement_dismiss")}
          onClick={onDismiss}
        >
          <Icon name="close" />
        </IconButton>
      </p>
    );
  return (
    <div
      role="note"
      data-movement-notice="staged"
      className="grid gap-1 text-sm text-muted-foreground"
    >
      <p>{t("desktop.agent.movement_staged", { name: shown.name })}</p>
      {sharedWith !== null && (
        <p data-movement-shared>
          {t("desktop.agent.movement_shared", { provider: sharedWith })}
        </p>
      )}
    </div>
  );
}
