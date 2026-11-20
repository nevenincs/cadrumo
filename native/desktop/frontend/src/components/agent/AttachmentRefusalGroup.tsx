import {
  isBarCode,
  refusalKey,
  type BarredGroup,
} from "../../shell/attachmentRefusals";
import { useStrings } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";

/**
 * What the person is told when the service bars every read that would leave
 * this computer: the files, once, with the reason and what controls it. A bar
 * that the profile's own setting controls offers the way to that setting;
 * the others have no setting to open and do not pretend to, and a profile the
 * service could not read is retried, not changed. Sending stays
 * declined, answering every read the agent is waiting on.
 */
export function AttachmentRefusalGroup({
  group,
  onDecline,
  onOpenProfile,
}: {
  group: BarredGroup;
  /** Answers every parked read of the group as declined. */
  onDecline: (() => void) | undefined;
  /** Opens the profile page, where the setting lives; absent where the window
   * has no way to. */
  onOpenProfile: (() => void) | undefined;
}) {
  const t = useStrings();
  if (!isBarCode(group.code)) return null;
  const reason = t(refusalKey(group.code));
  const [only] = group.names;
  return (
    <section
      aria-label={t("desktop.agent.attachment_refused_title")}
      className="grid gap-2 rounded-xl bg-card p-3.5 text-sm shadow-raised"
    >
      <p className="text-foreground">
        {group.names.length === 1 && only !== undefined
          ? t("desktop.agent.attachment_refused_named", { name: only, reason })
          : t("desktop.agent.attachment_refused_group", { reason })}
      </p>
      {group.names.length > 1 && (
        <ul className="grid list-disc gap-0.5 pl-5 text-foreground">
          {group.names.map((name) => (
            <li key={name} className="break-all">
              {name}
            </li>
          ))}
        </ul>
      )}
      <div className="flex justify-end gap-2">
        {group.code === "profile_not_eligible" && onOpenProfile && (
          <AgentTextAction variant="outline" size="sm" onAction={onOpenProfile}>
            {t("desktop.agent.attachment_open_profile")}
          </AgentTextAction>
        )}
        {onDecline && (
          <AgentTextAction variant="outline" size="sm" onAction={onDecline}>
            {t("desktop.agent.consent_decline")}
          </AgentTextAction>
        )}
      </div>
    </section>
  );
}
