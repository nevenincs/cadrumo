import { Channel, invoke } from "@tauri-apps/api/core";
import type {
  DesktopSetup,
  LogBatch,
  ManagerSignal,
  ShellToken,
  SignInSignal,
  WindowPresentation,
} from "../ipc/contract";
import type { AgentAccess } from "./agentAccess";
import type {
  AgentServiceStatus,
  AgentSession,
  AgentStreamEvent,
  AgentUploadEvent,
  AgentDropSignal,
} from "./agentSession";
import {
  readSkillDetail,
  readSkillInventory,
  readSkillVerification,
} from "./agentSkills";
import type { AgentViews } from "./agentViews";
import type { Host } from "./host";
import type { HostCall } from "./hostCall";
import { hostCall } from "./hostCall";
import type {
  ProviderSignInSnapshot,
  ProviderSettings,
  ProviderSettingsAnswer,
  ProviderSettingsRecord,
} from "./providerSettings";
import { tauriLedger } from "./tauriLedger";
import { tauriModelo } from "./tauriModelo";
import { tauriSedeView } from "./tauriSedeView";
import { openTauriTerminal } from "./tauriTerminal";

const TOKEN_PATTERN = /^[0-9a-f]{64}$/;
const PROFILE_HEADER = "x-cadrumo-profile";
const TOKEN_HEADER = "x-cadrumo-token";

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
  const openExternal = (url: string) =>
    call("open_external", { url }).then(() => undefined);
  // A command whose body is a password, or one JSON object holding it, and
  // nothing else. The token travels as a header, and so does the label of
  // the profile it names, percent-encoded, since a header carries no other
  // text.
  const submit = <Result>(
    command:
      | "sign_in_submit"
      | "profile_create"
      | "profile_password_change"
      | "profile_aeat_credential_save",
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
    censo: {
      async observe(changed) {
        let active = true;
        const updates = new Channel<null>();
        updates.onmessage = () => {
          if (active) changed();
        };
        const subscription = await call("profile_censo_observe", { updates });
        return () => {
          active = false;
          void call("profile_censo_unobserve", { subscription }).catch(
            () => undefined,
          );
        };
      },
      readiness: (profile) => call("profile_censo_readiness", { profile }),
      start: (profile) => call("profile_censo_start", { profile }),
      status: (profile, operation) =>
        call("profile_censo_status", { profile, operation }),
      answer: (profile, operation, reviewDigest, decision) =>
        call("profile_censo_answer", {
          profile,
          operation,
          reviewDigest,
          decision,
        }),
    },
    userProfile: {
      read: (language) => call("user_profile_read", { language }),
      change: (change) =>
        call("user_profile_change", { change }).then(() => undefined),
      async observe(changed) {
        let active = true;
        const updates = new Channel<null>();
        updates.onmessage = () => {
          if (active) changed();
        };
        const subscription = await call("user_profile_observe", { updates });
        return () => {
          active = false;
          void call("user_profile_unobserve", { subscription }).catch(
            () => undefined,
          );
        };
      },
      aeat: {
        pickCertificate: () => call("profile_aeat_certificate_pick", {}),
        async saveCredential(credential) {
          const body = new TextEncoder().encode(JSON.stringify(credential));
          try {
            await submit("profile_aeat_credential_save", body);
          } finally {
            body.fill(0);
          }
        },
      },
    },
    views: {
      notifications: () => call("profile_views_notifications", {}),
      filingCalendar: (range, language) =>
        call("profile_views_calendar", {
          from: range.from,
          to: range.to,
          language,
        }),
    },
    ledger: tauriLedger(token, call),
    modelo: tauriModelo(token, call),
    sedeView: tauriSedeView(call),
    attendance: {
      async inventory() {
        const reply = (await call("runtime_attendance_inventory", {})) as {
          kind: string;
          candidates?: unknown;
        };
        if (
          reply.kind !== "attendance_inventory" ||
          !Array.isArray(reply.candidates) ||
          reply.candidates.length > 8
        )
          throw new Error("Attendance unavailable");
        return {
          candidates:
            reply.candidates as import("./host").AttendanceCandidate[],
        };
      },
      async decide(attendanceId, approve) {
        const reply = (await call("runtime_attendance_decide", {
          attendanceId,
          approve,
        })) as { kind: string; attendance_id: string; approved: boolean };
        if (
          reply.kind !== "attendance_decided" ||
          reply.attendance_id !== attendanceId ||
          reply.approved !== approve
        )
          throw new Error("Attendance decision unavailable");
      },
      async observe(changed) {
        const updates = new Channel<null>();
        updates.onmessage = () => changed();
        const subscription = await call("runtime_attendance_subscribe", {
          updates,
        });
        return () => {
          updates.onmessage = () => undefined;
          void call("runtime_attendance_unsubscribe", { subscription }).catch(
            () => undefined,
          );
        };
      },
    },
    available: true,
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
      async guardClose(asked) {
        const requests = new Channel<null>();
        requests.onmessage = () => asked();
        const subscription = await call("shell_close_guard_subscribe", {
          requests,
        });
        return () => {
          requests.onmessage = () => undefined;
          void call("shell_close_guard_unsubscribe", { subscription }).catch(
            () => undefined,
          );
        };
      },
    },
    presentation: {
      present: (view, params) => call("desktop_present_view", { view, params }),
    },
    environment: () => call("desktop_environment", {}),
    about: () => call("about_info", {}),
    language: {
      read: () => call("desktop_language_read", {}),
      set: (language) => call("desktop_language_set", { language }),
      async observe(listener) {
        const updates = new Channel<
          import("../ipc/contract").DesktopLanguage
        >();
        updates.onmessage = listener;
        const subscription = await call("desktop_language_observe", {
          updates,
        });
        return () => {
          updates.onmessage = () => undefined;
          void call("desktop_language_unobserve", { subscription }).catch(
            () => undefined,
          );
        };
      },
    },
    setup: {
      read: () => call("desktop_setup_read", {}),
      check: (mode) => call("desktop_setup_check", { mode }),
      verify: (items) => call("desktop_setup_verify", { items }),
      start: (item, options = {}) =>
        call("desktop_setup_start", {
          item,
          resume: options.resume ?? false,
          ...(options.download ? { download: options.download } : {}),
        }),
      answer: (operationId, planDigest, decision) =>
        call("desktop_setup_answer", { operationId, planDigest, decision }),
      cancel: (operationId) => call("desktop_setup_cancel", { operationId }),
      removeModel: (model) => call("desktop_setup_remove_model", { model }),
      remove: (removal) => call("desktop_setup_remove", { removal }),
      signInGoogle: () => call("desktop_google_sign_in", {}),
      signOutGoogle: () => call("desktop_google_sign_out", {}),
      async observe(listener) {
        const updates = new Channel<DesktopSetup>();
        updates.onmessage = listener;
        const subscription = await call("desktop_setup_observe", { updates });
        return () => {
          updates.onmessage = () => undefined;
          void call("desktop_setup_unobserve", { subscription }).catch(
            () => undefined,
          );
        };
      },
    },
    signInStatus: () => call("sign_in_status", {}),
    noteActivity: () => call("sign_in_activity", {}),
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
      reviewDelete: (name) => call("profile_delete_review", { name }),
      delete: (review, confirmation, acknowledged) =>
        call("profile_delete", { review, confirmation, acknowledged }).then(
          () => undefined,
        ),
      changePassword: (passwords) =>
        submit("profile_password_change", passwords),
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
    exportLogs: (text) => call("logs_export", { text }),
    copyLogs: (text) => call("logs_copy", { text }).then(() => undefined),
    revealLogs: () => call("logs_reveal", {}).then(() => undefined),
    openExternal,
    providerSettings: tauriProviderSettings(token, openExternal),
    agentAccess: tauriAgentAccess(call),
    ...tauriAgent(call),
  };
}

// The signed-in profile's model providers, served by the host's provider
// settings commands. A key travels once, as the raw body of the call that
// saves it, in a buffer this overwrites as soon as the call settles; the
// provider, the revision it was read at and the gateway address travel as
// headers, so that the body is the key and nothing else. Nothing here keeps a
// key or reads one back. A refusal rejects with the host's `{ code }`.

const PROVIDER_HEADER = "x-cadrumo-provider";
const REVISION_HEADER = "x-cadrumo-revision";
const BASE_URL_HEADER = "x-cadrumo-base-url";
const CLEAR_BASE_URL_HEADER = "x-cadrumo-clear-base-url";
/** What a header can carry as text, and the host will read as one word. */
const HEADER_TEXT = /^[\x21-\x7e]+$/;

/** A refusal the window words from its code, as the host would send it. */
function refusal(code: string): Error & { code: string } {
  return Object.assign(new Error(code), { code });
}

function tauriProviderSettings(
  token: ShellToken | null,
  openExternal: (url: string) => Promise<void>,
): ProviderSettings {
  const unavailable = () =>
    Promise.reject(new Error("Missing desktop launch token."));
  const command = <Result>(
    name: string,
    args: Record<string, string>,
  ): Promise<Result> =>
    token ? invoke<Result>(name, { ...args, token }) : unavailable();
  return {
    status: () =>
      command<ProviderSettingsAnswer>("provider_settings_status", {}),
    async set({ provider, revision, secret, base_url }) {
      if (!token) return unavailable();
      // An empty address is the catalogue's default; absent keeps the stored one.
      if (
        base_url !== undefined &&
        base_url !== "" &&
        !HEADER_TEXT.test(base_url)
      )
        throw refusal("base_url_rejected");
      const key = new TextEncoder().encode(secret);
      try {
        return await invoke<ProviderSettingsRecord>(
          "provider_settings_set",
          key,
          {
            headers: {
              [TOKEN_HEADER]: token,
              [PROVIDER_HEADER]: provider,
              [REVISION_HEADER]: revision,
              ...(base_url === undefined
                ? {}
                : base_url === ""
                  ? { [CLEAR_BASE_URL_HEADER]: "1" }
                  : { [BASE_URL_HEADER]: base_url }),
            },
          },
        );
      } finally {
        key.fill(0);
      }
    },
    turnOff: ({ provider, revision }) =>
      command<ProviderSettingsRecord>("provider_settings_remove", {
        provider,
        revision,
      }),
    turnOn: ({ provider, revision }) =>
      command<ProviderSettingsRecord>("provider_settings_turn_on", {
        provider,
        revision,
      }),
    reset: ({ provider, revision }) =>
      command<ProviderSettingsRecord>("provider_settings_reset", {
        provider,
        revision,
      }),
    signIn: {
      start: ({ provider, revision, method }) =>
        command<ProviderSignInSnapshot>("provider_sign_in_start", {
          provider,
          revision,
          method,
        }),
      status: ({ attemptId }) =>
        command<ProviderSignInSnapshot>("provider_sign_in_status", {
          attemptId,
        }),
      cancel: ({ attemptId }) =>
        command<ProviderSignInSnapshot>("provider_sign_in_cancel", {
          attemptId,
        }),
      async submitCode({ attemptId, code }) {
        if (!token) return unavailable();
        const bytes = new TextEncoder().encode(code);
        try {
          return await invoke<ProviderSignInSnapshot>(
            "provider_sign_in_submit_code",
            bytes,
            {
              headers: {
                [TOKEN_HEADER]: token,
                "x-cadrumo-attempt-id": attemptId,
              },
            },
          );
        } finally {
          bytes.fill(0);
        }
      },
      openExternal,
    },
  };
}

// The keys the signed-in profile has issued to agents outside Cadrumo, served
// by the host's agent access commands. No call carries a password or a key:
// each is one token-checked call, and a refusal rejects with the host's
// `{ code }`. The host refuses to issue a key (`issue_unavailable`) until the
// product offers issuing as one act of the person's.

function tauriAgentAccess(call: HostCall): AgentAccess {
  return {
    list: () => call("agent_access_list", {}),
    issue: ({ tax_values }) =>
      call("agent_access_issue", { taxValues: tax_values }),
    revoke: ({ grant_id }) =>
      call("agent_access_revoke", { grantId: grant_id }),
  };
}

// The agent column served by the desktop host's agent commands: the status
// and each conversation's stream arrive on channels, everything else is one
// token-checked call. A refusal rejects with the host's `{ code }`.

/** An answer of the agent read into its shape, else refused as one the host
 * could not read. */
function readable<T>(read: T | null): T {
  if (read === null)
    throw Object.assign(new Error("The agent's answer was unreadable."), {
      code: "agent_gateway_unreadable",
    });
  return read;
}

/** The agent session and views of the desktop host. */
function tauriAgent(call: HostCall): {
  agentSession: AgentSession;
  agent: AgentViews;
} {
  return {
    agentSession: {
      status: () => call("agent_status", {}),
      retry: () => call("agent_retry", {}).then(() => undefined),
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
      localModels: () => call("agent_local_models", {}),
      addLocalModel: (lane, model, expectedRevision) =>
        call("agent_local_model_add", { lane, model, expectedRevision }),
      removeLocalModel: (lane, model, expectedRevision) =>
        call("agent_local_model_remove", { lane, model, expectedRevision }),
      resetLocalModels: (expectedRevision) =>
        call("agent_local_models_reset", { expectedRevision }),
      chooseReadingModel: (lane, model, expectedRevision) =>
        call("agent_reading_model_choose", { lane, model, expectedRevision }),
      modelLicence: (provider, transport, model) =>
        call("agent_model_licence", { provider, transport, model }),
      skills: () =>
        call("agent_skills", {}).then((answer) =>
          readable(readSkillInventory(answer)),
        ),
      skill: (name) =>
        call("agent_skill", { name }).then((answer) =>
          readable(readSkillDetail(answer)),
        ),
      verifySkill: (name) =>
        call("agent_skill_verify", { name }).then((answer) =>
          readable(readSkillVerification(answer)),
        ),
      startConversation: () => call("agent_conversation_start", {}),
      archive: (conversationId) =>
        call("agent_conversation_archive", { conversationId }).then(
          () => undefined,
        ),
      delete: (conversationId) =>
        call("agent_conversation_delete", { conversationId }).then(
          () => undefined,
        ),
      rename: (conversationId, title) =>
        call("agent_conversation_rename", { conversationId, title }).then(
          () => undefined,
        ),
      send: (request) => call("agent_send", { request }),
      attach: (conversationId, filterLabel, onEvent, dropId) => {
        const updates = new Channel<AgentUploadEvent>();
        updates.onmessage = onEvent;
        return call("agent_attach", {
          conversationId,
          filterLabel,
          updates,
          ...(dropId ? { dropId } : {}),
        });
      },
      async observeDrops(listener) {
        let active = true;
        const updates = new Channel<AgentDropSignal>();
        updates.onmessage = (signal) => {
          if (active) listener(signal);
        };
        const subscription = await call("agent_drop_observe", { updates });
        return () => {
          active = false;
          void call("agent_drop_unobserve", { subscription }).catch(
            () => undefined,
          );
        };
      },
      removeDocuments: (conversationId, name) =>
        call("agent_documents_remove", {
          conversationId,
          ...(name === undefined ? {} : { name }),
        }).then(() => undefined),
      attachmentPolicy: () => call("agent_attachment_policy", {}),
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
      snapshot: (conversationId) => call("agent_snapshot", { conversationId }),
      documents: (query) => call("agent_documents", { query }),
    },
  };
}
