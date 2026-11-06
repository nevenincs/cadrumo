import { type Page } from "@playwright/test";
import { label } from "./strings";

export const calendarButton = (target: Page, locale = "en") =>
  target
    .getByRole("navigation", { name: label("desktop.rail.label", {}, locale) })
    .getByRole("button", { name: label("desktop.calendar.title", {}, locale) });

export const messagesButton = (target: Page) =>
  target
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.rail.messages") });
