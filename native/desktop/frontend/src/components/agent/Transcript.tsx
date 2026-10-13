import { useLayoutEffect, useRef } from "react";
import { cn } from "@/components/ui/cn";
import { Empty, EmptyDescription } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { useStrings, type Translate } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";
import { KIND_GLYPH } from "./files";
import type {
  SentFile,
  ToolActivityState,
  TranscriptItem,
  TranscriptMessage,
  TranscriptToolActivity,
} from "./types";

/** The sent files a turn names before it folds the rest into a count. */
const FILES_SHOWN = 6;

/** How far from the bottom, in pixels, still counts as reading the newest. */
const NEWEST_SLACK = 8;

const lists = new Map<string, Intl.ListFormat>();

/** Names joined as the locale joins a list of things. */
function listFormat(locale: string): Intl.ListFormat {
  let format = lists.get(locale);
  if (!format) {
    format = new Intl.ListFormat(locale, {
      style: "long",
      type: "conjunction",
    });
    lists.set(locale, format);
  }
  return format;
}

function toolWords(t: Translate): Record<ToolActivityState, string> {
  return {
    running: t("desktop.agent.tool_running"),
    done: t("desktop.agent.tool_done"),
    refused: t("desktop.agent.refused"),
  };
}

/** The files that went with a message, read-only, above its bubble. */
function SentFiles({
  files,
  locale,
}: {
  files: readonly SentFile[];
  locale: string;
}) {
  const t = useStrings();
  const shown = files.slice(0, FILES_SHOWN);
  const folded = files.slice(FILES_SHOWN);
  return (
    <ul
      aria-label={t("desktop.agent.sent_files")}
      className="flex max-w-full flex-wrap justify-end gap-1"
    >
      {shown.map((file) => (
        <li
          key={file.id}
          title={file.name}
          className="flex h-control-xs max-w-40 min-w-0 items-center gap-1 rounded-full border bg-card px-2 text-xs text-foreground"
        >
          <Icon
            name={KIND_GLYPH[file.kind]}
            size="xs"
            className="text-muted-foreground"
          />
          <span className="truncate">{file.name}</span>
        </li>
      ))}
      {folded.length > 0 && (
        <li
          title={listFormat(locale).format(folded.map((file) => file.name))}
          className="flex h-control-xs items-center rounded-full border bg-card px-2 text-xs text-muted-foreground"
        >
          {t("desktop.agent.more_files", { count: folded.length })}
        </li>
      )}
    </ul>
  );
}

function PersonTurn({
  message,
  locale,
}: {
  message: Extract<TranscriptMessage, { kind: "person" }>;
  locale: string;
}) {
  const t = useStrings();
  const files = message.files ?? [];
  return (
    <li className="flex justify-end pl-8">
      <article
        aria-label={t("desktop.agent.you_said")}
        className="flex min-w-0 flex-col items-end gap-1"
      >
        {files.length > 0 && <SentFiles files={files} locale={locale} />}
        {message.text && (
          <p className="max-w-full rounded-lg bg-accent px-3 py-2 whitespace-pre-wrap text-foreground wrap-anywhere">
            {message.text}
          </p>
        )}
        {message.sentAtLabel && (
          <span className="text-xs text-muted-foreground">
            {message.sentAtLabel}
          </span>
        )}
      </article>
    </li>
  );
}

function AgentTurn({
  message,
  onRetry,
}: {
  message: Extract<TranscriptMessage, { kind: "agent" }>;
  onRetry?: () => void;
}) {
  const t = useStrings();
  const { text, state } = message;
  return (
    <li className="pr-4">
      <article
        aria-label={t("desktop.agent.agent_replied")}
        className="grid min-w-0 gap-1.5"
      >
        {text && (
          <p className="whitespace-pre-wrap text-foreground wrap-anywhere">
            {text}
          </p>
        )}
        {state === "working" && message.waitingOnPerson && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.agent.waiting_on_you")}
          </p>
        )}
        {state === "working" && !message.waitingOnPerson && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <span
              aria-hidden="true"
              className="size-1.5 shrink-0 rounded-full bg-muted-foreground motion-safe:animate-pulse"
            />
            {t("desktop.agent.working")}
          </p>
        )}
        {state === "stopped" && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.agent.stopped")}
          </p>
        )}
        {state === "failed" && (
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5 rounded-md bg-accent px-3 py-2">
            <p className="flex min-w-0 flex-1 basis-40 items-start gap-2 text-sm text-foreground wrap-anywhere">
              <Icon name="alert" className="mt-0.5 text-destructive" />
              <span>
                {message.failureReason ?? t("desktop.agent.reply_failed")}
              </span>
            </p>
            <AgentTextAction variant="outline" size="xs" onAction={onRetry}>
              {t("desktop.agent.retry")}
            </AgentTextAction>
          </div>
        )}
      </article>
    </li>
  );
}

function ToolRow({ activity }: { activity: TranscriptToolActivity }) {
  const t = useStrings();
  const { state } = activity;
  const refused = state === "refused";
  return (
    <li className="flex min-w-0 items-start gap-2 pr-4 text-sm text-muted-foreground">
      {state === "running" ? (
        <Spinner className="mt-0.5" />
      ) : (
        <Icon
          name={refused ? "alert" : "check"}
          className={cn("mt-0.5", refused && "text-destructive")}
        />
      )}
      <div className="grid min-w-0 flex-1">
        <span className="wrap-anywhere">
          {activity.label}
          <span className="sr-only">, {toolWords(t)[state]}</span>
        </span>
        {activity.detail && (
          <span className="text-xs wrap-anywhere">{activity.detail}</span>
        )}
      </div>
    </li>
  );
}

/**
 * The conversation so far, oldest first and newest at the bottom: what the
 * person said, with the files they sent, what the agent replied, and the
 * Cadrumo tools it called on the way. It draws what it is given and nothing
 * more; text is shown as written, line breaks kept, with no formatting read
 * into it.
 *
 * While `followNewest` holds, the list stays at the bottom as it grows,
 * unless the person has scrolled away from the bottom; scrolling back down
 * resumes following.
 */
export function Transcript({
  items,
  locale,
  emptyHint,
  onRetry,
  followNewest = true,
}: {
  items: readonly TranscriptItem[];
  locale: string;
  /** What an empty conversation says in place of the default hint. */
  emptyHint?: string;
  /** Ask again for a failed reply. Without it, Retry says it is not
   * available. */
  onRetry?: (id: string) => void;
  /** Keep the newest turn in view as the conversation grows. */
  followNewest?: boolean;
}) {
  const t = useStrings();
  const scroller = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  // Whether the person is reading the bottom of the list. Only their own
  // scrolling changes it; growth of the list below them does not.
  const atNewest = useRef(true);

  const readPosition = () => {
    const el = scroller.current;
    if (!el) return;
    atNewest.current =
      el.scrollHeight - el.scrollTop - el.clientHeight <= NEWEST_SLACK;
  };

  // The list follows its newest turn when the items change and whenever its
  // content or its own height changes size, as a reply grows or the column
  // is resized.
  useLayoutEffect(() => {
    const el = scroller.current;
    const inner = content.current;
    if (!el || !inner || !followNewest) return;
    const follow = () => {
      if (atNewest.current) el.scrollTop = el.scrollHeight;
    };
    follow();
    const observer = new ResizeObserver(follow);
    observer.observe(el);
    observer.observe(inner);
    return () => observer.disconnect();
  }, [items, followNewest]);

  return (
    <div
      ref={scroller}
      role="log"
      aria-live="polite"
      aria-label={t("desktop.agent.transcript")}
      tabIndex={0}
      onScroll={readPosition}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto focus-visible:-outline-offset-2"
    >
      <div ref={content} className="flex flex-1 flex-col">
        {items.length === 0 ? (
          <Empty>
            <EmptyDescription>
              {emptyHint ?? t("desktop.agent.transcript_empty")}
            </EmptyDescription>
          </Empty>
        ) : (
          <ol className="mt-auto grid gap-4 px-3 py-4">
            {items.map((item) =>
              item.kind === "person" ? (
                <PersonTurn key={item.id} message={item} locale={locale} />
              ) : item.kind === "agent" ? (
                <AgentTurn
                  key={item.id}
                  message={item}
                  onRetry={onRetry ? () => onRetry(item.id) : undefined}
                />
              ) : (
                <ToolRow key={item.id} activity={item} />
              ),
            )}
          </ol>
        )}
      </div>
    </div>
  );
}
