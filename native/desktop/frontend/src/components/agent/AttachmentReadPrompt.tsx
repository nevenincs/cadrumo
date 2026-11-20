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
  ReleaseScope,
} from "../../shell/attachmentAdminContract";
import {
  isBarCode,
  refusalKey,
  type BarredRead,
} from "../../shell/attachmentRefusals";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";
import { ConsentPrompt } from "./ConsentPrompt";
import type { AgentApproval } from "../../shell/agentSnapshotContract";

type Sent = "idle" | "sending" | "done";

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
  plain,
}: {
  session: Pick<AgentSession, "attachmentCard" | "attachmentRelease">;
  approval: AgentApproval;
  disabled: boolean;
  /** The agent's request has been answered. */
  onSettled: () => void;
  onDecline: (() => void) | undefined;
  /** The read was refused for a bar that holds for every off-host read, or no
   * longer is: the column words those once for all the reads it refuses, so
   * this prompt draws nothing for it. */
  onBarred: (
    requestId: string,
    barred: Omit<BarredRead, "requestId"> | null,
  ) => void;
  plain: ReactNode;
}) {
  const t = useStrings();
  const [card, setCard] = useState<AttachmentCardAnswer | null>(null);
  const [refusal, setRefusal] = useState<{
    code: string;
    name: string | null;
  } | null>(null);
  const [sent, setSent] = useState<Sent>("idle");
  const allowOnce = approval.options.find(
    (option) => option.kind === "allow_once",
  )?.option_id;
  const asked = useRef(false);

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
          setRefusal({ code: answered.code, name: answered.name });
          setSent("idle");
          return;
        }
        setSent("done");
        onSettled();
      } catch (error) {
        setRefusal({ code: failureCode(error), name: null });
        setSent("idle");
      }
    },
    [session, approval, allowOnce, onSettled],
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
        if (read.kind === "card" && read.existing_grant) void answer(null);
      },
      (error: unknown) => setRefusal({ code: failureCode(error), name: null }),
    );
    // One read is one question: the ref keeps a later render from asking again.
  }, [session, approval, answer]);

  const refused =
    refusal ??
    (card?.kind === "refused" ? { code: card.code, name: card.name } : null);
  const barCode = refused && isBarCode(refused.code) ? refused.code : null;
  const barName = refused?.name ?? null;
  const requestId = approval.request_id;
  useEffect(() => {
    if (!barCode) return;
    onBarred(requestId, { code: barCode, name: barName });
    return () => onBarred(requestId, null);
  }, [barCode, barName, requestId, onBarred]);

  if (card?.kind === "not_required") return <>{plain}</>;
  if (barCode) return null;
  const reason =
    refused &&
    (refused.name === null
      ? t("desktop.agent.attachment_refused", {
          reason: t(refusalKey(refused.code)),
        })
      : t("desktop.agent.attachment_refused_named", {
          name: refused.name,
          reason: t(refusalKey(refused.code)),
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
