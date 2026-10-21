import { useLayoutEffect, useMemo, useRef } from "react";
import type { AgentSession } from "../../shell/agentSession";
import {
  SKILL_COMMANDS,
  matchingSkills,
  partialSkillCommand,
  type AgentSkillSummary,
  type SkillCommand,
  type SkillCommandKind,
} from "../../shell/agentSkills";
import { useStrings } from "../../shell/strings";
import { charTrigger } from "./composerTrigger";
import type { AnySource, SuggestionSource } from "./ComposerSuggestions";

/** What the `/` list offers: one of the composer's commands, or a skill. */
type SlashItem =
  | { kind: "command"; command: SkillCommandKind }
  | { kind: "skill"; skill: AgentSkillSummary };

const COMMAND_KINDS = Object.keys(SKILL_COMMANDS) as SkillCommandKind[];

/** Reads the skills once for a session, and again after a failed read. */
export function useSkillInventory(
  session: Pick<AgentSession, "skills"> | null | undefined,
): (() => Promise<readonly AgentSkillSummary[]>) | undefined {
  const held = useRef<{
    session: unknown;
    read: Promise<readonly AgentSkillSummary[]>;
  } | null>(null);
  return useMemo(() => {
    const skills = session?.skills?.bind(session);
    if (!skills) return undefined;
    return () => {
      const kept = held.current;
      if (kept && kept.session === session) return kept.read;
      const read = skills().then((inventory) => inventory.skills);
      held.current = { session, read };
      read.catch(() => {
        if (held.current?.read === read) held.current = null;
      });
      return read;
    };
  }, [session]);
}

function SkillWords({
  name,
  description,
}: {
  name: string;
  description: string;
}) {
  return (
    <span className="grid min-w-0 flex-1">
      <span className="truncate font-mono text-sm font-medium">/{name}</span>
      {description && (
        <span className="truncate text-sm text-muted-foreground in-data-[selected=true]:text-accent-foreground">
          {description}
        </span>
      )}
    </span>
  );
}

/**
 * The composer's `/` suggestions: its own commands and cadrumo-agent's
 * skills. A skill chosen is written as its `/name` token, which the send
 * carries as the skill to load; a command chosen asks next for the skill it
 * is for, and choosing that skill runs the command at once and takes its
 * words out of the message.
 */
export function useSlashSources(
  skills: (() => Promise<readonly AgentSkillSummary[]>) | undefined,
  onSkillCommand: ((command: SkillCommand) => void) | undefined,
): readonly AnySource[] {
  const t = useStrings();
  // The latest handler, so the sources stay the same while it changes.
  const run = useRef(onSkillCommand);
  useLayoutEffect(() => {
    run.current = onSkillCommand;
  });
  const commands = onSkillCommand !== undefined;
  return useMemo(() => {
    if (!skills) return [];
    const common = {
      empty: t("desktop.agent.slash_empty"),
      loading: t("desktop.agent.slash_loading"),
      failed: t("desktop.agent.slash_failed"),
    };
    const commandWords: Record<SkillCommandKind, string> = {
      review: t("desktop.agent.skill_command_review"),
      verify: t("desktop.agent.skill_command_verify"),
    };
    const slash: SuggestionSource<SlashItem> = {
      ...common,
      id: "slash",
      label: t("desktop.agent.slash_label"),
      match: charTrigger("/"),
      items: async (query) => {
        const typed = query.toLocaleLowerCase();
        const offered: SlashItem[] = commands
          ? COMMAND_KINDS.filter((kind) =>
              SKILL_COMMANDS[kind].includes(typed),
            ).map((command) => ({ kind: "command", command }))
          : [];
        return [
          ...offered,
          ...matchingSkills(await skills(), query).map((skill): SlashItem => ({
            kind: "skill",
            skill,
          })),
        ];
      },
      key: (item) =>
        item.kind === "command"
          ? `command:${item.command}`
          : `skill:${item.skill.name}`,
      section: (item) =>
        item.kind === "command"
          ? t("desktop.agent.slash_commands")
          : t("desktop.agent.slash_skills"),
      render: (item) =>
        item.kind === "command" ? (
          <SkillWords
            name={SKILL_COMMANDS[item.command]}
            description={commandWords[item.command]}
          />
        ) : (
          <SkillWords
            name={item.skill.name}
            description={item.skill.description}
          />
        ),
      accept: (item) =>
        item.kind === "command"
          ? `/${SKILL_COMMANDS[item.command]} `
          : `/${item.skill.name} `,
    };
    const commandArguments = COMMAND_KINDS.map(
      (kind): SuggestionSource<AgentSkillSummary> => ({
        ...common,
        id: `skill-${kind}`,
        label: commandWords[kind],
        match: (before) => {
          const partial = partialSkillCommand(before);
          return partial?.kind === kind
            ? { start: partial.start, query: partial.query }
            : null;
        },
        items: async (query) => matchingSkills(await skills(), query),
        key: (skill) => skill.name,
        render: (skill) => (
          <SkillWords name={skill.name} description={skill.description} />
        ),
        accept: (skill) => {
          run.current?.({ kind, name: skill.name });
          return "";
        },
      }),
    );
    // A command typed up to its skill is answered before a bare `/` token.
    const sources: AnySource[] = [...(commands ? commandArguments : []), slash];
    return sources;
  }, [skills, commands, t]);
}
