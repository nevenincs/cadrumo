import { useState, type ReactNode } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon, type IconName } from "@/components/ui/icon";
import type { SedeViewFailureCode } from "../../ipc/contract";
import { useStrings } from "../../shell/strings";
import type {
  ChooserOffer,
  DownloadOffer,
  PageNotice,
  TransferNote,
} from "./browserModel";
import { failureText, noticeText, transferText } from "./browserWords";

type Tone = "neutral" | "success" | "warning" | "danger";

/** One line over the page, with what the person can do about it. */
function Line({
  tone = "neutral",
  icon,
  role,
  more,
  children,
  actions,
}: {
  tone?: Tone;
  icon: IconName;
  role?: "alert";
  /** How many more of its kind wait behind it. */
  more?: number;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const t = useStrings();
  return (
    <Alert
      tone={tone}
      role={role}
      icon={<Icon name={icon} />}
      className="pointer-events-auto bg-card shadow-overlay"
    >
      <div>{children}</div>
      {(actions || more) && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {actions}
          {more ? (
            <span className="text-sm text-muted-foreground">
              {t("desktop.browser.notice.more", { count: more })}
            </span>
          ) : null}
        </div>
      )}
    </Alert>
  );
}

/** Waits for the native dialog the answer opens. */
function Waiting({
  children,
  run,
  ...props
}: {
  children: ReactNode;
  run: () => Promise<void>;
  variant?: "primary" | "outline" | "ghost";
}) {
  const [pending, setPending] = useState(false);
  return (
    <Button
      size="xs"
      pending={pending}
      onClick={() => {
        setPending(true);
        void run().finally(() => setPending(false));
      }}
      {...props}
    >
      {children}
    </Button>
  );
}

/**
 * What the view asks of the person, over the top of the page, oldest first:
 * a refused call, a login that runs, a download or a file the page asks for,
 * a notice with its way into the person's own browser, and how the last
 * transfer ended. Only the first of each kind shows, with a count behind it.
 */
export function BrowserPrompts({
  acquiring,
  problem,
  downloads,
  choosers,
  notices,
  note,
  onAnswerDownload,
  onAnswerChooser,
  onOpenExternal,
  onDismissNotice,
  onDismissNote,
  onDismissProblem,
}: {
  acquiring: boolean;
  problem: SedeViewFailureCode | null;
  downloads: readonly DownloadOffer[];
  choosers: readonly ChooserOffer[];
  notices: readonly PageNotice[];
  note: TransferNote | null;
  onAnswerDownload: (transferId: number, save: boolean) => Promise<void>;
  onAnswerChooser: (chooserId: number, choose: boolean) => Promise<void>;
  onOpenExternal: (offerId: string) => void;
  onDismissNotice: (key: number) => void;
  onDismissNote: () => void;
  onDismissProblem: () => void;
}) {
  const t = useStrings();
  const download = downloads[0];
  const chooser = choosers[0];
  const notice = notices[0];
  const dismiss = (run: () => void) => (
    <Button size="xs" variant="ghost" onClick={run}>
      {t("desktop.browser.notice.dismiss")}
    </Button>
  );
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-x-3 top-3 z-(--layer-pinned) flex flex-col gap-2",
      )}
      data-browser-prompts=""
    >
      {problem && (
        <Line
          tone="warning"
          icon="alert"
          role="alert"
          actions={dismiss(onDismissProblem)}
        >
          {failureText(t, problem)}
        </Line>
      )}
      {acquiring && <Line icon="key">{t("desktop.browser.acquiring")}</Line>}
      {download && (
        <Line
          key={`download-${download.transferId}`}
          icon="download"
          more={downloads.length - 1}
          actions={
            <>
              <Waiting run={() => onAnswerDownload(download.transferId, true)}>
                {t("desktop.browser.download.save")}
              </Waiting>
              <Waiting
                variant="ghost"
                run={() => onAnswerDownload(download.transferId, false)}
              >
                {t("desktop.browser.download.decline")}
              </Waiting>
            </>
          }
        >
          {t("desktop.browser.download.prompt", { name: download.filename })}
        </Line>
      )}
      {chooser && (
        <Line
          key={`chooser-${chooser.chooserId}`}
          icon="upload"
          more={choosers.length - 1}
          actions={
            <>
              <Waiting run={() => onAnswerChooser(chooser.chooserId, true)}>
                {t("desktop.browser.upload.choose")}
              </Waiting>
              <Waiting
                variant="ghost"
                run={() => onAnswerChooser(chooser.chooserId, false)}
              >
                {t("desktop.browser.upload.decline")}
              </Waiting>
            </>
          }
        >
          {chooser.multiple
            ? t("desktop.browser.upload.prompt_many")
            : t("desktop.browser.upload.prompt")}
        </Line>
      )}
      {notice && (
        <Line
          key={`notice-${notice.key}`}
          icon="info"
          more={notices.length - 1}
          actions={
            <>
              {notice.offerId !== null && (
                <Button
                  size="xs"
                  onClick={() => {
                    if (notice.offerId !== null) onOpenExternal(notice.offerId);
                    onDismissNotice(notice.key);
                  }}
                >
                  {t("desktop.browser.external")}
                </Button>
              )}
              {dismiss(() => onDismissNotice(notice.key))}
            </>
          }
        >
          {noticeText(t, notice.code)}
        </Line>
      )}
      {note && (
        <Line
          tone={
            note.outcome === "done"
              ? "success"
              : note.outcome === "failed"
                ? "danger"
                : "neutral"
          }
          icon={note.outcome === "done" ? "check" : "info"}
          actions={dismiss(onDismissNote)}
        >
          {transferText(t, note.kind, note.outcome)}
        </Line>
      )}
    </div>
  );
}
