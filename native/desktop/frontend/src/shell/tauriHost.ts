import { Channel, invoke } from "@tauri-apps/api/core";
import type {
  ContextMenuItem,
  LogBatch,
  ManagerSignal,
  ShellToken,
  SignInSignal,
  WindowPresentation,
} from "../ipc/contract";
import type {
  AgentServiceStatus,
  AgentSession,
  AgentStreamEvent,
} from "./agentSession";
import type { AgentViews } from "./agentViews";
import type { Host } from "./host";
import type { HostCall } from "./hostCall";
import { hostCall } from "./hostCall";
import { openTauriTerminal } from "./tauriTerminal";

const TOKEN_PATTERN = /^[0-9a-f]{64}$/;
const PROFILE_HEADER = "x-cadrumo-profile";

// The host defines the token getter only on the shell's top frame, and it
// answers once. Read it here, at module load, and keep it in this closure: it
// never reaches the documentation frame, a URL, storage or a log.
function takeToken(): ShellToken | null {
  const token = window.__CADRUMO_SHELL__?.token;
  return typeof token === "string" && TOKEN_PATTERN.test(token)
    ? (token as ShellToken)
    : null;
}

/** The desktop host, reached only through the published command contract. */
export function tauriHost(): Host {
  const token = takeToken();
  const call = hostCall(token);
  // A command whose body is a password and nothing else. The token travels
  // as a header, and so does the label of the profile it names,
  // percent-encoded, since a header carries no other text.
  const submit = <Result>(
    command: "sign_in_submit" | "profile_create",
    password: Uint8Array,
    profile?: string,
  ): Promise<Result> =>
    token
      ? invoke<Result>(command, password, {
          headers: {
            "x-cadrumo-token": token,
            ...(profile === undefined
              ? {}
              : { [PROFILE_HEADER]: encodeURIComponent(profile) }),
          },
        })
      : Promise.reject(new Error("Missing desktop launch token."));

  return {
    available: true,
    nativeMenus: true,
    window: {
      action: (action) =>
        call("shell_window_action", { action }).then(() => undefined),
      async observe(listener) {
        const updates = new Channel<WindowPresentation>();
        updates.onmessage = listener;
        const subscription = await call("shell_window_subscribe", { updates });
        return () => {
          updates.onmessage = () => undefined;
          void call("shell_window_unsubscribe", { subscription }).catch(
            () => undefined,
          );
        };
      },
    },
    environment: () => call("desktop_environment", {}),
    signInStatus: () => call("sign_in_status", {}),
    managerStatus: () => call("manager_status", {}),
    async observeManager(listener) {
      const updates = new Channel<ManagerSignal>();
      updates.onmessage = listener;
      const subscription = await call("manager_subscribe", { updates });
      return () => {
        updates.onmessage = () => undefined;
        void call("manager_unsubscribe", { subscription }).catch(
          () => undefined,
        );
      };
    },
    async observeSignIn(listener) {
      const updates = new Channel<SignInSignal>();
      updates.onmessage = listener;
      const subscription = await call("sign_in_subscribe", { updates });
      return () => {
        updates.onmessage = () => undefined;
        void call("sign_in_unsubscribe", { subscription }).catch(
          () => undefined,
        );
      };
    },
    startManager: () => call("manager_start", {}),
    installManager: (scope) => call("manager_install", { scope }),
    signOut: () => call("sign_out", {}),
    signIn: (password, profile) => submit("sign_in_submit", password, profile),
    profiles: {
      list: () => call("profile_list", {}),
      create: (name, password) => submit("profile_create", password, name),
    },
    openTerminal: (kind, size, listener) =>
      token
        ? openTauriTerminal(token, call, kind, size, listener)
        : Promise.reject(
            new Error("The desktop host did not provide a launch token."),
          ),
    async subscribeLogs(listener: (batch: LogBatch) => void) {
      const records = new Channel<LogBatch>();
      records.onmessage = listener;
      const { subscription } = await call("logs_subscribe", { records });
      return () => {
        void call("logs_unsubscribe", { subscription }).catch(() => undefined);
      };
    },
    readClipboard: () =>
      call("shell_clipboard_read", {}).then(({ text }) => text),
    writeClipboard: (text) =>
      call("shell_clipboard_write", { text }).then(() => undefined),
    async showMenu(items: ContextMenuItem[], at?: { x: number; y: number }) {
      const { chosen } = await call(
        "shell_context_menu",
        at ? { items, x: at.x, y: at.y } : { items },
      );
      return chosen;
    },
    openExternal: (url) => call("open_external", { url }).then(() => undefined),
    ...tauriAgent(call),
  };
}

// The agent column served by the desktop host's agent commands: the status
// and each conversation's stream arrive on channels, everything else is one
// token-checked call. A refusal rejects with the host's `{ code }`.

/** The agent session and views of the desktop host. */
function tauriAgent(call: HostCall): {
  agentSession: AgentSession;
  agent: AgentViews;
} {
  return {
    agentSession: {
      status: () => call("agent_status", {}),
      async observeStatus(listener) {
        const updates = new Channel<AgentServiceStatus>();
        updates.onmessage = listener;
        const subscription = await call("agent_status_subscribe", { updates });
        return () => {
          updates.onmessage = () => undefined;
          void call("agent_status_unsubscribe", { subscription }).catch(
            () => undefined,
          );
        };
      },
      providerCatalog: () => call("agent_provider_catalog", {}),
      startConversation: () => call("agent_conversation_start", {}),
      send: (request) => call("agent_send", { request }),
      cancel: (replyId) =>
        call("agent_cancel", { replyId }).then(() => undefined),
      pending: (conversationId) => call("agent_pending", { conversationId }),
      answerQuestions: ({ reply_id, request_id }, answer) =>
        call("agent_questions_answer", {
          questionnaire: { reply_id, request_id },
          answer,
        }),
      decideApproval: ({ reply_id, request_id }, optionId) =>
        call("agent_approval_decide", {
          approval: { reply_id, request_id },
          optionId,
        }).then(() => undefined),
      async observe(conversationId, listener) {
        const events = new Channel<AgentStreamEvent>();
        events.onmessage = listener;
        const subscription = await call("agent_observe", {
          conversationId,
          events,
        });
        return () => {
          events.onmessage = () => undefined;
          void call("agent_unobserve", { subscription }).catch(() => undefined);
        };
      },
    },
    agent: {
      conversations: () => call("agent_conversations", {}),
      history: (conversationId) => call("agent_history", { conversationId }),
      documents: (conversationId) =>
        call("agent_documents", { conversationId }),
    },
  };
}
