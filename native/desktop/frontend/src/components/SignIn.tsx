import { useRef } from "react";
import type { SignInRefusal } from "../ipc/contract";
import type { SignInController } from "../shell/signIn";
import { useStrings } from "../shell/strings";

const refusalKeys: Record<string, string> = {
  CREDENTIAL_REJECTED: "desktop.signin.refused.invalid",
  PROFILE_LOCKED: "desktop.signin.refused.profile_locked",
  RECEIPT_ABSENT: "desktop.signin.refused.receipt_absent",
  RECEIPT_EXPIRED: "desktop.signin.refused.receipt_expired",
  CUSTODY_CHANGED: "desktop.signin.refused.custody_changed",
  KEYRING_UNAVAILABLE: "desktop.signin.refused.keyring_unavailable",
  LOGIN_MISMATCH: "desktop.signin.refused.login_mismatch",
  GENERATION_CHANGED: "desktop.signin.refused.generation_changed",
  RUNTIME_UNAVAILABLE: "desktop.signin.refused.runtime_unavailable",
};

export function SignInRefusalMessage({
  refusal,
  seconds,
}: {
  refusal: SignInRefusal | null;
  seconds: number;
}) {
  const t = useStrings();
  if (!refusal) return null;
  return (
    <p role="status">
      {t(
        refusal.code.toUpperCase() === "THROTTLED"
          ? "desktop.signin.refused.throttled"
          : (refusalKeys[refusal.code.toUpperCase()] ??
              "desktop.signin.refused.other"),
        { code: refusal.code, seconds },
      )}
    </p>
  );
}

export function SignIn({ account }: { account: SignInController }) {
  const t = useStrings();
  const input = useRef<HTMLInputElement>(null);
  const seconds = account.retrySeconds;
  if (!account.status)
    return (
      <p className="pane-note" role="status">
        {t("desktop.signin.checking")}
      </p>
    );
  return (
    <section className="sign-in" aria-label={t("desktop.signin.title")}>
      <h2>{t("desktop.signin.title")}</h2>
      {account.status.active_profile && <p>{account.status.active_profile}</p>}
      <p>{t("desktop.signin.lead")}</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!input.current || account.busy || seconds > 0) return;
          const bytes = new TextEncoder().encode(input.current.value);
          input.current.value = "";
          void account.submit(bytes);
        }}
      >
        <label htmlFor="profile-password">{t("desktop.signin.password")}</label>
        <input
          ref={input}
          id="profile-password"
          type="password"
          autoComplete="current-password"
          required
          disabled={account.busy || !account.status.runtimeAvailable}
        />
        <button
          type="submit"
          disabled={
            account.busy || seconds > 0 || !account.status.runtimeAvailable
          }
        >
          {t(
            account.busy
              ? "desktop.signin.submitting"
              : "desktop.signin.submit",
          )}
        </button>
      </form>
      <SignInRefusalMessage refusal={account.refusal} seconds={seconds} />
      {!account.status.runtimeAvailable && !account.refusal && (
        <p role="status">{t("desktop.signin.refused.runtime_unavailable")}</p>
      )}
      <p>{t("desktop.signin.open_tui_hint")}</p>
      <button onClick={account.openTui} disabled={account.busy}>
        {t("desktop.signin.open_tui")}
      </button>
    </section>
  );
}

export function Account({ account }: { account: SignInController }) {
  const t = useStrings();
  if (!account.status?.supported) return null;
  return (
    <section className="account" aria-label={t("desktop.account.title")}>
      <h3>{t("desktop.account.title")}</h3>
      <p>
        {t(
          account.status.state === "present"
            ? "desktop.account.signed_in"
            : account.status.state === "absent"
              ? "desktop.account.signed_out"
              : "desktop.account.unknown",
        )}
      </p>
      <button
        disabled={account.busy || account.status.state !== "present"}
        onClick={() => void account.signOut()}
      >
        {t("desktop.account.sign_out")}
      </button>
      <p>{t("desktop.account.sign_out_hint")}</p>
      {account.remaining &&
        account.remaining.remainingAccess.automationEnabled !== false && (
          <p role="status">{t("desktop.account.remaining_access")}</p>
        )}
      <SignInRefusalMessage
        refusal={account.refusal}
        seconds={account.retrySeconds}
      />
    </section>
  );
}
