import {
  useDeferredValue,
  useMemo,
  useState,
  type RefObject,
  type SetStateAction,
} from "react";
import type { ITheme } from "@xterm/xterm";
import type { ProfileView } from "../../shell/layout";
import { IconButton } from "@/components/ui/icon-button";
import type { Host } from "../../shell/host";
import { useStrings } from "../../shell/strings";
import {
  fieldValue,
  profileText,
  useUserProfile,
  type ProfileField,
  type ProfileSection,
} from "../../shell/userProfile";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Spinner } from "@/components/ui/spinner";
import { Icon } from "@/components/ui/icon";
import { ProfileEditor, type ProfileDraft } from "./ProfileEditor";
import { ProfileSectionCard } from "./ProfileSectionCard";
import { AeatSetupDialog } from "../agent/AeatSetupDialog";
import { CensoDialog } from "./CensoDialog";

export function UserProfilePage({
  host,
  reader,
  language,
  shown,
  theme,
  fontSize,
  page,
  maximized,
  view,
  onViewChange,
}: {
  host: Host;
  reader: string;
  language: string;
  shown: boolean;
  theme: ITheme;
  fontSize: number;
  page: RefObject<HTMLElement | null>;
  maximized: boolean;
  view: ProfileView;
  onViewChange(update: (current: ProfileView) => ProfileView): void;
}) {
  const t = useStrings();
  const profile = useUserProfile(host.userProfile, reader, language, shown);
  const [search, setSearch] = useState("");
  const { section, filter } = view;
  const expanded = new Set(view.expanded);
  const collapsed = new Set(view.collapsed);
  const setSection = (section: string) =>
    onViewChange((current) => ({ ...current, section }));
  const setFilter = (filter: ProfileView["filter"]) =>
    onViewChange((current) => ({ ...current, filter }));
  const setMembership = (
    key: "expanded" | "collapsed",
    update: SetStateAction<Set<string>>,
  ) =>
    onViewChange((current) => ({
      ...current,
      [key]: [
        ...(typeof update === "function"
          ? update(new Set(current[key]))
          : update),
      ],
    }));
  const setExpanded = (update: SetStateAction<Set<string>>) =>
    setMembership("expanded", update);
  const setCollapsed = (update: SetStateAction<Set<string>>) =>
    setMembership("collapsed", update);
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const [auth, setAuth] = useState(false);
  const [censo, setCenso] = useState(false);
  const [returnToCenso, setReturnToCenso] = useState(false);
  const query = profileText(useDeferredValue(search));
  const data = profile.data;
  const missing = useMemo(() => new Set(data?.missing_required), [data]);
  const chooseSection = (key: string) => {
    setSection(key);
    setCollapsed(new Set());
    if (key) setExpanded((current) => new Set([...current, key]));
  };
  const sections = useMemo(
    () =>
      data?.sections
        .filter((item) => !section || item.key === section)
        .map((item) => ({
          ...item,
          fields: item.fields.filter((field) => {
            const empty = field.value === null || field.value === "";
            const match =
              filter === "missing"
                ? empty
                : filter === "required"
                  ? missing.has(field.path)
                  : filter === "saved"
                    ? !empty
                    : true;
            return (
              match &&
              (!query ||
                profileText(
                  [
                    item.title,
                    field.label,
                    ...(field.help ?? []),
                    field.masked ? "" : (fieldValue(field) ?? ""),
                  ].join(" "),
                ).includes(query))
            );
          }),
        }))
        .filter((item) => item.fields.length),
    [data, section, filter, missing, query],
  );
  const errorKeys = {
    unavailable: "desktop.profile.unavailable",
    not_signed_in: "desktop.profile.signed_out",
    refused: "desktop.profile.refused",
    conflict: "desktop.profile.conflict",
    unknown: "desktop.profile.unknown",
    saved_unread: "desktop.profile.saved_unread",
  } as const;
  const error = profile.error ? t(errorKeys[profile.error]) : null;
  const busy = profile.saving || profile.loading;
  const open = (item: ProfileSection, field?: ProfileField, remove = false) => {
    if (!data) return;
    const original = data.sections.find((entry) => entry.key === item.key)!;
    const fields = field
      ? original.repeatable
        ? original.fields.filter((entry) => entry.row_index === field.row_index)
        : [field]
      : [
          ...new Map(
            original.fields.map((entry) => [
              entry.path.slice(
                original.key.length +
                  1 +
                  (entry.row_index === null ? 0 : entry.row_index.length + 1),
              ),
              entry,
            ]),
          ).values(),
        ];
    const existing = fields.some(
      (entry) => entry.value !== null && entry.value !== "",
    );
    setDraft({
      base: data,
      section: original,
      fields,
      kind: remove
        ? "remove_row"
        : original.repeatable
          ? !field || !existing
            ? "add_row"
            : "update_row"
          : "field",
    });
  };
  return (
    <section
      ref={page}
      tabIndex={-1}
      className="user-profile-page @container/profile flex min-h-0 flex-1 flex-col outline-none"
      aria-label={t("desktop.profile.title")}
    >
      <header className="flex flex-wrap items-center justify-end gap-2 border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={!data || busy}
            onClick={() => setCenso(true)}
          >
            {t("desktop.profile.censo.title")}
          </Button>
          <IconButton
            size="sm"
            onClick={profile.refresh}
            disabled={busy}
            label={t("desktop.profile.refresh")}
          >
            <Icon name="reset" />
          </IconButton>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        {data && maximized && (
          <nav
            aria-label={t("desktop.profile.sections")}
            className="hidden w-menu shrink-0 overflow-y-auto border-r p-3 sm:block"
          >
            <Button
              size="sm"
              variant={section === "" ? "secondary" : "ghost"}
              className="mb-2 w-full justify-start"
              onClick={() => chooseSection("")}
              aria-current={section === "" ? "page" : undefined}
            >
              {t("desktop.profile.all_sections")}
            </Button>
            {data.sections
              .filter((item) => item.fields.length)
              .map((item) => {
                const count = item.fields.filter((field) =>
                  missing.has(field.path),
                ).length;
                return (
                  <Button
                    key={item.key}
                    size="sm"
                    variant={section === item.key ? "secondary" : "ghost"}
                    className="h-auto w-full justify-between gap-2 py-2 text-left whitespace-normal"
                    onClick={() => chooseSection(item.key)}
                    aria-current={section === item.key ? "page" : undefined}
                  >
                    <span>{item.title}</span>
                    {count > 0 && <Badge variant="warning">{count}</Badge>}
                  </Button>
                );
              })}
          </nav>
        )}
        <div className="min-w-0 flex-1 overflow-y-auto p-4">
          {error && (
            <Alert role="alert" tone="danger">
              {error}
            </Alert>
          )}
          {profile.saved && !error && (
            <div role="status" className="mb-2 text-sm text-muted-foreground">
              {t("desktop.profile.saved_notice")}
            </div>
          )}
          {profile.loading && (
            <div role="status" className="flex items-center gap-2 py-2">
              <Spinner />
              {t("desktop.profile.loading")}
            </div>
          )}
          {data && (
            <>
              <div
                className="mb-4 flex flex-wrap items-center gap-2"
                role="search"
                aria-label={t("desktop.profile.search")}
              >
                <Input
                  type="search"
                  className="min-w-0 flex-1 basis-field"
                  aria-label={t("desktop.profile.search")}
                  placeholder={t("desktop.profile.search")}
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setCollapsed(new Set());
                  }}
                />
                <NativeSelect
                  className={
                    maximized
                      ? "w-auto max-w-full sm:hidden"
                      : "w-auto max-w-full"
                  }
                  aria-label={t("desktop.profile.sections")}
                  value={section}
                  onChange={(event) => chooseSection(event.target.value)}
                >
                  <option value="">{t("desktop.profile.all_sections")}</option>
                  {data.sections
                    .filter((item) => item.fields.length)
                    .map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.title}
                      </option>
                    ))}
                </NativeSelect>
                <NativeSelect
                  className="w-auto max-w-full"
                  aria-label={t("desktop.profile.filter")}
                  value={filter}
                  onChange={(event) => {
                    setFilter(event.target.value as ProfileView["filter"]);
                    setCollapsed(new Set());
                  }}
                >
                  <option value="all">{t("desktop.profile.all_fields")}</option>
                  <option value="missing">
                    {t("desktop.profile.missing_filter")}
                  </option>
                  <option value="required">
                    {t("desktop.profile.required_filter")}
                  </option>
                  <option value="saved">
                    {t("desktop.profile.saved_filter")}
                  </option>
                </NativeSelect>
              </div>
              <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => {
                    setCollapsed(new Set());
                    setExpanded(new Set(data.sections.map((item) => item.key)));
                  }}
                >
                  {t("desktop.profile.expand_all")}
                </Button>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => {
                    setSearch("");
                    setFilter("all");
                    setExpanded(new Set());
                    setCollapsed(new Set());
                  }}
                >
                  {t("desktop.profile.collapse_all")}
                </Button>
              </div>
              <div className="grid gap-3">
                {sections?.map((item) => (
                  <ProfileSectionCard
                    key={item.key}
                    section={item}
                    expanded={
                      !collapsed.has(item.key) &&
                      (expanded.has(item.key) || !!query || filter !== "all")
                    }
                    onToggle={() => {
                      const isOpen =
                        !collapsed.has(item.key) &&
                        (expanded.has(item.key) || !!query || filter !== "all");
                      setCollapsed((current) => {
                        const next = new Set(current);
                        if (isOpen) next.add(item.key);
                        else next.delete(item.key);
                        return next;
                      });
                      setExpanded((current) => {
                        const next = new Set(current);
                        if (isOpen) next.delete(item.key);
                        else next.add(item.key);
                        return next;
                      });
                    }}
                    missing={missing}
                    busy={busy}
                    onEdit={(field, remove) => open(item, field, remove)}
                    onAuth={() => setAuth(true)}
                  />
                ))}
              </div>
              {!sections?.length && (
                <p className="py-5 text-muted-foreground">
                  {t("desktop.profile.empty")}
                </p>
              )}
              {data.notices.map((notice, index) => (
                <Alert key={index}>{notice.message}</Alert>
              ))}
              {data.setup_state !== "complete" &&
                missing.size === 0 &&
                data.valid && (
                  <Button
                    className="mt-4"
                    disabled={busy || profile.error === "unknown"}
                    onClick={() =>
                      void profile.save(data, { kind: "complete" })
                    }
                  >
                    {t("desktop.profile.complete")}
                  </Button>
                )}
            </>
          )}
        </div>
      </div>
      {draft && (
        <ProfileEditor
          draft={draft}
          busy={busy}
          blocked={profile.error === "unknown"}
          onRefresh={profile.refresh}
          changed={
            !data ||
            draft.base.record_revision !== data.record_revision ||
            draft.base.content_digest !== data.content_digest
          }
          error={error}
          onSave={(edit) => profile.save(draft.base, edit)}
          onClose={() => {
            setDraft(null);
            if (returnToCenso) {
              setReturnToCenso(false);
              setCenso(true);
            }
          }}
        />
      )}
      {auth && data && (
        <AeatSetupDialog
          host={host}
          profile={data.profile_id}
          theme={theme}
          fontSize={fontSize}
          onClose={() => {
            setAuth(false);
            if (returnToCenso) {
              setReturnToCenso(false);
              setCenso(true);
            }
          }}
          onDone={() => {
            setAuth(false);
            profile.refresh();
            if (returnToCenso) {
              setReturnToCenso(false);
              setCenso(true);
            }
          }}
        />
      )}
      {data && (
        <CensoDialog
          key={data.profile_id}
          port={host.censo}
          profile={data}
          open={censo}
          onClose={() => setCenso(false)}
          onRefresh={profile.refresh}
          onSetup={() => {
            setCenso(false);
            setReturnToCenso(true);
            setAuth(true);
          }}
          onIdentity={() => {
            setCenso(false);
            setReturnToCenso(true);
            const identity = data.sections.find(
              (item) => item.key === "identity",
            );
            const field = identity?.fields.find(
              (item) => item.path === "identity.tax_id",
            );
            if (identity && field) open(identity, field);
          }}
        />
      )}
    </section>
  );
}
