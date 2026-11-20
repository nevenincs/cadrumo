// The attached-file reads of `asks=attachments`: a reply that asks to read
// three files at once on a lane whose installation keeps documents on this
// computer, so the service refuses each card, as it does where cloud upload
// is not permitted.

import type { AgentApproval } from "../shell/agentSnapshotContract";
import type { AgentSession } from "../shell/agentSession";
import { CANONICAL_OPTIONS, requested } from "./agentFixtureAsks";

const READ_NAMES = [
  "factura-enero.pdf",
  "factura-febrero.pdf",
  "factura-marzo.pdf",
];

/** The requests the reply parks on, and the call that ends it once the
 * person has answered every one. */
export function readWaits(
  replyId: string,
  requestId: (prefix: string) => string,
  done: () => void,
) {
  let left = READ_NAMES.length;
  return READ_NAMES.map((name) => ({
    kind: "approval" as const,
    approval: requested({
      request_id: requestId("p"),
      reply_id: replyId,
      source: "agent_tool",
      tool_call: "read_attachment",
      tool_kind: "other",
      tool_server: null,
      description: `Permission required: read_attachment; attachment: ${JSON.stringify(name)}`,
      options: CANONICAL_OPTIONS,
    }),
    then: () => {
      if (--left === 0) done();
    },
  }));
}

/** The service's answers about a parked read: its card names the file and the
 * lane and refuses it under `asks=attachments`; a lane that stays here needs
 * no decision. The grants it holds are none. */
export function readAnswers(
  say: (call: string) => void,
  refuses: boolean,
  waiting: ReadonlyMap<string, { kind: string; approval?: AgentApproval }>,
): Pick<
  AgentSession,
  | "attachmentCard"
  | "attachmentRelease"
  | "attachmentGrants"
  | "attachmentGrantRevoke"
> {
  return {
    attachmentCard({ request_id }) {
      say(`agentAttachmentCard ${request_id}`);
      const named = /attachment: (".*")/.exec(
        waiting.get(request_id)?.approval?.description ?? "",
      )?.[1];
      return Promise.resolve(
        refuses
          ? {
              kind: "refused" as const,
              code: "cloud_upload_not_permitted" as const,
              name: named ? (JSON.parse(named) as string) : null,
              provider: "codex",
            }
          : { kind: "not_required" as const },
      );
    },
    attachmentRelease({ request_id }, _optionId, scope) {
      say(`agentAttachmentRelease ${request_id} ${scope ?? "grant"}`);
      return Promise.resolve({ kind: "not_required" as const });
    },
    attachmentGrants: () =>
      Promise.resolve({ kind: "grants" as const, grants: [] }),
    attachmentGrantRevoke: () =>
      Promise.resolve({
        kind: "refused" as const,
        code: "grant_revoked" as const,
        name: null,
        provider: null,
      }),
  };
}
