import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: ["ledger-assets-contract.spec.ts","ledger-classes.spec.ts","ledger-fixture-host.spec.ts","ledger-setup-model.spec.ts","ledger-apply.spec.ts","ledger-plan.spec.ts"],
  reporter: "line",
});
