import { cn } from "@/components/ui/cn";
import { requiredSection, sectionCounts } from "../../shell/profileRows";
import { useStrings } from "../../shell/strings";
import type { ProfileSection } from "../../shell/userProfile";
import { RequiredMark } from "./ProfileMarks";

/** The full-screen page's index of its sections, each with how complete it
 * is, marking the one in view. */
export function ProfileSectionIndex({
  sections,
  missing,
  current,
  onGoToSection,
}: {
  sections: ProfileSection[];
  /** The paths of the required details still missing. */
  missing: Set<string>;
  /** The section in view. */
  current: string;
  onGoToSection(key: string): void;
}) {
  const t = useStrings();
  return (
    <nav
      aria-label={t("desktop.profile.sections")}
      className="hidden w-menu shrink-0 overflow-y-auto border-r py-2 @2xl/profile:block"
    >
      <ul className="px-2">
        {sections.map((section) => {
          const c = sectionCounts(section, missing);
          return (
            <li key={section.key}>
              <button
                type="button"
                aria-current={current === section.key ? "location" : undefined}
                onClick={() => onGoToSection(section.key)}
                className={cn(
                  "flex w-full cursor-pointer items-baseline gap-2 rounded-md px-2 py-1 text-left text-sm text-muted-foreground hover:bg-accent hover:text-foreground",
                  "aria-[current]:bg-selected aria-[current]:font-medium aria-[current]:text-foreground",
                )}
              >
                <span className="flex min-w-0 flex-1 gap-1">
                  <span className="truncate">{section.title}</span>
                  {requiredSection(section) && <RequiredMark />}
                </span>
                <span className="shrink-0 text-xs text-faint tabular-nums">
                  {section.repeatable ? c.entries : `${c.filled}/${c.total}`}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
