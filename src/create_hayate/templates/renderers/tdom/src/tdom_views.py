"""Experimental tdom views for the generated Python 3.14 application."""

from __future__ import annotations

from collections.abc import Mapping
from string.templatelib import Template
from typing import cast

from tdom import Markup

from identity import Principal
from storage import Todo


def _principal(values: Mapping[str, object]) -> Principal:
    return cast(Principal, values["principal"])


def _todo(values: Mapping[str, object]) -> Todo:
    return cast(Todo, values["todo"])


def _todos(values: Mapping[str, object]) -> list[Todo]:
    return cast(list[Todo], values["todos"])


def create_error(values: Mapping[str, object]) -> Template:
    error = str(values["error"])
    return t'<p class="form-error" role="alert">{error}</p>'


def todo_item(values: Mapping[str, object]) -> Template:
    todo = _todo(values)
    current_filter = str(values["current_filter"])
    todo_id = todo["id"]
    classes = {"todo-item": True, "is-done": todo["done"]}
    return t"""
<article id="todo-{todo_id}" class={classes}>
  <label class="check-control">
    <input
      type="checkbox"
      aria-label="Mark {todo["title"]} complete"
      checked={todo["done"]}
      hx-patch="/app/todos/{todo_id}/toggle?filter={current_filter}"
      hx-target="#todo-list"
      hx-swap="outerHTML"
    >
    <span aria-hidden="true"></span>
  </label>
  <p>{todo["title"]}</p>
  <div class="item-actions">
    <button
      class="text-button"
      type="button"
      hx-get="/app/todos/{todo_id}/edit"
      hx-target="#todo-{todo_id}"
      hx-swap="outerHTML"
    >Edit</button>
    <button
      class="text-button danger"
      type="button"
      hx-delete="/app/todos/{todo_id}?filter={current_filter}"
      hx-target="#todo-list"
      hx-swap="outerHTML"
    >Delete</button>
  </div>
</article>
"""


def todo_list(values: Mapping[str, object]) -> Template:
    current_filter = str(values["current_filter"])
    todos = _todos(values)
    heading = {
        "done": "Completed",
        "open": "Open tasks",
    }.get(current_filter, "All tasks")
    content = (
        t'<div class="todo-items">{
            [todo_item({"current_filter": current_filter, "todo": todo}) for todo in todos]
        }</div>'
        if todos
        else t'<p class="empty-state">No tasks in this view.</p>'
    )
    section_attrs = {
        "id": "todo-list",
        "class": "todo-list",
        "aria": {"live": "polite"},
        "data": {"filter": current_filter},
    }
    return t"""<section {section_attrs}>
  <header class="list-heading">
    <h2>{heading}</h2>
    <span>{len(todos)}</span>
  </header>
  {content}
</section>
"""


def edit_todo(values: Mapping[str, object]) -> Template:
    todo = _todo(values)
    error = values["error"]
    todo_id = todo["id"]
    error_content = t'<p class="form-error" role="alert">{str(error)}</p>' if error else t""
    return t"""
<article id="todo-{todo_id}" class="todo-item editing">
  <form
    hx-patch="/app/todos/{todo_id}"
    hx-target="#todo-{todo_id}"
    hx-swap="outerHTML"
  >
    <label for="edit-title-{todo_id}">Task title</label>
    <div class="input-row">
      <input
        id="edit-title-{todo_id}"
        name="title"
        value="{todo["title"]}"
        maxlength="200"
        aria-describedby="edit-error-{todo_id}"
        required
      >
      <button type="submit">Save</button>
      <button
        class="secondary"
        type="button"
        hx-get="/app?filter=all"
        hx-target="#todo-list"
        hx-swap="outerHTML"
      >Cancel</button>
    </div>
    <div id="edit-error-{todo_id}" class="error-slot" aria-live="polite">
      {error_content}
    </div>
  </form>
</article>
"""


def app_page(values: Mapping[str, object]) -> Template:
    principal = _principal(values)
    identity = principal["email"] or principal["subject"]
    todos = todo_list(values)
    doctype = Markup("<!doctype html>")
    return t"""{doctype}<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <meta
      name="htmx-config"
      content='{{"historyCacheSize":10,"includeIndicatorStyles":false}}'
    >
    <title>Tasks · $project_name</title>
    <link rel="icon" href="data:,">
    <link rel="stylesheet" href="/assets/app.css">
    <script
      src="/assets/vendor/htmx-2.0.10.min.js"
      integrity="sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"
      crossorigin="anonymous"
      defer
    ></script>
    <script src="/assets/app.js" defer></script>
  </head>
  <body>
    <header class="topbar">
      <a class="wordmark" href="/app">$project_name</a>
      <nav aria-label="Application">
        <a href="/api/health">API</a>
        <a href="/auth">{identity}</a>
      </nav>
    </header>

    <main class="layout">
      <section class="workspace" aria-labelledby="page-title">
        <header class="workspace-heading">
          <div>
            <p class="kicker">Server-owned workspace</p>
            <h1 id="page-title">Tasks</h1>
          </div>
          <span class="route-label">/app</span>
        </header>

        <form
          id="todo-create"
          class="create-form"
          hx-post="/app/todos"
          hx-target="#todo-list"
          hx-swap="outerHTML"
        >
          <label for="new-todo">Add a task</label>
          <div class="input-row">
            <input
              id="new-todo"
              name="title"
              maxlength="200"
              aria-describedby="todo-form-errors"
              autocomplete="off"
              placeholder="What needs attention?"
              required
            >
            <button type="submit">Add</button>
          </div>
          <div id="todo-form-errors" class="error-slot" aria-live="polite"></div>
        </form>

        <nav class="filters" aria-label="Task filters">
          <a
            href="/app?filter=all"
            hx-get="/app?filter=all"
            hx-target="#todo-list"
            hx-swap="outerHTML"
            hx-push-url="true"
          >All</a>
          <a
            href="/app?filter=open"
            hx-get="/app?filter=open"
            hx-target="#todo-list"
            hx-swap="outerHTML"
            hx-push-url="true"
          >Open</a>
          <a
            href="/app?filter=done"
            hx-get="/app?filter=done"
            hx-target="#todo-list"
            hx-swap="outerHTML"
            hx-push-url="true"
          >Completed</a>
        </nav>

        {todos}
      </section>

      <aside class="context" aria-labelledby="stream-title">
        <p class="kicker">SSE transport</p>
        <h2 id="stream-title">Watch the response arrive.</h2>
        <p>One same-origin stream, ready for progress or model output.</p>
        <button id="stream-demo" class="secondary" type="button">Run stream</button>
        <output id="stream-output" aria-live="polite"></output>
      </aside>
    </main>
  </body>
</html>
"""


def auth_page(values: Mapping[str, object]) -> Template:
    principal = _principal(values)
    email = principal["email"] or "Not provided"
    doctype = Markup("<!doctype html>")
    return t"""{doctype}<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <title>Identity · $project_name</title>
    <link rel="icon" href="data:,">
    <link rel="stylesheet" href="/assets/app.css">
  </head>
  <body>
    <header class="topbar">
      <a class="wordmark" href="/app">$project_name</a>
      <span class="route-label">/auth</span>
    </header>
    <main class="identity-shell">
      <p class="kicker">Request identity</p>
      <h1>One identity boundary, shared by HTML and JSON.</h1>
      <dl class="identity-list">
        <div>
          <dt>Subject</dt>
          <dd>{principal["subject"]}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{email}</dd>
        </div>
        <div>
          <dt>Credential</dt>
          <dd>{principal["credential_type"]}</dd>
        </div>
      </dl>
      <a class="primary-link" href="/app">Return to tasks</a>
    </main>
  </body>
</html>
"""
