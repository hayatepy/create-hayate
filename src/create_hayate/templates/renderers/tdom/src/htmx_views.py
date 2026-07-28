"""Experimental tdom t-string components for the generated htmx application."""

from __future__ import annotations

from collections.abc import Mapping
from string.templatelib import Template
from typing import cast


def _mapping(values: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = values[name]
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a mapping")
    return cast(Mapping[str, object], value)


def _text(values: Mapping[str, object], name: str) -> str:
    value = values[name]
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _todo(values: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(values, "todo")


def _todos(values: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw = values["todos"]
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise TypeError("todos must be a list of mappings")
    return cast(list[Mapping[str, object]], raw)


def _todo_id(todo: Mapping[str, object]) -> str:
    value = todo["id"]
    if not isinstance(value, str):
        raise TypeError("todo id must be a string")
    return value


def _todo_title(todo: Mapping[str, object]) -> str:
    value = todo["title"]
    if not isinstance(value, str):
        raise TypeError("todo title must be a string")
    return value


def _todo_done(todo: Mapping[str, object]) -> bool:
    value = todo["done"]
    if not isinstance(value, bool):
        raise TypeError("todo done must be a boolean")
    return value


def auth_page(values: Mapping[str, object]) -> Template:
    principal = _mapping(values, "principal")
    subject = principal["subject"]
    email = principal["email"] or "Not provided"
    credential_type = principal["credential_type"]
    return t"""<!doctype html>
<html lang="en">
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
        <div><dt>Subject</dt><dd>{subject}</dd></div>
        <div><dt>Email</dt><dd>{email}</dd></div>
        <div><dt>Credential</dt><dd>{credential_type}</dd></div>
      </dl>
      <a class="primary-link" href="/app">Return to tasks</a>
    </main>
  </body>
</html>"""


def todo_item(values: Mapping[str, object]) -> Template:
    todo = _todo(values)
    todo_id = _todo_id(todo)
    todo_title = _todo_title(todo)
    done = _todo_done(todo)
    current_filter = _text(values, "current_filter")
    item_class = "todo-item is-done" if done else "todo-item"
    checked = {"checked": True} if done else {}
    return t"""<article id="todo-{todo_id}" class="{item_class}">
  <label class="check-control">
    <input
      type="checkbox"
      aria-label="Mark {todo_title} complete"
      hx-patch="/app/todos/{todo_id}/toggle?filter={current_filter}"
      hx-target="#todo-list"
      hx-swap="outerHTML"
      {checked}
    >
    <span aria-hidden="true"></span>
  </label>
  <p>{todo_title}</p>
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
</article>"""


def todo_list(values: Mapping[str, object]) -> Template:
    current_filter = _text(values, "current_filter")
    todos = _todos(values)
    heading = {
        "done": "Completed",
        "open": "Open tasks",
    }.get(current_filter, "All tasks")
    if todos:
        items = [todo_item({"current_filter": current_filter, "todo": todo}) for todo in todos]
        content = t"""<div class="todo-items">{items}</div>"""
    else:
        content = t"""<p class="empty-state">No tasks in this view.</p>"""
    todo_count = len(todos)
    return t"""<section
  id="todo-list"
  class="todo-list"
  aria-live="polite"
  data-filter="{current_filter}"
>
  <header class="list-heading">
    <h2>{heading}</h2>
    <span>{todo_count}</span>
  </header>
  {content}
</section>"""


def app_page(values: Mapping[str, object]) -> Template:
    principal = _mapping(values, "principal")
    identity = principal["email"] or principal["subject"]
    rendered_list = todo_list(values)
    return t"""<!doctype html>
<html lang="en">
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

        {rendered_list}
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
</html>"""


def create_error(values: Mapping[str, object]) -> Template:
    error = _text(values, "error")
    return t"""<p class="form-error" role="alert">{error}</p>"""


def edit_todo(values: Mapping[str, object]) -> Template:
    todo = _todo(values)
    todo_id = _todo_id(todo)
    todo_title = _todo_title(todo)
    error = values["error"]
    error_content = t"""<p class="form-error" role="alert">{error}</p>""" if error else t""
    return t"""<article id="todo-{todo_id}" class="todo-item editing">
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
        value="{todo_title}"
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
</article>"""
