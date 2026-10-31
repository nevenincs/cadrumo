import { useEffect, useId, useRef, useState } from "react";
import { TextEditor } from "@/components/editors/TextEditor";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import type { ProfileDeleteReview, ProfileList } from "@/ipc/contract";
import { nameable, type ProfileAccounts } from "@/shell/profiles";
import type { SignInController } from "@/shell/signIn";
import { useStrings } from "@/shell/strings";

export function ManageProfiles({
  profiles,
  account,
  onClose,
  onCreate,
}: {
  profiles: ProfileAccounts;
  account: SignInController;
  onClose: () => void;
  onCreate: () => void;
}) {
  const t = useStrings();
  const [list, setList] = useState<ProfileList | null>(null);
  const [review, setReview] = useState<ProfileDeleteReview | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const nameInput = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleted, setDeleted] = useState<string | null>(null);
  const confirmationId = useId();
  const acknowledgementId = useId();
  useEffect(() => {
    if (review) nameInput.current?.focus();
  }, [review]);
  useEffect(() => {
    let current = true;
    void profiles
      .list()
      .then((value) => {
        if (current) setList(value);
      })
      .catch(() => {
        if (current) setError("desktop.signin.profiles_unread");
      });
    return () => {
      current = false;
    };
  }, [profiles]);
  const reset = () => {
    setReview(null);
    setConfirmation("");
    setAcknowledged(false);
    setError(null);
  };
  const failureKey = (error: unknown) => {
    const code =
      typeof error === "object" && error !== null && "code" in error
        ? String(error.code).toLowerCase()
        : "";
    return code.includes("retention") || code === "custody_refused"
      ? "desktop.account.manage.retained"
      : "desktop.account.manage.failed";
  };
  const prepare = async (name: string) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    reset();
    setDeleted(null);
    try {
      setReview(await profiles.reviewDelete(name));
    } catch (error) {
      setError(failureKey(error));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  const remove = async () => {
    if (
      !review ||
      pending.current ||
      confirmation !== review.name ||
      !acknowledged
    )
      return;
    pending.current = true;
    setBusy(true);
    setError(null);
    try {
      await profiles.delete(review, confirmation, acknowledged);
      setDeleted(review.name);
      reset();
      // Completion is authoritative; failed refresh must not offer a duplicate deletion.
      setList(null);
      await account.profilesChanged();
      try {
        setList(await profiles.list());
      } catch {
        setError("desktop.signin.profiles_unread");
      }
    } catch (error) {
      reset();
      setError(failureKey(error));
      setList(null);
      // A lost reply has an unknown outcome. Reobserve, never auto-repeat.
      await account.profilesChanged();
      try {
        setList(await profiles.list());
      } catch {
        /* Keep unavailable. */
      }
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent
        closeLabel={t("desktop.signin.dismiss")}
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
        onInteractOutside={(event) => {
          if (busy) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle className="wrap-anywhere">
            {t(
              review
                ? "desktop.account.manage.delete_title"
                : "desktop.account.manage.title",
              { name: review?.name ?? "" },
            )}
          </DialogTitle>
          <DialogDescription>
            {t(
              review
                ? "desktop.account.manage.loss"
                : "desktop.account.manage.scope",
            )}
          </DialogDescription>
        </DialogHeader>
        {error && (
          <Alert tone="danger" role="alert">
            {t(error)}
          </Alert>
        )}
        {!review && (error || list?.complete === false) && (
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void profiles
                .list()
                .then((value) => {
                  setList(value);
                  setError(null);
                })
                .catch(() => setError("desktop.signin.profiles_unread"))
                .finally(() => setBusy(false));
            }}
          >
            {t("desktop.profile.refresh")}
          </Button>
        )}
        {deleted && (
          <Alert tone="success" role="status">
            {t("desktop.account.manage.deleted", { name: deleted })}
          </Alert>
        )}
        {review ? (
          <form
            className="grid min-w-0 gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void remove();
            }}
          >
            <div className="grid min-w-0 gap-2">
              <Label htmlFor={confirmationId} className="wrap-anywhere">
                {t("desktop.account.manage.confirm_name", {
                  name: review.name,
                })}
              </Label>
              <TextEditor
                ref={nameInput}
                id={confirmationId}
                value={confirmation}
                onChange={setConfirmation}
                readOnly={busy}
              />
            </div>
            <Label
              htmlFor={acknowledgementId}
              className="flex items-start gap-2"
            >
              <Checkbox
                id={acknowledgementId}
                className="mt-1"
                checked={acknowledged}
                disabled={busy}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              {t("desktop.account.manage.acknowledge")}
            </Label>
            <DialogFooter>
              <Button
                variant="ghost"
                type="button"
                disabled={busy}
                onClick={reset}
              >
                {t("desktop.account.manage.cancel")}
              </Button>
              <Button
                variant="destructive"
                type="submit"
                pending={busy}
                disabled={!acknowledged || confirmation !== review.name}
              >
                {t("desktop.account.manage.delete")}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <div className="grid min-w-0 gap-4">
            {!list ? (
              !error && (
                <p role="status">{t("desktop.account.manage.loading")}</p>
              )
            ) : !list.complete ? (
              !error && (
                <Alert tone="warning">
                  {t("desktop.signin.profiles_unread")}
                </Alert>
              )
            ) : (
              <ul className="grid min-w-0 gap-2 overflow-y-auto">
                {list.profiles.map((profile) => (
                  <li
                    key={profile.name}
                    className="flex min-w-0 items-center justify-between gap-3 rounded-md bg-accent p-3"
                  >
                    <span className="min-w-0 flex-1 wrap-anywhere">
                      {profile.name}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy || !nameable(profile.name)}
                      onClick={() => void prepare(profile.name)}
                      aria-label={t("desktop.account.manage.delete_title", {
                        name: profile.name,
                      })}
                    >
                      {t("desktop.account.manage.delete")}
                    </Button>
                  </li>
                ))}
                {list.profiles.length === 0 && (
                  <li>{t("desktop.account.no_profile")}</li>
                )}
              </ul>
            )}
            {account.offering ? (
              <Button disabled={busy || account.busy} onClick={onCreate}>
                {t("desktop.account.new_profile")}
              </Button>
            ) : (
              <Button
                variant="outline"
                disabled={busy || account.busy}
                onClick={() => void account.signOut()}
              >
                {t("desktop.account.manage.sign_out_create")}
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
