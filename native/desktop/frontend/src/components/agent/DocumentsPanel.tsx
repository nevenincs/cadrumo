import { useId, useState } from "react";
import { cn } from "@/components/ui/cn";
import { Empty, EmptyTitle } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { NativeSelect } from "@/components/ui/native-select";
import { useStrings, type Translate } from "../../shell/strings";
import { AgentIconAction } from "./AgentAction";
import { extensionLabel, formatSize, KIND_GLYPH } from "./files";
import type {
  ConversationDocument,
  DocumentRole,
  DocumentStatus,
} from "./types";

const ROLES: readonly DocumentRole[] = ["context", "information", "ledger"];

function roleWords(t: Translate): Record<DocumentRole, string> {
  return {
    context: t("desktop.agent.role_context"),
    information: t("desktop.agent.role_information"),
    ledger: t("desktop.agent.role_ledger"),
  };
}

function statusWords(t: Translate): Record<DocumentStatus, string> {
  return {
    uploading: t("desktop.agent.status_uploading"),
    ready: t("desktop.agent.status_ready"),
    extracting: t("desktop.agent.status_extracting"),
    needsReview: t("desktop.agent.status_needs_review"),
    failed: t("desktop.agent.status_failed"),
    skipped: t("desktop.agent.status_skipped"),
  };
}

// Filled while a document is usable or on its way, hollow once it is not.
const STATUS_DOT: Record<DocumentStatus, string> = {
  uploading: "bg-faint",
  ready: "bg-success",
  extracting: "bg-faint",
  needsReview: "bg-warning",
  failed: "ring-1 ring-destructive ring-inset",
  skipped: "ring-1 ring-faint ring-inset",
};

function StatusLabel({ status }: { status: DocumentStatus }) {
  const t = useStrings();
  return (
    <span
      className={cn(
        "flex items-center gap-1.5",
        status === "failed" && "text-destructive",
        status === "needsReview" && "text-warning",
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-1.5 shrink-0 rounded-full", STATUS_DOT[status])}
      />
      {statusWords(t)[status]}
    </span>
  );
}

/** A document's preview or type, at the size of a control. */
function DocumentMark({ document }: { document: ConversationDocument }) {
  if (document.kind === "image" && document.thumbnailUrl)
    return (
      <img
        src={document.thumbnailUrl}
        alt=""
        className="size-control-md shrink-0 rounded-md border object-cover"
      />
    );
  return (
    <span
      aria-hidden="true"
      className="flex size-control-md shrink-0 items-center justify-center rounded-md bg-accent text-muted-foreground"
    >
      <Icon name={document.kind ? KIND_GLYPH[document.kind] : "page"} />
    </span>
  );
}

function MemberRow({
  member,
  locale,
}: {
  member: ConversationDocument;
  locale: string;
}) {
  return (
    <li className="flex min-w-0 items-center gap-2 py-1 pr-2 pl-20 text-xs text-muted-foreground">
      <span
        className="min-w-0 flex-1 truncate text-foreground"
        title={member.name}
      >
        {member.name}
      </span>
      <StatusLabel status={member.status} />
      <span className="shrink-0 tabular-nums">
        {formatSize(locale, member.sizeBytes)}
      </span>
    </li>
  );
}

function DocumentRow({
  document,
  locale,
  onRoleChange,
  onRemove,
}: {
  document: ConversationDocument;
  locale: string;
  onRoleChange?: (role: DocumentRole) => void;
  onRemove?: () => void;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const roleId = useId();
  const reasonId = useId();
  const membersId = useId();
  const roles = roleWords(t);
  const members = document.members ?? [];
  return (
    <li className="grid gap-1 border-b py-2 last:border-b-0">
      <div className="flex min-w-0 items-center gap-2 px-2">
        {members.length > 0 ? (
          <IconButton
            label={
              open
                ? t("desktop.agent.collapse_members", { name: document.name })
                : t("desktop.agent.expand_members", { name: document.name })
            }
            aria-expanded={open}
            aria-controls={membersId}
            onClick={() => setOpen((was) => !was)}
          >
            <Icon name={open ? "chevronDown" : "forward"} />
          </IconButton>
        ) : (
          <span aria-hidden="true" className="size-control-xs shrink-0" />
        )}
        <DocumentMark document={document} />
        <div className="grid min-w-0 flex-1">
          <span className="truncate text-foreground" title={document.name}>
            {document.name}
          </span>
          <span className="flex min-w-0 flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
            <span>{extensionLabel(document.extension)}</span>
            <span className="tabular-nums">
              {formatSize(locale, document.sizeBytes)}
            </span>
            <StatusLabel status={document.status} />
          </span>
        </div>
        <AgentIconAction
          icon="close"
          label={t("desktop.agent.remove_document", { name: document.name })}
          onAction={onRemove}
        />
      </div>
      {/* At the column's default width the reason wraps under the select
          rather than squeezing the role names. */}
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 pr-2 pl-20">
        <label
          htmlFor={roleId}
          className="shrink-0 text-xs text-muted-foreground"
        >
          {t("desktop.agent.role_label")}
        </label>
        <div className="shrink-0">
          <NativeSelect
            id={roleId}
            controlSize="sm"
            value={document.role}
            disabled={!onRoleChange}
            aria-describedby={onRoleChange ? undefined : reasonId}
            onChange={(event) => {
              const role = ROLES.find((value) => value === event.target.value);
              if (role) onRoleChange?.(role);
            }}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {roles[role]}
              </option>
            ))}
          </NativeSelect>
        </div>
        {!onRoleChange && (
          <span id={reasonId} className="text-xs text-faint">
            {t("desktop.agent.unavailable")}
          </span>
        )}
      </div>
      {members.length > 0 && (
        <ul id={membersId} hidden={!open}>
          {members.map((member) => (
            <MemberRow key={member.id} member={member} locale={locale} />
          ))}
        </ul>
      )}
    </li>
  );
}

/**
 * The documents that are part of the conversation: what each is, how it is
 * used, and where it is on its way to being usable. An archive's row opens
 * to the files inside it; files it did not take say they were skipped.
 */
export function DocumentsPanel({
  documents,
  locale,
  onClose,
  onRoleChange,
  onRemove,
}: {
  documents: readonly ConversationDocument[];
  locale: string;
  onClose?: () => void;
  onRoleChange?: (id: string, role: DocumentRole) => void;
  onRemove?: (id: string) => void;
}) {
  const t = useStrings();
  const titleId = useId();
  const total = documents.reduce((sum, file) => sum + file.sizeBytes, 0);
  const review = documents.filter(
    (file) => file.status === "needsReview",
  ).length;
  const failed = documents.filter((file) => file.status === "failed").length;
  return (
    <section
      aria-labelledby={titleId}
      className="flex min-h-0 flex-1 flex-col bg-background"
    >
      <div className="flex h-control-lg shrink-0 items-center gap-2 border-b bg-chrome pr-1.5 pl-3">
        <h2 id={titleId} className="min-w-0 flex-1 truncate font-semibold">
          {t("desktop.agent.documents")}
        </h2>
        <AgentIconAction
          icon="close"
          label={t("desktop.agent.close_documents")}
          onAction={onClose}
        />
      </div>
      {documents.length === 0 ? (
        <Empty>
          <EmptyTitle>{t("desktop.agent.documents_empty")}</EmptyTitle>
        </Empty>
      ) : (
        <>
          <p className="flex shrink-0 flex-wrap gap-x-2 px-3 py-2 text-xs text-muted-foreground">
            <span>
              {t("desktop.agent.files_summary", {
                count: documents.length,
                size: formatSize(locale, total),
              })}
            </span>
            {review > 0 && (
              <span className="text-warning">
                {t("desktop.agent.documents_review", { count: review })}
              </span>
            )}
            {failed > 0 && (
              <span className="text-destructive">
                {t("desktop.agent.documents_failed", { count: failed })}
              </span>
            )}
          </p>
          <ul className="min-h-0 flex-1 overflow-y-auto border-t">
            {documents.map((document) => (
              <DocumentRow
                key={document.id}
                document={document}
                locale={locale}
                onRoleChange={
                  onRoleChange
                    ? (role) => onRoleChange(document.id, role)
                    : undefined
                }
                onRemove={onRemove ? () => onRemove(document.id) : undefined}
              />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
