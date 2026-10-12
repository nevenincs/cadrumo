import { useEffect, useMemo, useState } from "react";
import type {
  AgentReplyState,
  ConversationDocument,
  ConversationGroup,
  DocumentRole,
  DocumentStatus,
  FileKind,
  ToolActivityState,
  TranscriptItem,
} from "@/components/agent/types";
import { failureCode } from "../errors";

// What a host serves the agent column, as the host answers it. A desktop
// host serves these through its closed set of agent commands: the
// conversation list from the agent's gateway, the documents from Cadrumo's
// own custody. A host that cannot serves none of them, and the column shows
// each view as not available yet: never as empty, and never made up.

/** One conversation, as the agent's gateway lists it. */
export type AgentConversationRecord = {
  id: string;
  title: string;
  /** When it was last active, as an ISO instant. */
  last_active_at: string;
  document_count: number;
  archived: boolean;
};

/** One document of a conversation, as Cadrumo's custody lists it. */
export type AgentDocumentRecord = {
  id: string;
  name: string;
  media_type: string;
  size_bytes: number;
  role: DocumentRole;
  status: DocumentStatus;
  /** The files inside an archive, each held on its own. */
  members?: AgentDocumentRecord[];
};

/** A file sent with a message, as the conversation's history names it. */
export type AgentSentFileRecord = {
  id: string;
  name: string;
  media_type: string;
};

/** One turn of a conversation, in order, as the agent's gateway keeps it. */
export type AgentTurnRecord =
  | {
      kind: "person";
      id: string;
      text: string;
      /** When it was sent, as an ISO instant. */
      sent_at: string;
      files?: AgentSentFileRecord[];
    }
  | {
      kind: "agent";
      id: string;
      text: string;
      state: AgentReplyState;
      failure_reason?: string;
    }
  | {
      kind: "tool";
      id: string;
      /** What the Cadrumo operation called does, in the output language. */
      label: string;
      state: ToolActivityState;
      detail?: string;
    };

/** The agent views a host offers. Each read is refused while nobody is
 * signed in, as the profile's own views are. */
export interface AgentViews {
  /** Every conversation of the signed-in profile, archived ones included. */
  conversations(): Promise<AgentConversationRecord[]>;
  /** The turns of one conversation, oldest first. */
  history(conversationId: string): Promise<AgentTurnRecord[]>;
  /** The documents of one conversation. */
  documents(conversationId: string): Promise<AgentDocumentRecord[]>;
}

/** A read the column makes: not offered by the host, on its way, refused,
 * or answered. Not offered is its own state, never shown as empty. */
export type AgentRead<T> =
  | { kind: "unavailable" }
  | { kind: "loading" }
  | { kind: "failed"; code: string }
  | { kind: "ready"; value: T };

/**
 * Reads what `read` asks for whenever it changes, and drops the answer to a
 * question no longer asked. Null means the host does not offer the read, or
 * nobody it would belong to is signed in.
 */
export function useAgentRead<T>(read: (() => Promise<T>) | null): AgentRead<T> {
  const [state, setState] = useState<{
    for: (() => Promise<T>) | null;
    read: AgentRead<T>;
  }>({ for: null, read: { kind: "unavailable" } });
  useEffect(() => {
    if (!read) return;
    let current = true;
    read().then(
      (value) => {
        if (current) setState({ for: read, read: { kind: "ready", value } });
      },
      (error: unknown) => {
        if (current)
          setState({
            for: read,
            read: { kind: "failed", code: failureCode(error) },
          });
      },
    );
    return () => {
      current = false;
    };
  }, [read]);
  if (!read) return { kind: "unavailable" };
  // An answer belongs to the read that asked for it: a new read is loading
  // until it has its own.
  return state.for === read ? state.read : { kind: "loading" };
}

const IMAGE = /^image\//;
const SHEET =
  /spreadsheet|ms-excel|^text\/csv$|opendocument\.spreadsheet|^text\/tab-separated-values$/;
const ARCHIVE = /^application\/(zip|x-zip-compressed)$/;
const TEXT = /^text\//;

/** What a file is drawn as, from its media type. */
export function fileKind(mediaType: string): FileKind {
  if (IMAGE.test(mediaType)) return "image";
  if (SHEET.test(mediaType)) return "sheet";
  if (ARCHIVE.test(mediaType)) return "archive";
  if (TEXT.test(mediaType)) return "text";
  return "document";
}

const extensionOf = (name: string) => {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1) : "";
};

/** A document record as the documents panel shows it. */
export function conversationDocument(
  record: AgentDocumentRecord,
): ConversationDocument {
  return {
    id: record.id,
    name: record.name,
    extension: extensionOf(record.name),
    sizeBytes: record.size_bytes,
    role: record.role,
    status: record.status,
    kind: fileKind(record.media_type),
    ...(record.members
      ? { members: record.members.map(conversationDocument) }
      : {}),
  };
}

/** When a message was sent, in words: the time today, else the day too. */
function sentLabel(locale: string, at: Date, now: Date): string | undefined {
  if (!Number.isFinite(at.getTime())) return undefined;
  const sameDay = dayStart(at) === dayStart(now);
  return new Intl.DateTimeFormat(locale, {
    ...(sameDay ? {} : { day: "numeric", month: "short" }),
    hour: "numeric",
    minute: "2-digit",
  }).format(at);
}

/** A conversation's turns as the transcript lists them. */
export function transcriptItems(
  records: readonly AgentTurnRecord[],
  locale: string,
  now: Date = new Date(),
): TranscriptItem[] {
  return records.map((record): TranscriptItem => {
    if (record.kind === "person") {
      const sentAtLabel = sentLabel(locale, new Date(record.sent_at), now);
      return {
        kind: "person",
        id: record.id,
        text: record.text,
        ...(sentAtLabel ? { sentAtLabel } : {}),
        ...(record.files?.length
          ? {
              files: record.files.map((file) => ({
                id: file.id,
                name: file.name,
                extension: extensionOf(file.name),
                kind: fileKind(file.media_type),
              })),
            }
          : {}),
      };
    }
    if (record.kind === "agent")
      return {
        kind: "agent",
        id: record.id,
        text: record.text,
        state: record.state,
        ...(record.failure_reason
          ? { failureReason: record.failure_reason }
          : {}),
      };
    return {
      kind: "tool",
      id: record.id,
      label: record.label,
      state: record.state,
      ...(record.detail ? { detail: record.detail } : {}),
    };
  });
}

const capitalized = (text: string, locale: string) =>
  text.charAt(0).toLocaleUpperCase(locale) + text.slice(1);

/** How long ago an instant was, in the largest whole unit, in words. */
function agoLabel(locale: string, at: Date, now: Date): string {
  const words = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const seconds = Math.round((at.getTime() - now.getTime()) / 1000);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 365 * 86_400],
    ["month", 30 * 86_400],
    ["week", 7 * 86_400],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units)
    if (Math.abs(seconds) >= size)
      return words.format(Math.round(seconds / size), unit);
  return words.format(0, "minute");
}

/** The calendar day of an instant, where the person is. */
const dayStart = (at: Date) =>
  new Date(at.getFullYear(), at.getMonth(), at.getDate()).getTime();

/**
 * The conversations the history shows, newest first, under the headings the
 * person reads them by: today, yesterday, then each earlier month. The
 * words come from the locale itself, so no heading is a translation.
 */
export function conversationGroups(
  records: readonly AgentConversationRecord[],
  {
    locale,
    archived,
    currentId,
    now = new Date(),
  }: {
    locale: string;
    archived: boolean;
    currentId: string | null;
    now?: Date;
  },
): ConversationGroup[] {
  const days = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const months = new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
  });
  const today = dayStart(now);
  const groups: {
    heading: string;
    conversations: ConversationGroup["conversations"][number][];
  }[] = [];
  const shown = records
    .filter((record) => record.archived === archived)
    .map((record) => ({ record, at: new Date(record.last_active_at) }))
    .filter(({ at }) => Number.isFinite(at.getTime()))
    .sort((a, b) => b.at.getTime() - a.at.getTime());
  for (const { record, at } of shown) {
    const behind = Math.round((today - dayStart(at)) / 86_400_000);
    const heading = capitalized(
      behind <= 1
        ? days.format(-Math.max(0, behind), "day")
        : months.format(at),
      locale,
    );
    let group = groups.at(-1);
    if (group?.heading !== heading) {
      group = { heading, conversations: [] };
      groups.push(group);
    }
    group.conversations.push({
      id: record.id,
      title: record.title,
      lastActivityLabel: agoLabel(locale, at, now),
      documentCount: record.document_count,
      archived: record.archived,
      current: record.id === currentId,
    });
  }
  return groups;
}

/** The archived conversations, counted for the history's toggle. */
export const archivedCount = (records: readonly AgentConversationRecord[]) =>
  records.filter((record) => record.archived).length;

/** The memoized groups of a read, or null until it has an answer. */
export function useConversationGroups(
  read: AgentRead<AgentConversationRecord[]>,
  options: { locale: string; archived: boolean; currentId: string | null },
): ConversationGroup[] | null {
  const { locale, archived, currentId } = options;
  return useMemo(
    () =>
      read.kind === "ready"
        ? conversationGroups(read.value, { locale, archived, currentId })
        : null,
    [read, locale, archived, currentId],
  );
}
