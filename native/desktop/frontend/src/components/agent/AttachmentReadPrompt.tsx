import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { failureCode } from "../../errors";
import type { AgentSession } from "../../shell/agentSession";
import type {
  AttachmentCardAnswer,
  AttachmentReleaseAnswer,
  ReleaseScope,
} from "../../shell/attachmentAdminContract";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";
import { ConsentPrompt } from "./ConsentPrompt";
import { barKey, isBar, type BarredRead } from "./AttachmentBarNotice";
import type { AgentApproval } from "../../shell/agentSnapshotContract";

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
    case "cloud_upload_not_permitted":
    case "profile_not_eligible":
      return barKey(code);
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
  onBarred,
  quiet,
  plain,
}: {
  session: Pick<AgentSession, "attachmentCard" | "attachmentRelease">;
  approval: AgentApproval;
  disabled: boolean;
  /** The agent's request has been answered. */
  onSettled: () => void;
  onDecline: (() => void) | undefined;
  /** The service refused the read because the installation or profile keeps
   * documents on this computer: the caller words it once for the run. */
  onBarred: (read: BarredRead) => void;
  /** Draws nothing: the caller is answering this read for the person. */
  quiet: boolean;
  plain: ReactNode;
}) {
  const t = useStrings();
  const [card, setCard] = useState<AttachmentCardAnswer | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [refusedFile, setRefusedFile] = useState<string | null>(null);
  const [sent, setSent] = useState<Sent>("idle");
  const allowOnce = approval.options.find(
    (option) => option.kind === "allow_once",
  )?.option_id;
  const asked = useRef(false);

  // A refusal that names the file and the lane it was bound for, when it is a
  // bar of the installation or profile.
  const noteBar = useCallback(
    (refused: AttachmentCardAnswer | AttachmentReleaseAnswer) => {
      if (refused.kind !== "refused") return;
      setRefusedFile(refused.name);
      if (isBar(refused.code) && refused.name && refused.provider)
        onBarred({
          requestId: approval.request_id,
          replyId: approval.reply_id,
          code: refused.code,
          name: refused.name,
          provider: refused.provider,
        });
    },
    [approval, onBarred],
  );

  const answer = useCallback(
    async (scope: ReleaseScope | null) => {
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
          noteBar(answered);
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
    [session, approval, allowOnce, onSettled, noteBar],
  );

  // The person's refusal is told to the agent first, so the model hears that
  // they declined; the request is declined whether or not that was recorded.
  const decline = useMemo(() => {
    if (!onDecline) return undefined;
    return () => {
      if (!allowOnce) return onDecline();
      session
        .attachmentRelease(approval, allowOnce, "decline")
        .catch(() => undefined)
        .finally(onDecline);
    };
  }, [session, approval, allowOnce, onDecline]);

  useEffect(() => {
    if (asked.current) return;
    asked.current = true;
    void session.attachmentCard(approval).then(
      (read) => {
        setCard(read);
        noteBar(read);
        if (read.kind === "card" && read.existing_grant) void answer(null);
      },
      (error: unknown) => setRefusal(failureCode(error)),
    );
    // One read is one question: the ref keeps a later render from asking again.
  }, [session, approval, answer, noteBar]);

  if (card?.kind === "not_required") return <>{plain}</>;
  if (quiet) return null;
  const refused = refusal ?? (card?.kind === "refused" ? card.code : null);
  const file = refusedFile ?? (card?.kind === "refused" ? card.name : null);
  const reason =
    refused &&
    (file
      ? t("desktop.agent.attachment_refused_named", {
          name: file,
          reason: t(refusalKey(refused)),
        })
      : t("desktop.agent.attachment_refused", {
          reason: t(refusalKey(refused)),
        }));
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
        onDecline={decline}
      />
    </div>
  );
}
