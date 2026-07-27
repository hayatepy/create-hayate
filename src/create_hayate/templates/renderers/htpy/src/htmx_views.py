"""Typed htpy views for the generated htmx application."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import htpy as h
from htpy import Renderable

from identity import Principal
from storage import Todo


def _principal(values: Mapping[str, object]) -> Principal:
    return cast(Principal, values["principal"])


def _todo(values: Mapping[str, object]) -> Todo:
    return cast(Todo, values["todo"])


def _todos(values: Mapping[str, object]) -> list[Todo]:
    return cast(list[Todo], values["todos"])


def create_error(values: Mapping[str, object]) -> Renderable:
    return h.p(".form-error", role="alert")[str(values["error"])]


def todo_item(values: Mapping[str, object]) -> Renderable:
    todo = _todo(values)
    current_filter = str(values["current_filter"])
    todo_id = todo["id"]
    classes = "todo-item is-done" if todo["done"] else "todo-item"
    return h.article(id=f"todo-{todo_id}", class_=classes)[
        h.label(".check-control")[
            h.input(
                {
                    "aria-label": f"Mark {todo['title']} complete",
                    "hx-patch": f"/app/todos/{todo_id}/toggle?filter={current_filter}",
                    "hx-target": "#todo-list",
                    "hx-swap": "outerHTML",
                },
                type="checkbox",
                checked=todo["done"],
            ),
            h.span(aria_hidden="true"),
        ],
        h.p[todo["title"]],
        h.div(".item-actions")[
            h.button(
                ".text-button",
                {
                    "hx-get": f"/app/todos/{todo_id}/edit",
                    "hx-target": f"#todo-{todo_id}",
                    "hx-swap": "outerHTML",
                },
                type="button",
            )["Edit"],
            h.button(
                ".text-button.danger",
                {
                    "hx-delete": f"/app/todos/{todo_id}?filter={current_filter}",
                    "hx-target": "#todo-list",
                    "hx-swap": "outerHTML",
                },
                type="button",
            )["Delete"],
        ],
    ]


def todo_list(values: Mapping[str, object]) -> Renderable:
    current_filter = str(values["current_filter"])
    todos = _todos(values)
    heading = {
        "done": "Completed",
        "open": "Open tasks",
    }.get(current_filter, "All tasks")
    content: Renderable = (
        h.div(".todo-items")[
            [todo_item({"current_filter": current_filter, "todo": todo}) for todo in todos]
        ]
        if todos
        else h.p(".empty-state")["No tasks in this view."]
    )
    return h.section(
        "#todo-list.todo-list",
        aria_live="polite",
        data_filter=current_filter,
    )[
        h.header(".list-heading")[h.h2[heading], h.span[str(len(todos))]],
        content,
    ]


def edit_todo(values: Mapping[str, object]) -> Renderable:
    todo = _todo(values)
    error = values["error"]
    todo_id = todo["id"]
    return h.article(f"#todo-{todo_id}.todo-item.editing")[
        h.form(
            {
                "hx-patch": f"/app/todos/{todo_id}",
                "hx-target": f"#todo-{todo_id}",
                "hx-swap": "outerHTML",
            }
        )[
            h.label(for_=f"edit-title-{todo_id}")["Task title"],
            h.div(".input-row")[
                h.input(
                    id=f"edit-title-{todo_id}",
                    name="title",
                    value=todo["title"],
                    maxlength="200",
                    aria_describedby=f"edit-error-{todo_id}",
                    required=True,
                ),
                h.button(type="submit")["Save"],
                h.button(
                    ".secondary",
                    {
                        "hx-get": "/app?filter=all",
                        "hx-target": "#todo-list",
                        "hx-swap": "outerHTML",
                    },
                    type="button",
                )["Cancel"],
            ],
            h.div(
                f"#edit-error-{todo_id}.error-slot",
                aria_live="polite",
            )[h.p(".form-error", role="alert")[str(error)] if error else None,],
        ],
    ]


def app_page(values: Mapping[str, object]) -> Renderable:
    principal = _principal(values)
    identity = principal["email"] or principal["subject"]
    return h.html(lang="en")[
        h.head[
            h.meta(charset="utf-8"),
            h.meta(name="viewport", content="width=device-width, initial-scale=1"),
            h.meta(name="color-scheme", content="light"),
            h.meta(
                name="htmx-config",
                content='{"historyCacheSize":10,"includeIndicatorStyles":false}',
            ),
            h.title["Tasks · $project_name"],
            h.link(rel="icon", href="data:,"),
            h.link(rel="stylesheet", href="/assets/app.css"),
            h.script(
                src="/assets/vendor/htmx-2.0.10.min.js",
                integrity=(
                    "sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"
                ),
                crossorigin="anonymous",
                defer=True,
            ),
            h.script(src="/assets/app.js", defer=True),
        ],
        h.body[
            h.header(".topbar")[
                h.a(".wordmark", href="/app")["$project_name"],
                h.nav(aria_label="Application")[
                    h.a(href="/api/health")["API"],
                    h.a(href="/auth")[identity],
                ],
            ],
            h.main(".layout")[
                h.section(".workspace", aria_labelledby="page-title")[
                    h.header(".workspace-heading")[
                        h.div[
                            h.p(".kicker")["Server-owned workspace"],
                            h.h1("#page-title")["Tasks"],
                        ],
                        h.span(".route-label")["/app"],
                    ],
                    h.form(
                        "#todo-create.create-form",
                        {
                            "hx-post": "/app/todos",
                            "hx-target": "#todo-list",
                            "hx-swap": "outerHTML",
                        },
                    )[
                        h.label(for_="new-todo")["Add a task"],
                        h.div(".input-row")[
                            h.input(
                                id="new-todo",
                                name="title",
                                maxlength="200",
                                aria_describedby="todo-form-errors",
                                autocomplete="off",
                                placeholder="What needs attention?",
                                required=True,
                            ),
                            h.button(type="submit")["Add"],
                        ],
                        h.div(
                            "#todo-form-errors.error-slot",
                            aria_live="polite",
                        ),
                    ],
                    h.nav(".filters", aria_label="Task filters")[
                        h.a(
                            {
                                "hx-get": "/app?filter=all",
                                "hx-target": "#todo-list",
                                "hx-swap": "outerHTML",
                                "hx-push-url": "true",
                            },
                            href="/app?filter=all",
                        )["All"],
                        h.a(
                            {
                                "hx-get": "/app?filter=open",
                                "hx-target": "#todo-list",
                                "hx-swap": "outerHTML",
                                "hx-push-url": "true",
                            },
                            href="/app?filter=open",
                        )["Open"],
                        h.a(
                            {
                                "hx-get": "/app?filter=done",
                                "hx-target": "#todo-list",
                                "hx-swap": "outerHTML",
                                "hx-push-url": "true",
                            },
                            href="/app?filter=done",
                        )["Completed"],
                    ],
                    todo_list(values),
                ],
                h.aside(".context", aria_labelledby="stream-title")[
                    h.p(".kicker")["SSE transport"],
                    h.h2("#stream-title")["Watch the response arrive."],
                    h.p["One same-origin stream, ready for progress or model output."],
                    h.button("#stream-demo.secondary", type="button")["Run stream"],
                    h.output("#stream-output", aria_live="polite"),
                ],
            ],
        ],
    ]


def auth_page(values: Mapping[str, object]) -> Renderable:
    principal = _principal(values)
    return h.html(lang="en")[
        h.head[
            h.meta(charset="utf-8"),
            h.meta(name="viewport", content="width=device-width, initial-scale=1"),
            h.meta(name="color-scheme", content="light"),
            h.title["Identity · $project_name"],
            h.link(rel="icon", href="data:,"),
            h.link(rel="stylesheet", href="/assets/app.css"),
        ],
        h.body[
            h.header(".topbar")[
                h.a(".wordmark", href="/app")["$project_name"],
                h.span(".route-label")["/auth"],
            ],
            h.main(".identity-shell")[
                h.p(".kicker")["Request identity"],
                h.h1["One identity boundary, shared by HTML and JSON."],
                h.dl(".identity-list")[
                    h.div[h.dt["Subject"], h.dd[principal["subject"]]],
                    h.div[
                        h.dt["Email"],
                        h.dd[principal["email"] or "Not provided"],
                    ],
                    h.div[
                        h.dt["Credential"],
                        h.dd[principal["credential_type"]],
                    ],
                ],
                h.a(".primary-link", href="/app")["Return to tasks"],
            ],
        ],
    ]
