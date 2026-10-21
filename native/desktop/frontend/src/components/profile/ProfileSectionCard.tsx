import { useId } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/components/ui/cn";
import {
  fieldValue,
  type ProfileField,
  type ProfileSection,
} from "../../shell/userProfile";
import { useStrings } from "../../shell/strings";

export function ProfileSectionCard({
  section,
  expanded,
  onToggle,
  missing,
  busy,
  onEdit,
  onAuth,
}: {
  section: ProfileSection;
  expanded: boolean;
  onToggle(): void;
  missing: Set<string>;
  busy: boolean;
  onEdit(field?: ProfileField, remove?: boolean): void;
  onAuth(): void;
}) {
  const t = useStrings(),
    id = useId();
  const count = section.fields.filter((field) =>
    missing.has(field.path),
  ).length;
  return (
    <section className="rounded-xl border bg-card" aria-label={section.title}>
      <header className="flex items-center gap-2 px-4 py-3">
        <h2 className="min-w-0 flex-1">
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={id}
            onClick={onToggle}
            className="flex w-full cursor-pointer items-center gap-2 text-left font-medium"
          >
            <Icon name={expanded ? "chevronDown" : "forward"} />
            {section.title}
          </button>
        </h2>
        {count > 0 && (
          <Badge variant="warning">
            {t("desktop.profile.missing_count", { count })}
          </Badge>
        )}
        {section.repeatable && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onEdit()}
            disabled={busy}
          >
            <Icon name="plus" />
            {t("desktop.profile.add")}
          </Button>
        )}
      </header>
      <div id={id} hidden={!expanded}>
        <div className="grid gap-3 border-t p-4 @2xl/profile:grid-cols-2">
          {section.fields.map((field) => {
            const absent = field.value === null || field.value === "";
            const required = missing.has(field.path);
            const protectedField =
              field.masked || field.path.startsWith("auth.");
            const firstInRow =
              section.fields.find(
                (entry) => entry.row_index === field.row_index,
              ) === field;
            const hasRow = section.fields.some(
              (entry) => entry.row_index === field.row_index && entry.value,
            );
            return (
              <div
                key={field.path}
                className={cn(
                  "min-w-0 rounded-lg border",
                  required && "border-warning",
                )}
              >
                <div className="relative flex items-start justify-between gap-2 rounded-lg p-3 hover:bg-accent">
                  <dl className="min-w-0 flex-1">
                    <dt className="text-sm text-muted-foreground">
                      {field.label}
                      {required && (
                        <Badge className="ml-2" variant="warning">
                          {t("desktop.profile.required")}
                        </Badge>
                      )}
                    </dt>
                    <dd
                      className={cn(
                        "mt-1 block break-words",
                        absent && "text-faint",
                      )}
                    >
                      {absent ? (
                        <span aria-label={t("desktop.profile.not_set")}>—</span>
                      ) : (
                        fieldValue(field)
                      )}
                    </dd>
                  </dl>
                  <Button
                    size="xs"
                    variant="ghost"
                    disabled={busy}
                    aria-label={t("desktop.profile.edit_field", {
                      field: field.label,
                    })}
                    onClick={() => (protectedField ? onAuth() : onEdit(field))}
                    className="after:absolute after:inset-0 after:rounded-lg focus-visible:after:ring-2 focus-visible:after:ring-ring"
                  >
                    {t("desktop.profile.edit")}
                  </Button>
                </div>
                {section.repeatable && firstInRow && hasRow && (
                  <Button
                    size="xs"
                    variant="ghost"
                    disabled={busy}
                    className="mb-3 ml-3"
                    onClick={() => onEdit(field, true)}
                  >
                    <Icon name="trash" />
                    {t("desktop.profile.remove")}
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
