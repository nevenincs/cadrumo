import { expect, test } from "@playwright/test";
import {
  consoleSummary,
  errorEventSummary,
  isResizeObserverNotice,
  moduleName,
  redactTemplate,
  rejectionSummary,
} from "../src/shell/diagnosticSummary";

// The same expectations as the host's own admission tests: the host applies
// the rule again, so the two copies must agree on every case here.

test("a library's prop warning keeps its shape and loses every value", () => {
  expect(
    redactTemplate(
      "Invalid prop `value` of value `2` supplied to `Progress`. Defaulting to `null`.",
    ),
  ).toBe("Invalid prop `…` of value `…` supplied to `…`. Defaulting to `…`.");
});

test("private values never survive a template or a module", () => {
  const encoded = JSON.stringify([
    redactTemplate('Cannot read X1234567L for Juan García 1.234,56 "secret"'),
    redactTemplate("TypeError: juan@example.com IBAN ES9121000418450200051332"),
    redactTemplate("Failed `private-canary"),
    moduleName("C:\\Users\\Juan\\a.js"),
    moduleName("file:///home/private-canary/x"),
    moduleName("https://example.com/private-canary/"),
  ]);
  for (const secret of [
    "X1234567L",
    "Juan",
    "Garc",
    "1.234",
    "secret",
    "example.com",
    "ES91",
    "private-canary",
    "Users",
    "home",
  ])
    expect(encoded).not.toContain(secret);
  expect(redactTemplate("12 345")).toBeNull();
  expect(moduleName("/private/x.exe")).toBeNull();
  expect(
    moduleName("http://127.0.0.1:1430/assets/palette-Ab12_c.js?v=3#x"),
  ).toBe("palette-Ab12_c.js");
});

test("a console record names its caller's script and position, never its arguments", () => {
  const stack = [
    "Error",
    "    at console.error (http://127.0.0.1:1430/assets/index-Q1.js:4:10)",
    "    at Progress (http://127.0.0.1:1430/assets/palette-Ab.js:12:345)",
  ].join("\n");
  expect(
    consoleSummary(
      ["Warning: Failed %s type: %s%s", "prop", "private-canary"],
      stack,
    ),
  ).toEqual({
    template: "Warning: Failed %s type: …",
    module: "palette-Ab.js",
    line: 12,
    column: 345,
  });
  expect(consoleSummary([{ private: "canary" }], undefined)).toEqual({});
});

test("an uncaught error without detail still says what it was", () => {
  expect(
    errorEventSummary({ message: "", lineno: 0, colno: 0, error: null }),
  ).toEqual({
    template: "uncaught error event without message or error object",
  });
  expect(
    errorEventSummary({
      message: "Script error.",
      filename: "",
      lineno: 0,
      colno: 0,
    }),
  ).toEqual({ template: "Script error." });
  const notice = {
    message: "ResizeObserver loop completed with undelivered notifications.",
    error: null,
  };
  expect(isResizeObserverNotice(notice)).toBe(true);
  expect(errorEventSummary(notice).template).toBe(
    "ResizeObserver loop completed with undelivered notifications.",
  );
  expect(
    isResizeObserverNotice({
      message: "ResizeObserver loop",
      error: new Error(),
    }),
  ).toBe(false);
});

test("a rejected value says its kind, and a host failure its closed code", () => {
  expect(rejectionSummary({ code: "unknown", reason: "X1234567L" })).toEqual({
    template: "host failure unknown",
  });
  expect(rejectionSummary(undefined)).toEqual({
    template: "undefined thrown",
  });
  expect(rejectionSummary(null)).toEqual({ template: "null value thrown" });
  expect(rejectionSummary(new TypeError("x is not a function")).template).toBe(
    "TypeError: x is not a function",
  );
});
