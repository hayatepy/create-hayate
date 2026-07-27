from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import uvicorn
from playwright.async_api import Page, async_playwright

from app import app

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("HAYATE_HTMX_BROWSER_TESTS") != "1",
        reason="set HAYATE_HTMX_BROWSER_TESTS=1 after installing Chromium",
    ),
]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest_asyncio.fixture
async def live_url() -> AsyncIterator[str]:
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            log_level="warning",
        )
    )
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.02)
    else:
        server.should_exit = True
        await task
        raise RuntimeError("test server did not start")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


async def _assert_htmx_ready(page: Page) -> None:
    await page.wait_for_function("window.htmx && window.htmx.version")
    assert await page.evaluate("window.htmx.version") == "2.0.10"


@pytest.mark.asyncio
async def test_navigation_crud_validation_history_and_stream(live_url: str):
    console_errors: list[str] = []
    page_errors: list[str] = []
    request_failures: list[str] = []
    request_urls: list[str] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: request_failures.append(
                f"{request.method} {request.url}: {request.failure}"
            ),
        )
        page.on("request", lambda request: request_urls.append(request.url))

        await page.goto(f"{live_url}/app")
        await _assert_htmx_ready(page)

        form = page.locator("#todo-create")
        await form.get_by_label("Add a task").fill("   ")
        await form.get_by_role("button", name="Add").click()
        await page.get_by_role("alert").wait_for()
        assert "Enter a title" in await page.get_by_role("alert").inner_text()

        await form.get_by_label("Add a task").fill("First task")
        await form.get_by_role("button", name="Add").click()
        item = page.locator(".todo-item", has_text="First task")
        await item.wait_for()

        await item.get_by_role("button", name="Edit").click()
        editing = page.locator(".todo-item.editing")
        await editing.get_by_label("Task title").fill("Renamed task")
        await editing.get_by_role("button", name="Save").click()
        await page.get_by_text("Renamed task").wait_for()

        await page.get_by_role("link", name="Completed").click()
        await page.wait_for_url(f"{live_url}/app?filter=done")
        assert await page.locator("#todo-list").get_attribute("data-filter") == "done"
        await page.go_back()
        await page.wait_for_url(f"{live_url}/app")
        await page.get_by_text("Renamed task").wait_for()

        await page.get_by_role("button", name="Run stream").click()
        output = page.locator("#stream-output")
        await output.get_by_text(
            "Hayate keeps the stream safe and same-origin.",
            exact=True,
        ).wait_for()

        item = page.locator(".todo-item", has_text="Renamed task")
        await item.get_by_role("button", name="Delete").click()
        await item.wait_for(state="detached")

        assert console_errors == []
        assert page_errors == []
        # Chromium reports a client-initiated EventSource.close() as
        # net::ERR_ABORTED on some versions. The completed output above proves
        # the terminal event arrived; permit only that one deliberate close.
        stream_abort = f"GET {live_url}/app/stream: net::ERR_ABORTED"
        assert request_failures in ([], [stream_abort])
        assert all(url.startswith(live_url) or url.startswith("data:") for url in request_urls)
        assert any(url.endswith("/assets/vendor/htmx-2.0.10.min.js") for url in request_urls)

        await context.close()
        await browser.close()
