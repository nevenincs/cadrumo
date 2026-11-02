import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { failureCode } from "../../errors";
import type {
  AgentApproval,
  AgentAttachmentCard,
  AgentAttachmentScope,
  AgentSession,
} from "../../shell/agentSession";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";
import { ConsentPrompt } from "./ConsentPrompt";

type Sent = "idle" | "sending" | "done";

/** Each refusal in the closed set, in its own words. Any other failure could
 * not be recorded, and says so. */
const refusalKey = (code: string) => {
  switch (code) {
    case "acknowledgement_missing":
      return "desktop.agent.attachment_refusal.acknowledgement_missing";
    case "reference_unknown":
      return "desktop.agent.attachment_refusal.reference_unknown";
    case "document_removed":
      return "desktop.agent.attachment_refusal.document_removed";
    case "gestor_mode":
      return "desktop.agent.attachment_refusal.gestor_mode";
    case "cloud_upload_not_permitted":
      return "desktop.agent.attachment_refusal.cloud_upload_not_permitted";
    case "profile_not_eligible":
      return "desktop.agent.attachment_refusal.profile_not_eligible";
    case "file_changed_during_read":
      return "desktop.agent.attachment_refusal.file_changed_during_read";
    case "not_signed_in":
      return "desktop.agent.attachment_refusal.not_signed_in";
    case "grant_revoked":
      return "desktop.agent.attachment_refusal.grant_revoked";
    default:
      return "desktop.agent.attachment_refusal.service_failed";
  }
};

/**
 * The question asked when an agent's read of an attached file would leave this
 * computer. The service says what the read is; the agent's own request words
 * none of it. A grant the service already holds is answered without asking, and
 * a read that stays here is left to `plain`, the ordinary approval.
 */
export function AttachmentReadPrompt({
  session,
  approval,
  disabled,
  onSettled,
  onDecline,
  plain,
}: {
  session: Pick<AgentSession, "attachmentCard" | "attachmentRelease">;
  approval: AgentApproval;
  disabled: boolean;
  /** The agent's request has been answered. */
  onSettled: () => void;
  onDecline: (() => void) | undefined;
  plain: ReactNode;
}) {
  const t = useStrings();
  const [card, setCard] = useState<AgentAttachmentCard | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [sent, setSent] = useState<Sent>("idle");
  const allowOnce = approval.options.find(
    (option) => option.kind === "allow_once",
  )?.option_id;
  const asked = useRef(false);

  const answer = useCallback(
    async (scope: AgentAttachmentScope | null) => {
      if (!allowOnce) return;
      setSent("sending");
      setRefusal(null);
      try {
        const answered = await session.attachmentRelease(
          approval,
          allowOnce,
          scope,
        );
        if (answered.kind === "refused") {
          setRefusal(answered.code);
          setSent("idle");
          return;
        }
        setSent("done");
        onSettled();
      } catch (error) {
        setRefusal(failureCode(error));
        setSent("idle");
      }
    },
    [session, approval, allowOnce, onSettled],
  );

  useEffect(() => {
    if (asked.current) return;
    asked.current = true;
    void session.attachmentCard(approval).then(
      (read) => {
        setCard(read);
        if (read.kind === "card" && read.existing_grant) void answer(null);
      },
      (error: unknown) => setRefusal(failureCode(error)),
    );
    // One read is one question: the ref keeps a later render from asking again.
  }, [session, approval, answer]);

  if (card?.kind === "not_required") return <>{plain}</>;
  const refused = refusal ?? (card?.kind === "refused" ? card.code : null);
  const reason =
    refused &&
    t("desktop.agent.attachment_refused", {
      reason: t(refusalKey(refused)),
    });
  if (card?.kind !== "card" || (card.existing_grant && !refused)) {
    return reason ? (
      <section className="grid gap-2 rounded-xl bg-card p-3.5 text-sm shadow-raised">
        <p className="text-foreground">{reason}</p>
        {onDecline && (
          <div className="flex justify-end">
            <AgentTextAction variant="outline" size="sm" onAction={onDecline}>
              {t("desktop.agent.consent_decline")}
            </AgentTextAction>
          </div>
        )}
      </section>
    ) : null;
  }
  const images = card.action === "page_images";
  const active = !disabled && sent === "idle" && !!allowOnce;
  return (
    <div className="grid gap-2">
      {reason && <p className="text-sm text-foreground">{reason}</p>}
      <ConsentPrompt
        providerName={card.provider}
        modelName={card.model}
        contentItems={[
          {
            id: card.name,
            label: t(
              images
                ? "desktop.agent.consent_page_images"
                : "desktop.agent.consent_document_text",
              { name: card.name },
            ),
          },
        ]}
        warning={
          images ? t("desktop.agent.consent_page_images_warning") : undefined
        }
        onAllow={active ? () => void answer("once") : undefined}
        onAllowSession={active ? () => void answer("session") : undefined}
        onAllowRemember={active ? () => void answer("remember") : undefined}
        onDecline={onDecline}
      />
    </div>
  );
}
