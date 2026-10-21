// cadrumo-agent's skills as the composer offers them: the agent's own
// inventory, never a provider's command set. A skill is named in a message by
// a `/name` token; the send carries the names as a structured list, which is
// what makes the run load them.

/** A bundled skill's name: `cadrumo-` and a lowercase, hyphenated rest. */
export const SKILL_NAME = /^cadrumo-[a-z0-9][a-z0-9-]{0,118}$/;

/** The most skills one message may load. */
export const MAX_SKILLS_PER_MESSAGE = 8;

/** When the agent applies a skill on its own, as its frontmatter says. Keys
 * the agent adds later are kept and not shown. */
export type AgentSkillAppliesWhen = {
  always?: boolean;
  profile_facts?: { fact: string; match: string; values: unknown[] }[];
  profile_match?: "all" | "any";
  workflow_phase?: string;
  temporal_trigger?: string;
  [key: string]: unknown;
};

export type AgentSkillFile = { path: string; bytes: number; digest: string };

/** One skill of the inventory, as `GET /v1/skills` lists it. */
export type AgentSkillSummary = {
  name: string;
  description: string;
  applies_when: AgentSkillAppliesWhen;
  /** SHA-256 of the skill, lowercase hex. */
  digest: string;
  /** Every file of the skill, SKILL.md included, by path in its folder. */
  files: AgentSkillFile[];
};

export type AgentSkillInventory = {
  revision: string;
  skills: AgentSkillSummary[];
};

/** One skill in full: its summary and its SKILL.md, frontmatter included. */
export type AgentSkillDetail = AgentSkillSummary & { content: string };

export type AgentSkillFinding = {
  severity: "error" | "warning";
  code: string;
  message: string;
  path: string | null;
};

/** The agent's checks of one skill. It is valid when no finding is an
 * error. */
export type AgentSkillVerification = {
  name: string;
  digest: string;
  valid: boolean;
  findings: AgentSkillFinding[];
};

/** What the composer does on its own rather than send. */
export type SkillCommandKind = "review" | "verify";
export type SkillCommand = { kind: SkillCommandKind; name: string };

/** The composer's own commands, by the word typed after `/`. */
export const SKILL_COMMANDS: Readonly<Record<SkillCommandKind, string>> = {
  review: "skill-review",
  verify: "skill-verify",
};

const commandOf = (word: string): SkillCommandKind | undefined =>
  (Object.keys(SKILL_COMMANDS) as SkillCommandKind[]).find(
    (kind) => SKILL_COMMANDS[kind] === word,
  );

/** The skills a message names, once each, in the order it names them: every
 * `/name` token of a skill's grammar standing on its own. */
export function skillReferences(text: string): string[] {
  const named: string[] = [];
  for (const token of text.matchAll(/(?:^|\s)\/(\S+)/g)) {
    const name = token[1] ?? "";
    if (SKILL_NAME.test(name) && !named.includes(name)) named.push(name);
  }
  return named;
}

/** The command a whole message is, if it is one: a command word and the
 * skill it is for, and nothing else. */
export function skillCommand(text: string): SkillCommand | null {
  const parts = /^\/(\S+)\s+(\S+)$/.exec(text.trim());
  if (!parts) return null;
  const kind = commandOf(parts[1] ?? "");
  const name = parts[2] ?? "";
  return kind && SKILL_NAME.test(name) ? { kind, name } : null;
}

/** A command typed up to its skill: the command, where its token begins, and
 * what is typed of the skill so far. */
export function partialSkillCommand(
  before: string,
): { kind: SkillCommandKind; start: number; query: string } | null {
  const parts = /(^|\s)\/(\S+)\s+(\S*)$/.exec(before);
  if (!parts) return null;
  const kind = commandOf(parts[2] ?? "");
  if (!kind) return null;
  return {
    kind,
    start: parts.index + (parts[1] ?? "").length,
    query: parts[3] ?? "",
  };
}

/** Keeps the skills whose name or description holds what was typed; a skill
 * whose name begins with it comes first. */
export function matchingSkills(
  skills: readonly AgentSkillSummary[],
  query: string,
): AgentSkillSummary[] {
  const typed = query.trim().toLocaleLowerCase();
  if (!typed) return [...skills];
  const leading: AgentSkillSummary[] = [];
  const within: AgentSkillSummary[] = [];
  for (const skill of skills) {
    const name = skill.name.toLocaleLowerCase();
    const bare = name.replace(/^cadrumo-/, "");
    if (name.startsWith(typed) || bare.startsWith(typed)) leading.push(skill);
    else if (
      name.includes(typed) ||
      skill.description.toLocaleLowerCase().includes(typed)
    )
      within.push(skill);
  }
  return [...leading, ...within];
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const DIGEST = /^[0-9a-f]{64}$/;

function readFile(value: unknown): AgentSkillFile | null {
  if (!isRecord(value)) return null;
  const { path, bytes, digest } = value;
  if (typeof path !== "string" || path === "") return null;
  if (typeof bytes !== "number" || !Number.isSafeInteger(bytes) || bytes < 0)
    return null;
  if (typeof digest !== "string" || !DIGEST.test(digest)) return null;
  return { path, bytes, digest };
}

function readSummary(value: unknown): AgentSkillSummary | null {
  if (!isRecord(value)) return null;
  const { name, description, applies_when, digest, files } = value;
  if (typeof name !== "string" || !SKILL_NAME.test(name)) return null;
  if (typeof description !== "string") return null;
  if (!isRecord(applies_when)) return null;
  if (typeof digest !== "string" || !DIGEST.test(digest)) return null;
  const read = Array.isArray(files) ? files.map(readFile) : [];
  if (read.some((file) => file === null)) return null;
  return {
    name,
    description,
    applies_when: applies_when as AgentSkillAppliesWhen,
    digest,
    files: read as AgentSkillFile[],
  };
}

/** The inventory, or null when the agent answered something else. A skill
 * it cannot read makes the whole answer unreadable: none is silently left
 * out. */
export function readSkillInventory(value: unknown): AgentSkillInventory | null {
  if (!isRecord(value) || !Array.isArray(value.skills)) return null;
  const skills = value.skills.map(readSummary);
  if (skills.some((skill) => skill === null)) return null;
  return {
    revision: typeof value.revision === "string" ? value.revision : "",
    skills: skills as AgentSkillSummary[],
  };
}

export function readSkillDetail(value: unknown): AgentSkillDetail | null {
  const summary = readSummary(value);
  if (!summary || !isRecord(value) || typeof value.content !== "string")
    return null;
  return { ...summary, content: value.content };
}

function readFinding(value: unknown): AgentSkillFinding | null {
  if (!isRecord(value)) return null;
  const { severity, code, message, path } = value;
  if (severity !== "error" && severity !== "warning") return null;
  if (typeof code !== "string" || typeof message !== "string") return null;
  return {
    severity,
    code,
    message,
    path: typeof path === "string" ? path : null,
  };
}

export function readSkillVerification(
  value: unknown,
): AgentSkillVerification | null {
  if (!isRecord(value)) return null;
  const { name, digest, valid, findings } = value;
  if (typeof name !== "string" || typeof valid !== "boolean") return null;
  if (!Array.isArray(findings)) return null;
  const read = findings.map(readFinding);
  if (read.some((finding) => finding === null)) return null;
  return {
    name,
    digest: typeof digest === "string" ? digest : "",
    valid,
    findings: read as AgentSkillFinding[],
  };
}
