"""Typed htpy components for the generated htmx application."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import htpy as h


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


def _document_head(title: str, *, htmx: bool = False) -> h.Renderable:
    children: list[h.Renderable] = [
        h.meta(charset="utf-8"),
        h.meta(name="viewport", content="width=device-width, initial-scale=1"),
        h.meta(name="color-scheme", content="light"),
    ]
    if htmx:
        children.append(
            h.meta(
                name="htmx-config",
                content='{"historyCacheSize":10,"includeIndicatorStyles":false}',
            )
        )
    children.extend(
        [
            h.title[title],
            h.link(rel="icon", href="data:,"),
            h.link(rel="stylesheet", href="/assets/app.css"),
        ]
    )
    if htmx:
        children.extend(
            [
                h.script(
                    src="/assets/vendor/htmx-2.0.10.min.js",
                    integrity=(
                        "sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"
                    ),
                    crossorigin="anonymous",
                    defer=True,
                ),
                h.script(src="/assets/app.js", defer=True),
            ]
        )
    return h.head[children]


def auth_page(values: Mapping[str, object]) -> h.Renderable:
    principal = _mapping(values, "principal")
    subject = principal["subject"]
    email = principal["email"]
    credential_type = principal["credential_type"]
    return h.html(lang="en")[
        _document_head("Identity · $project_name"),
        h.body[
            h.header(class_="topbar")[
                h.a(class_="wordmark", href="/app")["$project_name"],
                h.span(class_="route-label")["/auth"],
            ],
            h.main(class_="identity-shell")[
                h.p(class_="kicker")["Request identity"],
                h.h1["One identity boundary, shared by HTML and JSON."],
                h.dl(class_="identity-list")[
                    h.div[h.dt["Subject"], h.dd[str(subject)]],
                    h.div[h.dt["Email"], h.dd[str(email or "Not provided")]],
                    h.div[h.dt["Credential"], h.dd[str(credential_type)]],
                ],
                h.a(class_="primary-link", href="/app")["Return to tasks"],
            ],
        ],
    ]


def todo_item(values: Mapping[str, object]) -> h.Renderable:
    todo = _todo(values)
    todo_id = _todo_id(todo)
    todo_title = _todo_title(todo)
    done = _todo_done(todo)
    current_filter = _text(values, "current_filter")
    return h.article(
        id=f"todo-{todo_id}",
        class_=f"todo-item{' is-done' if done else ''}",
    )[
        h.label(class_="check-control")[
            h.input(
                type="checkbox",
                checked=done,
                **{
                    "aria-label": f"Mark {todo_title} complete",
                    "hx-patch": f"/app/todos/{todo_id}/toggle?filter={current_filter}",
                    "hx-target": "#todo-list",
                    "hx-swap": "outerHTML",
                },
            ),
            h.span(**{"aria-hidden": "true"}),
        ],
        h.p[todo_title],
        h.div(class_="item-actions")[
            h.button(
                class_="text-button",
                type="button",
                **{
                    "hx-get": f"/app/todos/{todo_id}/edit",
                    "hx-target": f"#todo-{todo_id}",
                    "hx-swap": "outerHTML",
                },
            )["Edit"],
            h.button(
                class_="text-button danger",
                type="button",
                **{
                    "hx-delete": f"/app/todos/{todo_id}?filter={current_filter}",
                    "hx-target": "#todo-list",
                    "hx-swap": "outerHTML",
                },
            )["Delete"],
        ],
    ]


def todo_list(values: Mapping[str, object]) -> h.Renderable:
    current_filter = _text(values, "current_filter")
    todos = _todos(values)
    heading = {
        "done": "Completed",
        "open": "Open tasks",
    }.get(current_filter, "All tasks")
    content: h.Renderable
    if todos:
        content = h.div(class_="todo-items")[
            (todo_item({"current_filter": current_filter, "todo": todo}) for todo in todos)
        ]
    else:
        content = h.p(class_="empty-state")["No tasks in this view."]
    return h.section(
        id="todo-list",
        class_="todo-list",
        **{"aria-live": "polite", "data-filter": current_filter},
    )[
        h.header(class_="list-heading")[h.h2[heading], h.span[str(len(todos))]],
        content,
    ]


def app_page(values: Mapping[str, object]) -> h.Renderable:
    principal = _mapping(values, "principal")
    identity = principal["email"] or principal["subject"]
    return h.html(lang="en")[
        _document_head("Tasks · $project_name", htmx=True),
        h.body[
            h.header(class_="topbar")[
                h.a(class_="wordmark", href="/app")["$project_name"],
                h.nav(**{"aria-label": "Application"})[
                    h.a(href="/api/health")["API"],
                    h.a(href="/auth")[str(identity)],
                ],
            ],
            h.main(class_="layout")[
                h.section(class_="workspace", **{"aria-labelledby": "page-title"})[
                    h.header(class_="workspace-heading")[
                        h.div[
                            h.p(class_="kicker")["Server-owned workspace"],
                            h.h1(id="page-title")["Tasks"],
                        ],
                        h.span(class_="route-label")["/app"],
                    ],
                    h.form(
                        id="todo-create",
                        class_="create-form",
                        **{
                            "hx-post": "/app/todos",
                            "hx-target": "#todo-list",
                            "hx-swap": "outerHTML",
                        },
                    )[
                        h.label(for_="new-todo")["Add a task"],
                        h.div(class_="input-row")[
                            h.input(
                                id="new-todo",
                                name="title",
                                maxlength="200",
                                autocomplete="off",
                                placeholder="What needs attention?",
                                required=True,
                                **{"aria-describedby": "todo-form-errors"},
                            ),
                            h.button(type="submit")["Add"],
                        ],
                        h.div(
                            id="todo-form-errors",
                            class_="error-slot",
                            **{"aria-live": "polite"},
                        ),
                    ],
                    h.nav(class_="filters", **{"aria-label": "Task filters"})[
                        h.a(
                            href="/app?filter=all",
                            **{
                                "hx-get": "/app?filter=all",
                                "hx-target": "#todo-list",
                                "hx-swap": "outerHTML",
                                "hx-push-url": "true",
                            },
                        )["All"],
                        h.a(
                            href="/app?filter=open",
                            **{
                                "hx-get": "/app?filter=open",
                                "hx-target": "#todo-list",
                                "hx-swap": "outerHTML",
                                "hx-push-url": "true",
                            },
                        )["Open"],
                        h.a(
                            href="/app?filter=done",
                            **{
                                "hx-get": "/app?filter=done",
                                "hx-target": "#todo-list",
                                "hx-swap": "outerHTML",
                                "hx-push-url": "true",
                            },
                        )["Completed"],
                    ],
                    todo_list(values),
                ],
                h.aside(class_="context", **{"aria-labelledby": "stream-title"})[
                    h.p(class_="kicker")["SSE transport"],
                    h.h2(id="stream-title")["Watch the response arrive."],
                    h.p["One same-origin stream, ready for progress or model output."],
                    h.button(id="stream-demo", class_="secondary", type="button")["Run stream"],
                    h.output(id="stream-output", **{"aria-live": "polite"}),
                ],
            ],
        ],
    ]


def create_error(values: Mapping[str, object]) -> h.Renderable:
    return h.p(class_="form-error", role="alert")[_text(values, "error")]


def edit_todo(values: Mapping[str, object]) -> h.Renderable:
    todo = _todo(values)
    todo_id = _todo_id(todo)
    error = values["error"]
    error_content = h.p(class_="form-error", role="alert")[str(error)] if error else None
    return h.article(id=f"todo-{todo_id}", class_="todo-item editing")[
        h.form(
            **{
                "hx-patch": f"/app/todos/{todo_id}",
                "hx-target": f"#todo-{todo_id}",
                "hx-swap": "outerHTML",
            }
        )[
            h.label(for_=f"edit-title-{todo_id}")["Task title"],
            h.div(class_="input-row")[
                h.input(
                    id=f"edit-title-{todo_id}",
                    name="title",
                    value=_todo_title(todo),
                    maxlength="200",
                    required=True,
                    **{"aria-describedby": f"edit-error-{todo_id}"},
                ),
                h.button(type="submit")["Save"],
                h.button(
                    class_="secondary",
                    type="button",
                    **{
                        "hx-get": "/app?filter=all",
                        "hx-target": "#todo-list",
                        "hx-swap": "outerHTML",
                    },
                )["Cancel"],
            ],
            h.div(
                id=f"edit-error-{todo_id}",
                class_="error-slot",
                **{"aria-live": "polite"},
            )[error_content],
        ],
    ]
