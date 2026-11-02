import { useCallback, useEffect, useState } from "react";
import type {
  AgentSession,
  AgentAttachmentGrants,
} from "../../shell/agentSession";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";

/**
 * The permissions the person asked to be remembered, each revocable here. A
 * revoked one stops working at the next read, which asks again. It shows nothing
 * while there are none, and nothing when the service cannot say.
 */
export function AttachmentGrants({
  session,
}: {
  session: Pick<AgentSession, "attachmentGrants" | "attachmentGrantRevoke">;
}) {
  const t = useStrings();
  const [listed, setListed] = useState<AgentAttachmentGrants | null>(null);
  const refresh = useCallback(() => {
    session.attachmentGrants().then(setListed, () => setListed(null));
  }, [session]);
  useEffect(refresh, [refresh]);

  if (listed?.kind !== "grants" || listed.grants.length === 0) return null;
  return (
    <section className="grid gap-1 border-t px-2 py-2 text-sm">
      <h3 className="font-medium text-foreground">
        {t("desktop.agent.attachment_grants_title")}
      </h3>
      <ul className="grid gap-1">
        {listed.grants.map((grant) => (
          <li
            key={grant.grant_id}
            className="flex min-w-0 items-center justify-between gap-2"
          >
            <span className="truncate text-muted-foreground">
              {grant.action === "page_images" || grant.display_name === null
                ? t("desktop.agent.attachment_grant_images", {
                    model: grant.model,
                  })
                : t("desktop.agent.attachment_grant_document", {
                    name: grant.display_name,
                    model: grant.model,
                  })}
            </span>
            <AgentTextAction
              variant="ghost"
              size="xs"
              onAction={() => {
                session
                  .attachmentGrantRevoke(grant.grant_id)
                  .then(refresh, refresh);
              }}
            >
              {t("desktop.agent.attachment_grant_revoke")}
            </AgentTextAction>
          </li>
        ))}
      </ul>
    </section>
  );
}
