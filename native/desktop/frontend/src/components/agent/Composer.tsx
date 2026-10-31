import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Textarea } from "@/components/ui/textarea";
import {
  MAX_CONTINUATION_CHARS,
  characters,
} from "../../shell/agentClarification";
import { described, facts } from "../../shell/compose";
import { readPx } from "../../shell/metrics";
import { useStrings, type Translate } from "../../shell/strings";
import { AgentIconAction, AgentTextAction } from "./AgentAction";
import { AgentSettingsPopover } from "./AgentSettingsPopover";
import { AttachmentWell } from "./AttachmentWell";
import {
  ComposerSuggestions,
  useComposerSuggestions,
  type AnySource,
} from "./ComposerSuggestions";
import { ProviderMark } from "./ProviderMark";
import { useSlashSources } from "./SlashSuggestions";
import {
  MAX_SKILLS_PER_MESSAGE,
  skillCommand,
  skillReferences,
  type AgentSkillSummary,
  type SkillCommand,
} from "../../shell/agentSkills";
import type {
  AgentSelection,
  ModelOption,
  ProviderOption,
  ProviderWay,
  StagedAttachment,
} from "./types";

/** What a message names beside its words, which its send carries as
 * structured references. */
export type ComposerReferences = {
  /** The skills the message's `/name` tokens name, once each. */
  skills: string[];
};

/** The lines the message field grows to before it scrolls. */
const MAX_LINES = 8;

/** The model and effort, as the settings button names them, and the way into
 * its provider; null while none is chosen. */
function selectionWords(
  t: Translate,
  providers: readonly ProviderOption[],
  models: Readonly<Record<string, readonly ModelOption[]>>,
  selection: AgentSelection,
): { provider: ProviderOption; way: ProviderWay; words: string } | null {
  const provider = providers.find((held) => held.id === selection.providerId);
  const way = provider?.ways.find((held) => held.id === selection.wayId);
  if (!provider || !way) return null;
  const model = (models[way.id] ?? []).find(
    (option) => option.id === selection.modelId,
  );
  const name = way.modelWritten ? selection.modelId.trim() : model?.name;
  if (!name) return null;
  const efforts = way.modelWritten?.efforts ?? model?.efforts ?? [];
  // The effort chosen, or else the one the model's catalog applies.
  const effort = efforts.find(
    (held) => held.id === (selection.effort ?? model?.defaultEffort),
  );
  return {
    provider,
    way,
    words: facts(t, [name, effort?.name]),
  };
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
 *
 * `/` at the start or after a space lists cadrumo-agent's skills and the
 * composer's own commands above the field. A message that is one of those
 * commands and a skill is never sent: `onSkillCommand` runs it.
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
  pickerRequests,
  onPickerClosed,
  onRemoveAttachment,
  onRemoveAllAttachments,
  onShowAllAttachments,
  skills,
  onSkillCommand,
  suggestionSources,
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
  onSend?: (text: string, references: ComposerReferences) => boolean | void;
  onStop?: () => void;
  onAddFiles?: () => void;
  onSelectionChange?: (selection: AgentSelection) => void;
  /** Counts the asks from elsewhere to open the model picker. */
  pickerRequests?: number;
  /** Called when the person closes the model picker. */
  onPickerClosed?: () => void;
  onRemoveAttachment?: (id: string) => void;
  onRemoveAllAttachments?: () => void;
  onShowAllAttachments?: () => void;
  /** cadrumo-agent's skills; without it `/` lists nothing. */
  skills?: () => Promise<readonly AgentSkillSummary[]>;
  /** Runs a skill command: reviewing or verifying a skill. */
  onSkillCommand?: (command: SkillCommand) => void;
  /** Further suggestion lists, after the `/` list; memoized. */
  suggestionSources?: readonly AnySource[];
}) {
  const t = useStrings();
  const [draft, setDraft] = useState(defaultDraft);
  const field = useRef<HTMLTextAreaElement>(null);
  const slashSources = useSlashSources(skills, onSkillCommand);
  const sources = useMemo(
    () => [...slashSources, ...(suggestionSources ?? [])],
    [slashSources, suggestionSources],
  );
  const suggestions = useComposerSuggestions({
    field,
    value: draft,
    onValueChange: setDraft,
    sources,
  });

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
  // A message of the agent is one to 65536 characters, counted as code points.
  const length =
    draft.length > MAX_CONTINUATION_CHARS ? characters(draft) : draft.length;
  const command = onSkillCommand ? skillCommand(draft) : null;
  const named = command ? [] : skillReferences(draft);
  const heldBy = command
    ? undefined
    : waiting
      ? t("desktop.agent.send_waiting")
      : length > MAX_CONTINUATION_CHARS
        ? t("desktop.agent.send_too_long", {
            count: length,
            max: MAX_CONTINUATION_CHARS,
          })
        : named.length > MAX_SKILLS_PER_MESSAGE
          ? t("desktop.agent.send_too_many_skills", {
              max: MAX_SKILLS_PER_MESSAGE,
            })
          : !sendable
            ? t("desktop.agent.send_nothing")
            : undefined;

  const send = () => {
    if (command && onSkillCommand) {
      onSkillCommand(command);
      setDraft("");
      return;
    }
    if (!onSend || heldBy || running) return;
    if (onSend(draft, { skills: named }) !== false) setDraft("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestions.onKeyDown(event)) return;
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

  const current = selectionWords(t, providers, models, selection);
  const settingsText = current?.words ?? t("desktop.agent.choose_model");
  // The name says which provider the words are for.
  const settingsName = t("desktop.agent.settings_label", {
    current: current
      ? described(t, current.provider.name, current.words)
      : settingsText,
  });
  const settingsLook = (
    <>
      {current && <ProviderMark provider={current.provider.id} />}
      <span className="truncate">{settingsText}</span>
      <Icon name="chevronDown" size="xs" />
    </>
  );
  const settingsButton = (
    <Button
      variant="ghost"
      size="xs"
      aria-label={settingsName}
      className="min-w-0"
    >
      {settingsLook}
    </Button>
  );

  return (
    <ComposerSuggestions state={suggestions}>
      <div className="rounded-xl bg-card text-card-foreground shadow-raised has-[textarea:focus-visible]:outline-(length:--focus-ring) has-[textarea:focus-visible]:outline-offset-(length:--focus-ring) has-[textarea:focus-visible]:outline-solid">
        <Textarea
          ref={field}
          rows={1}
          value={draft}
          aria-label={t("desktop.agent.message_label")}
          placeholder={t("desktop.agent.message_placeholder")}
          {...suggestions.fieldProps}
          onChange={(event) => setDraft(event.target.value)}
          onSelect={suggestions.onCaret}
          onClick={suggestions.onCaret}
          onKeyDown={onKeyDown}
          className="resize-none rounded-none border-0 bg-transparent px-3 pt-3 pb-1 focus-visible:outline-none"
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
              openRequests={pickerRequests}
              onClosed={onPickerClosed}
            >
              {settingsButton}
            </AgentSettingsPopover>
          ) : (
            <AgentTextAction
              variant="ghost"
              size="xs"
              className="min-w-0"
              aria-label={described(
                t,
                settingsName,
                t("desktop.agent.unavailable"),
              )}
            >
              {settingsLook}
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
    </ComposerSuggestions>
  );
}
