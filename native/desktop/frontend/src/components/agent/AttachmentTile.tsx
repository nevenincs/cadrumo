import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../shell/strings";
import { AgentIconAction } from "./AgentAction";
import {
  clampShare,
  extensionLabel,
  formatPercent,
  formatSize,
  KIND_GLYPH,
} from "./files";
import type { StagedAttachment } from "./types";

/** How much of an upload has gone, drawn as a ring with its percentage. */
function UploadRing({
  share,
  locale,
  name,
}: {
  share: number;
  locale: string;
  name: string;
}) {
  const t = useStrings();
  const percent = Math.round(share * 100);
  return (
    <div
      role="progressbar"
      aria-label={t("desktop.agent.uploading_name", { name })}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-valuetext={formatPercent(locale, share)}
      className="relative flex size-control-lg items-center justify-center"
    >
      <svg
        viewBox="0 0 36 36"
        aria-hidden="true"
        className="absolute inset-0 size-full -rotate-90"
      >
        <circle
          cx="18"
          cy="18"
          r="15"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          className="text-foreground/15"
        />
        <circle
          cx="18"
          cy="18"
          r="15"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          pathLength={100}
          strokeDasharray={`${percent} 100`}
          className="text-foreground transition-[stroke-dasharray] duration-(--motion-base)"
        />
      </svg>
      <span className="text-2xs font-medium text-foreground tabular-nums">
        {formatPercent(locale, share)}
      </span>
    </div>
  );
}

/**
 * One file staged for the next message, as a square tile: its preview or
 * type, and where it is on its way to being sent. A refused file says why.
 * Its remove button shows on hover and on focus.
 */
export function AttachmentTile({
  attachment,
  locale,
  onRemove,
}: {
  attachment: StagedAttachment;
  locale: string;
  onRemove?: () => void;
}) {
  const t = useStrings();
  const { name, kind, state } = attachment;
  const size = formatSize(locale, attachment.sizeBytes);
  const refused = state === "refused";
  const reason = attachment.refusalReason ?? t("desktop.agent.refused");
  const preview = kind === "image" && attachment.thumbnailUrl;
  const members =
    kind === "archive" && attachment.memberCount !== undefined
      ? attachment.memberCount === 1
        ? t("desktop.agent.members_single")
        : t("desktop.agent.members_multiple", {
            count: attachment.memberCount,
          })
      : null;
  const stateWords: Record<StagedAttachment["state"], string> = {
    queued: t("desktop.agent.queued"),
    uploading: t("desktop.agent.uploading"),
    ready: t("desktop.agent.ready"),
    refused: reason,
  };
  return (
    <li
      data-state={state}
      title={refused ? `${name} · ${reason}` : `${name} · ${size}`}
      className={cn(
        "group/tile relative flex aspect-square min-w-0 flex-col overflow-hidden rounded-lg border bg-card",
        refused && "border-destructive bg-destructive/5",
      )}
    >
      {preview ? (
        <img
          src={attachment.thumbnailUrl}
          alt=""
          className="absolute inset-0 size-full object-cover"
        />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-0.5 px-1 pt-1">
          <Icon
            name={refused ? "alert" : KIND_GLYPH[kind]}
            size="lg"
            className={refused ? "text-destructive" : "text-muted-foreground"}
          />
          <span
            aria-hidden="true"
            className="text-2xs font-semibold tracking-wide text-muted-foreground"
          >
            {extensionLabel(attachment.extension)}
          </span>
          {members && (
            <span aria-hidden="true" className="text-2xs text-faint">
              {members}
            </span>
          )}
        </div>
      )}
      {(state === "uploading" || state === "queued") && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/90">
          {state === "uploading" ? (
            <UploadRing
              share={clampShare(attachment.progress)}
              locale={locale}
              name={name}
            />
          ) : (
            <Icon name="clock" size="md" className="text-muted-foreground" />
          )}
        </div>
      )}
      <div
        className={cn(
          "relative shrink-0 px-1.5 pb-1 text-2xs",
          preview && "mt-auto bg-card/85 pt-0.5",
        )}
      >
        <p className="truncate text-foreground">{name}</p>
        {refused && (
          <p className="line-clamp-2 text-destructive" aria-hidden="true">
            {reason}
          </p>
        )}
      </div>
      <span className="sr-only">
        {[size, members, stateWords[state]].filter(Boolean).join(", ")}
      </span>
      <AgentIconAction
        icon="close"
        label={t("desktop.agent.remove_file", { name })}
        onAction={onRemove}
        side="top"
        variant="secondary"
        className="absolute top-0.5 right-0.5 opacity-0 group-hover/tile:opacity-100 focus-visible:opacity-100 pointer-coarse:opacity-100"
      />
    </li>
  );
}
