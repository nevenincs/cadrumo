import { Button } from "@/components/ui/button";
import { useStrings } from "@/shell/strings";
import { BoxLine } from "./BoxLine";
import type { Family as FamilyData } from "./fixtures";
import { Gap } from "./Gap";

// The family unit: the profile facts the declaration reads, as the profile
// view serves them, beside the minimum boxes they feed. The facts are
// changed in the profile, never here, and the boxes stay the form's own.

export function Family({ family }: { family: FamilyData }) {
  const t = useStrings();
  return (
    <section className="flex max-w-4xl flex-col gap-4 p-4">
      <h2 className="text-lg font-semibold">
        {t("workspace.renta.outline.family")}
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {t("desktop.renta.proto.family.profile")}
          </h3>
          {family.profile.sections.map((section) => (
            <div
              key={section.key}
              className="rounded-md border border-border px-3 py-2"
            >
              <div className="text-sm font-medium">{section.title}</div>
              <dl className="mt-1 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
                {section.fields.map((field) => (
                  <div key={field.path} className="contents">
                    <dt className="text-muted-foreground">{field.label}</dt>
                    <dd className={field.value === null ? "text-faint" : ""}>
                      {field.value === null
                        ? t("desktop.renta.proto.family.empty")
                        : (field.choices.find((c) => c.value === field.value)
                            ?.label ?? field.value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
          <Gap operation="user-profile.view: choices for renta_filing.declaration_type" />
          <Gap operation="user-profile.descendants (not admitted by the desktop relay)" />
          <Button variant="outline" disabled>
            {t("desktop.renta.proto.family.edit")}
          </Button>
        </div>
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {t("desktop.renta.proto.family.boxes")}
          </h3>
          <ul className="rounded-md border border-border px-3">
            {family.minimums.map((field) => (
              <BoxLine key={field.state_digest} field={field} />
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
