import {
  memo,
  useCallback,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/ui/cn";
import { Empty, EmptyDescription } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { useStrings, type Translate } from "../../shell/strings";
import { AgentTextAction } from "./AgentAction";
import { KIND_GLYPH } from "./files";
import { Markdown, type OpenLink } from "./Markdown";
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

/** How much of the agent's thinking the preview keeps: its newest part. */
const THINKING_SHOWN = 4_000;

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
    pending: t("desktop.agent.tool_pending"),
    in_progress: t("desktop.agent.tool_running"),
    completed: t("desktop.agent.tool_done"),
    failed: t("desktop.agent.tool_failed"),
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
        <li key={file.id} title={file.name} className="min-w-0">
          <Badge className="h-control-xs max-w-40 min-w-0">
            <Icon name={KIND_GLYPH[file.kind]} size="xs" />
            <span className="truncate">{file.name}</span>
          </Badge>
        </li>
      ))}
      {folded.length > 0 && (
        <li title={listFormat(locale).format(folded.map((file) => file.name))}>
          <Badge className="h-control-xs">
            {t("desktop.agent.more_files", { count: folded.length })}
          </Badge>
        </li>
      )}
    </ul>
  );
}

/** The skills a message loaded, read-only, above its bubble. */
function SentSkills({ skills }: { skills: readonly string[] }) {
  const t = useStrings();
  return (
    <ul
      aria-label={t("desktop.agent.sent_skills")}
      className="flex max-w-full flex-wrap justify-end gap-1"
    >
      {skills.map((name) => (
        <li key={name} title={name} className="min-w-0">
          <Badge className="h-control-xs max-w-60 min-w-0">
            <span className="truncate font-mono">/{name}</span>
          </Badge>
        </li>
      ))}
    </ul>
  );
}

const PersonTurn = memo(function PersonTurn({
  message,
  locale,
}: {
  message: Extract<TranscriptMessage, { kind: "person" }>;
  locale: string;
}) {
  const t = useStrings();
  const files = message.files ?? [];
  const skills = message.skills ?? [];
  return (
    <li className="flex justify-end pl-8">
      <article
        aria-label={t("desktop.agent.you_said")}
        className="flex min-w-0 flex-col items-end gap-1"
      >
        {files.length > 0 && <SentFiles files={files} locale={locale} />}
        {skills.length > 0 && <SentSkills skills={skills} />}
        {message.text && (
          <p className="max-w-full rounded-lg bg-accent px-3 py-2 whitespace-pre-wrap text-foreground wrap-anywhere">
            {message.text}
          </p>
        )}
        {message.sending ? (
          <span
            role="status"
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <Spinner />
            {t("desktop.agent.sending")}
          </span>
        ) : (
          message.sentAtLabel && (
            <span className="text-xs text-muted-foreground">
              {message.sentAtLabel}
            </span>
          )
        )}
      </article>
    </li>
  );
});

/**
 * A line that opens and closes what is behind it, below it: the agent's
 * thinking or a tool call's internals. It is a button only where there is
 * something to show; otherwise it is the line alone.
 */
function Disclosure({
  label,
  regionLabel,
  className,
  children,
}: {
  label: ReactNode;
  regionLabel: string;
  className?: string;
  /** What opens, or nothing when there is nothing to show. */
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const region = useId();
  if (!children)
    return (
      <p className={cn("flex min-w-0 items-start gap-2", className)}>{label}</p>
    );
  return (
    <div className="grid min-w-0 gap-1">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={region}
        onClick={() => setOpen((was) => !was)}
        className={cn(
          "group flex min-w-0 items-start gap-2 rounded-sm text-left hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2",
          className,
        )}
      >
        {label}
        <Icon
          name={open ? "chevronUp" : "chevronDown"}
          size="xs"
          className="mt-1 shrink-0 opacity-60 group-hover:opacity-100"
        />
      </button>
      {open && (
        <div
          id={region}
          role="region"
          aria-label={regionLabel}
          className="max-h-48 overflow-y-auto border-l-2 border-border pl-2 text-xs text-muted-foreground/80"
        >
          {children}
        </div>
      )}
    </div>
  );
}

/** The newest part of the agent's thinking, as it wrote it. */
function Thinking({ text }: { text: string }) {
  const shown =
    text.length > THINKING_SHOWN ? `…${text.slice(-THINKING_SHOWN)}` : text;
  return <p className="whitespace-pre-wrap wrap-anywhere">{shown}</p>;
}

const AgentTurn = memo(function AgentTurn({
  message,
  onRetry,
  onOpenProviderSettings,
  onOpenLink,
}: {
  message: Extract<TranscriptMessage, { kind: "agent" }>;
  onRetry?: (id: string) => void;
  onOpenProviderSettings?: () => void;
  onOpenLink?: OpenLink;
}) {
  const t = useStrings();
  const { text, state } = message;
  const thinking = message.thinking ? (
    <Thinking text={message.thinking} />
  ) : undefined;
  const working = state === "working" && !message.waitingOnPerson;
  return (
    <li className="grid gap-1.5 pr-4">
      {/* Once the reply is no longer being written, what the agent thought
          on the way stays behind its own line, above what it wrote and apart
          from it. */}
      {thinking && !working && (
        <Disclosure
          label={t("desktop.agent.thinking")}
          regionLabel={t("desktop.agent.thoughts")}
          className="text-xs text-muted-foreground"
        >
          {thinking}
        </Disclosure>
      )}
      <article
        aria-label={t("desktop.agent.agent_replied")}
        className="grid min-w-0 gap-1.5"
      >
        {text && <Markdown text={text} onOpenLink={onOpenLink} />}
        {state === "working" && message.waitingOnPerson && (
          <p className="text-sm text-muted-foreground">
            {t("desktop.agent.waiting_on_you")}
          </p>
        )}
        {working && (
          <Disclosure
            label={
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="size-1.5 shrink-0 rounded-full bg-muted-foreground motion-safe:animate-pulse"
                />
                {t("desktop.agent.working")}
              </span>
            }
            regionLabel={t("desktop.agent.thoughts")}
            className="text-sm text-muted-foreground"
          >
            {thinking}
          </Disclosure>
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
            {message.failureAction === "provider_settings" ? (
              onOpenProviderSettings && (
                <AgentTextAction
                  variant="outline"
                  size="xs"
                  onAction={onOpenProviderSettings}
                >
                  {t("desktop.agent.settings")}
                </AgentTextAction>
              )
            ) : (
              <AgentTextAction
                variant="outline"
                size="xs"
                onAction={onRetry ? () => onRetry(message.id) : undefined}
              >
                {t("desktop.agent.retry")}
              </AgentTextAction>
            )}
          </div>
        )}
      </article>
    </li>
  );
});

const ToolRow = memo(function ToolRow({
  activity,
}: {
  activity: TranscriptToolActivity;
}) {
  const t = useStrings();
  const { state } = activity;
  const failed = state === "failed";
  return (
    <li className="flex min-w-0 items-start gap-2 pr-4 text-sm text-muted-foreground">
      {state === "pending" || state === "in_progress" ? (
        <Spinner className="mt-0.5" />
      ) : (
        <Icon
          name={failed ? "alert" : "check"}
          className={cn("mt-0.5", failed && "text-destructive")}
        />
      )}
      <div className="grid min-w-0 flex-1">
        <Disclosure
          label={
            <span className="wrap-anywhere">
              {activity.label}
              {/* A failed call is said in words, not by its icon alone. */}
              <span className={failed ? "ml-1.5 text-destructive" : "sr-only"}>
                {failed ? "" : ", "}
                {toolWords(t)[state]}
              </span>
            </span>
          }
          regionLabel={t("desktop.agent.tool_details")}
        >
          {activity.internals?.length ? (
            <div className="grid gap-1.5">
              {activity.internals.map((internal, index) => (
                <pre
                  key={index}
                  className="font-mono whitespace-pre-wrap wrap-anywhere"
                >
                  {internal}
                </pre>
              ))}
            </div>
          ) : undefined}
        </Disclosure>
        {activity.detail && (
          <span className="text-xs wrap-anywhere">{activity.detail}</span>
        )}
      </div>
    </li>
  );
});

/**
 * The conversation so far, oldest first and newest at the bottom: what the
 * person said, with the files they sent, what the agent replied, and the
 * Cadrumo tools it called on the way. It draws what it is given and nothing
 * more. The person's words are shown as written, line breaks kept; the
 * agent's are read as the Markdown it writes. What the agent thought, and
 * what a tool call took and gave, open beneath the line that has them.
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
  onOpenProviderSettings,
  onOpenLink,
  followNewest = true,
}: {
  items: readonly TranscriptItem[];
  locale: string;
  /** What an empty conversation says in place of the default hint. */
  emptyHint?: string;
  /** Ask again for a failed reply. Without it, Retry says it is not
   * available. */
  onRetry?: (id: string) => void;
  /** Open the provider settings for a reply that needs sign-in. */
  onOpenProviderSettings?: () => void;
  /** Open an address a reply links to, outside the window. */
  onOpenLink?: OpenLink;
  /** Keep the newest turn in view as the conversation grows. */
  followNewest?: boolean;
}) {
  const t = useStrings();
  // Event handlers always use the current caller without invalidating every
  // completed row when the parent publishes another text chunk.
  const actions = useRef({ onRetry, onOpenProviderSettings, onOpenLink });
  actions.current = { onRetry, onOpenProviderSettings, onOpenLink };
  const retry = useCallback((id: string) => actions.current.onRetry?.(id), []);
  const settings = useCallback(
    () => actions.current.onOpenProviderSettings?.(),
    [],
  );
  const openLink = useCallback(
    (url: string) => actions.current.onOpenLink?.(url),
    [],
  );
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
    let frame: number | undefined;
    const follow = () => {
      if (!atNewest.current || frame !== undefined) return;
      frame = requestAnimationFrame(() => {
        frame = undefined;
        if (atNewest.current) el.scrollTop = el.scrollHeight;
      });
    };
    follow();
    const observer = new ResizeObserver(follow);
    observer.observe(el);
    observer.observe(inner);
    return () => {
      observer.disconnect();
      if (frame !== undefined) cancelAnimationFrame(frame);
    };
  }, [followNewest]);

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
                  onRetry={onRetry ? retry : undefined}
                  onOpenProviderSettings={
                    onOpenProviderSettings ? settings : undefined
                  }
                  onOpenLink={onOpenLink ? openLink : undefined}
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
