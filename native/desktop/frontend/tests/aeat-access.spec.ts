import { expect, test } from "@playwright/test";
import { credentialFailure } from "../src/shell/userProfile";

// How a rejected credential save is read: whether the passphrase or password
// reached the runtime decides whether the person may be told to try again.
// No page is opened.

test("a refusal that settled before anything was sent says nothing happened", () => {
  for (const code of ["invalid", "refused", "conflict", "not_signed_in"])
    expect(credentialFailure({ code }), code).toBe("refused");
});

test("an unreachable service is unavailable, not unconfirmed", () => {
  expect(credentialFailure({ code: "unavailable" })).toBe("unavailable");
});

test("an outcome that was not observed stays unconfirmed, whatever its shape", () => {
  for (const failure of [
    { code: "unknown" },
    { code: "saved_unread" },
    { code: "unknown", operation_id: "a".repeat(64) },
    { code: "something_new" },
    { code: 7 },
    "unknown",
    new Error("lost"),
    null,
    undefined,
  ])
    expect(credentialFailure(failure), String(failure)).toBe("unconfirmed");
});
