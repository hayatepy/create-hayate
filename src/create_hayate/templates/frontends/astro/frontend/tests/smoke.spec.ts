import { expect, test } from "@playwright/test";

test("keeps public pages static and loads private state in the visible island", async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Build less.*Say more/ })).toBeVisible();
  await expect(page.getByText("Notes worth publishing")).toBeVisible();

  const workspace = page.getByRole("heading", { name: "Your private margin" });
  await workspace.scrollIntoViewIfNeeded();
  await expect(page.getByText("Your private workspace is clear.")).toBeVisible();

  await page.getByLabel("A note for this identity").fill("Keep private state at runtime");
  await page.getByRole("button", { name: "Save privately" }).click();
  await expect(page.getByText("Keep private state at runtime")).toBeVisible();

  await page.reload();
  await workspace.scrollIntoViewIfNeeded();
  await expect(page.getByText("Keep private state at runtime")).toBeVisible();

  await page.getByRole("link", { name: "Principles" }).click();
  await expect(page).toHaveURL(/\/principles\/$$/);
  await expect(page.getByRole("heading", { name: /One contract.*Two moments/ })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Public is durable.")).toBeVisible();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);

  consoleErrors.length = 0;
  const missing = await page.goto("/missing/");
  expect(missing?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: /This note was never written/ })).toBeVisible();
  expect(consoleErrors).toEqual([
    "Failed to load resource: the server responded with a status of 404 (Not Found)",
  ]);
  expect(pageErrors).toEqual([]);
});
