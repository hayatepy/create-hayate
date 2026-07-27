import { expect, test } from "@playwright/test";

test("creates, edits, persists, and deep-links through the typed API", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Decide what moves today/ })).toBeVisible();

  await page.getByLabel("New signal").fill("Connect React to Hayate");
  await page.getByRole("button", { name: "Add to desk" }).click();
  await expect(page.getByText("Connect React to Hayate")).toBeVisible();

  await page.getByRole("button", { name: "Edit" }).click();
  const edit = page.getByLabel("Edit task");
  await edit.fill("Ship the typed React profile");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Ship the typed React profile")).toBeVisible();

  await page.reload();
  await expect(page.getByText("Ship the typed React profile")).toBeVisible();

  await page.getByRole("link", { name: "System" }).click();
  await expect(page).toHaveURL(/\/about$$/);
  await page.reload();
  await expect(page.getByRole("heading", { name: /Two layers.*One contract/ })).toBeVisible();

  await page.getByRole("link", { name: /Return to the desk/ }).click();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("Ship the typed React profile")).toHaveCount(0);
});
