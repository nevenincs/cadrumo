import type { ProfileCompanionPort } from "../../../shell/profileHousehold";
import type { UserProfilePort } from "../../../shell/userProfile";
import { ImputationElection } from "./ImputationElection";

/** The profile's reads and its one write door, which the profile's elements
 * call. */
export type ProfileCompanionKit = {
  reads: ProfileCompanionPort;
  change: UserProfilePort["change"];
};

/**
 * The companion elements the profile owns, drawn for a declaration whose form
 * says it asks for them. The declaration's own profile and tax year are served
 * with its form; each element reads and writes through the kit.
 */
export function ProfileCompanions({
  kit,
  profile,
  taxYear,
  language,
}: {
  kit: ProfileCompanionKit;
  profile: string;
  taxYear: number;
  language: string;
}) {
  return (
    <div className="flex flex-col gap-4">
      <ImputationElection
        profile={profile}
        taxYear={taxYear}
        language={language}
        reads={kit.reads}
        change={kit.change}
      />
    </div>
  );
}
