import { useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { readPx } from "../../shell/metrics";
import { useStrings } from "../../shell/strings";
import { AgentIconAction, AgentTextAction } from "./AgentAction";
import { AgentSettingsPopover } from "./AgentSettingsPopover";
import { AttachmentWell } from "./AttachmentWell";
import type {
  AgentSelection,
  ModelOption,
  ProviderOption,
  StagedAttachment,
} from "./types";

/** The lines the message field grows to before it scrolls. */
const MAX_LINES = 8;

/** The model and effort, as the settings button names them. */
function selectionWords(
  models: Readonly<Record<string, readonly ModelOption[]>>,
  selection: AgentSelection,
): string | null {
  const model = (models[selection.providerId] ?? []).find(
    (option) => option.id === selection.modelId,
  );
  if (!model) return null;
  return selection.effort ? `${model.name} · ${selection.effort}` : model.name;
}

/**
 * Where the next message is written: a field that grows with what is typed,
 * the files staged with it, and the controls that add files, choose the
 * model and send. Enter sends, Shift+Enter starts a new line, and a key that
 * ends an input-method composition never sends.
 *
 * The draft is the composer's own until it is sent. `onSend` takes it; the
 * field is cleared unless `onSend` returns false. While `running`, Send is
 * Stop. Nothing is sent while any file is still waiting or uploading.
 */
export function Composer({
  locale,
  attachments,
  providers,
  models,
  selection,
  running = false,
  defaultDraft = "",
  onSend,
  onStop,
  onAddFiles,
  onSelectionChange,
  onRemoveAttachment,
  onRemoveAllAttachments,
  onShowAllAttachments,
}: {
  locale: string;
  attachments: readonly StagedAttachment[];
  providers: readonly ProviderOption[];
  /** Each provider's models, by provider id. */
  models: Readonly<Record<string, readonly ModelOption[]>>;
  selection: AgentSelection;
  /** A reply is being written; Send becomes Stop. */
  running?: boolean;
  defaultDraft?: string;
  /** Send the draft with the ready files. Return false to keep the draft. */
  onSend?: (text: string) => boolean | void;
  onStop?: () => void;
  onAddFiles?: () => void;
  onSelectionChange?: (selection: AgentSelection) => void;
  onRemoveAttachment?: (id: string) => void;
  onRemoveAllAttachments?: () => void;
  onShowAllAttachments?: () => void;
}) {
  const t = useStrings();
  const [draft, setDraft] = useState(defaultDraft);
  const field = useRef<HTMLTextAreaElement>(null);

  // The field is as tall as its text, up to a few lines, then scrolls.
  // It is measured again whenever its width changes, which includes being
  // shown: a field laid out while its column is put away measures nothing,
  // and must not keep that. Never less than one line.
  useLayoutEffect(() => {
    const el = field.current;
    if (!el) return;
    let width = -1;
    const fit = () => {
      if (el.clientWidth === 0) return;
      width = el.clientWidth;
      const style = getComputedStyle(el);
      const chrome =
        parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) || 0;
      const line = readPx("--text-base--line-height", 20);
      const most = line * MAX_LINES + chrome;
      el.style.height = "auto";
      const wanted = Math.max(el.scrollHeight, line + chrome);
      el.style.height = `${Math.min(wanted, most)}px`;
      el.style.overflowY = wanted > most ? "auto" : "hidden";
    };
    fit();
    // Fitted in the next frame, not in the observation itself: a height set
    // while observations are delivered is reported as a loop.
    let frame = 0;
    const observer = new ResizeObserver(() => {
      if (el.clientWidth === width) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(fit);
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [draft]);

  const waiting = attachments.some(
    (file) => file.state === "queued" || file.state === "uploading",
  );
  const sendable =
    draft.trim() !== "" || attachments.some((file) => file.state === "ready");
  const heldBy = waiting
    ? t("desktop.agent.send_waiting")
    : !sendable
      ? t("desktop.agent.send_nothing")
      : undefined;

  const send = () => {
    if (!onSend || heldBy || running) return;
    if (onSend(draft) !== false) setDraft("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.nativeEvent.isComposing ||
      // Some engines report the key that ends a composition only this way.
      event.keyCode === 229
    )
      return;
    event.preventDefault();
    send();
  };

  const current = selectionWords(models, selection);
  const settingsText = current ?? t("desktop.agent.choose_model");
  const settingsName = t("desktop.agent.settings_label", {
    current: settingsText,
  });
  const settingsButton = (
    <Button
      variant="ghost"
      size="xs"
      aria-label={settingsName}
      className="min-w-0"
    >
      <span className="truncate">{settingsText}</span>
      <Icon name="chevronDown" size="xs" />
    </Button>
  );

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-raised has-[textarea:focus-visible]:outline-(length:--focus-ring) has-[textarea:focus-visible]:outline-offset-(length:--focus-ring) has-[textarea:focus-visible]:outline-solid">
      <textarea
        ref={field}
        rows={1}
        value={draft}
        aria-label={t("desktop.agent.message_label")}
        placeholder={t("desktop.agent.message_placeholder")}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
        className="block w-full resize-none bg-transparent px-3 pt-3 pb-1 text-base text-foreground placeholder:text-faint focus-visible:outline-none"
      />
      <div className="flex min-w-0 items-center gap-1 px-2 pb-2">
        <AgentIconAction
          icon="plus"
          label={t("desktop.agent.add_files")}
          side="top"
          onAction={onAddFiles}
        />
        {onSelectionChange ? (
          <AgentSettingsPopover
            providers={providers}
            models={models}
            selection={selection}
            onChange={onSelectionChange}
          >
            {settingsButton}
          </AgentSettingsPopover>
        ) : (
          <AgentTextAction
            variant="ghost"
            size="xs"
            className="min-w-0"
            aria-label={`${settingsName}, ${t("desktop.agent.unavailable")}`}
          >
            <span className="truncate">{settingsText}</span>
            <Icon name="chevronDown" size="xs" />
          </AgentTextAction>
        )}
        <span className="flex-1" />
        {running ? (
          <AgentIconAction
            icon="stop"
            label={t("desktop.agent.stop")}
            side="top"
            variant="primary"
            size="sm"
            className="rounded-full"
            onAction={onStop}
          />
        ) : (
          <AgentIconAction
            icon="send"
            label={t("desktop.agent.send")}
            side="top"
            variant="primary"
            size="sm"
            className="rounded-full"
            heldBy={heldBy}
            onAction={onSend ? send : undefined}
          />
        )}
      </div>
      <AttachmentWell
        attachments={attachments}
        locale={locale}
        onRemove={onRemoveAttachment}
        onRemoveAll={onRemoveAllAttachments}
        onShowAll={onShowAllAttachments}
      />
    </div>
  );
}
