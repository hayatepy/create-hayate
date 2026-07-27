from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
import uvicorn
from playwright.async_api import Page, async_playwright, expect

from app import app

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("HAYATE_ADMIN_BROWSER_TESTS") != "1",
        reason="set HAYATE_ADMIN_BROWSER_TESTS=1 after installing Chromium",
    ),
]

PORT = 8787
ORIGIN = f"http://127.0.0.1:{PORT}"


@pytest_asyncio.fixture
async def page() -> AsyncIterator[Page]:
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=PORT,
            lifespan="on",
            log_level="warning",
        )
    )
    server_task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.02)
    else:
        server.should_exit = True
        await server_task
        raise RuntimeError("generated admin browser server did not start")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            extra_http_headers={
                "Cf-Access-Authenticated-User-Email": "developer@example.com",
            }
        )
        browser_page = await context.new_page()
        try:
            yield browser_page
        finally:
            await context.close()
            await browser.close()
            server.should_exit = True
            await server_task


async def test_generated_admin_browser_crud_search_history_and_delete(page: Page) -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []
    request_failures: list[str] = []
    page.on(
        "console",
        lambda message: console_errors.append(message.text) if message.type == "error" else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "requestfailed",
        lambda request: (
            request_failures.append(f"{request.method} {request.url}: {request.failure}")
            if "/export.csv" not in request.url
            else None
        ),
    )

    await page.goto(f"{ORIGIN}/admin/todos")
    await expect(page.get_by_role("heading", name="TODOs")).to_be_visible()
    await page.get_by_role("link", name="Add TODO").click()
    await page.get_by_label("Title").fill("Browser-managed TODO")
    await page.get_by_role("button", name="Create").click()
    await expect(page.get_by_role("heading", name="Browser-managed TODO")).to_be_visible()
    await page.get_by_role("link", name="Back to TODOs").click()

    await page.get_by_role("link", name="Title A-Z").click()
    await expect(page.get_by_role("link", name="Title A-Z")).to_have_attribute(
        "aria-current",
        "page",
    )
    await page.get_by_label("Search").fill("Browser-managed")
    await page.get_by_role("button", name="Apply", exact=True).click()
    await expect(page.locator("tbody tr")).to_have_count(1)
    async with page.expect_download() as download_info:
        await page.get_by_role("link", name="Export CSV").click()
    download = await download_info.value
    assert download.suggested_filename == "todos.csv"
    download_path = await download.path()
    assert "Browser-managed TODO" in Path(download_path).read_text(encoding="utf-8")
    await page.get_by_role("link", name="Edit").click()
    await page.get_by_label("Title").fill("Browser-shipped TODO")
    await page.get_by_label("Done").check()
    await page.get_by_role("button", name="Save changes").click()
    await expect(page.get_by_role("heading", name="Browser-shipped TODO")).to_be_visible()

    await page.get_by_role("link", name="History").click()
    await expect(page.get_by_text("submitted values are not recorded")).to_be_visible()
    await expect(page.get_by_text("Browser-shipped TODO")).to_have_count(0)
    await page.get_by_role("link", name="Back to record").click()
    await page.get_by_role("link", name="Delete").click()
    await page.get_by_role("button", name="Confirm delete").click()
    await expect(page.get_by_role("heading", name="TODOs")).to_be_visible()
    await expect(page.get_by_text("Browser-shipped TODO")).to_have_count(0)

    assert console_errors == []
    assert page_errors == []
    assert request_failures == []
