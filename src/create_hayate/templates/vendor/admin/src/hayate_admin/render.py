"""Safely escaped progressive HTML and htmx fragments."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from html import escape
from urllib.parse import quote, urlencode

from hayate import Context, Response
from hayate_htmx import HtmxRequest, append_htmx_vary, select_render_mode

from .contracts import (
    Actor,
    AdminAsset,
    AdminBulkAction,
    AdminField,
    AdminInline,
    AdminRelationship,
    AdminResource,
    AuditHistoryPage,
    BulkActionResult,
    InlineCollection,
    InlineOperation,
    ListQuery,
    Page,
    Record,
    RelationshipChoice,
    RelationshipPage,
)


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _display(value: object | None) -> str:
    if value is None or value == "":
        return '<span aria-label="empty">—</span>'
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return _e(value)


def _record_value(record: Record, field: str) -> object | None:
    return record.get(field)


def _record_id(resource: AdminResource, record: Record) -> str:
    value = _record_value(record, resource.id_field)
    if value is None:
        raise ValueError(f"{resource.slug}: repository record has no {resource.id_field!r}")
    return str(value)


def _record_title(resource: AdminResource, record: Record) -> str:
    value = _record_value(record, resource.title_field)
    return _record_id(resource, record) if value is None else str(value)


def _path(prefix: str, resource: AdminResource | None = None, *parts: str) -> str:
    segments = [prefix.rstrip("/")]
    if resource is not None:
        segments.append(resource.slug)
    segments.extend(quote(part, safe="") for part in parts)
    return "/".join(segments)


def _link(label: object, href: str, *, current: bool = False) -> str:
    marker = ' aria-current="page"' if current else ""
    return (
        f'<a href="{_e(href)}" hx-get="{_e(href)}" hx-target="#hayate-admin" '
        f'hx-select="#hayate-admin" hx-swap="outerHTML" hx-push-url="true"{marker}>'
        f"{_e(label)}</a>"
    )


class AdminRenderer:
    """Pure-Python renderer with no raw record interpolation."""

    __slots__ = ("asset", "prefix", "title")

    def __init__(self, *, prefix: str, title: str, asset: AdminAsset | None) -> None:
        self.prefix = prefix
        self.title = title
        self.asset = asset

    def response(
        self,
        context: Context,
        *,
        title: str,
        actor: Actor,
        content: str,
        status: int = 200,
    ) -> Response:
        main = (
            '<main id="hayate-admin" tabindex="-1">'
            f'<nav aria-label="Breadcrumb">{_link(self.title, self.prefix)}</nav>'
            f"{content}</main>"
        )
        script_policy = "'none'" if self.asset is None else "'self'"
        if select_render_mode(HtmxRequest.from_context(context)) == "fragment":
            html = main
        else:
            script = ""
            if self.asset is not None:
                script = (
                    f'<script src="{_e(self.asset.url)}" integrity="{_e(self.asset.integrity)}" '
                    'crossorigin="anonymous" defer></script>'
                )
            html = (
                "<!doctype html>"
                '<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                f"<title>{_e(title)} · {_e(self.title)}</title>{script}</head>"
                '<body hx-boost="true" hx-target="#hayate-admin" '
                'hx-select="#hayate-admin" hx-swap="outerHTML">'
                f"<header><strong>{_e(self.title)}</strong>"
                f'<span aria-label="Signed in administrator"> — {_e(actor.display)}</span></header>'
                f"{main}</body></html>"
            )
        headers = {
            "cache-control": "no-store",
            "content-security-policy": (
                "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                f"script-src {script_policy}; connect-src 'self'; form-action 'self'"
            ),
            "referrer-policy": "same-origin",
            "x-content-type-options": "nosniff",
        }
        return append_htmx_vary(context.html(html, status, headers))

    def index(self, resources: Sequence[AdminResource]) -> str:
        if not resources:
            listing = "<p>No resources are available to this administrator.</p>"
        else:
            items = "".join(
                f"<li>{_link(resource.label, _path(self.prefix, resource))}</li>"
                for resource in resources
            )
            listing = f'<ul aria-label="Resources">{items}</ul>'
        return f"<h1>{_e(self.title)}</h1>{listing}"

    def listing(
        self,
        resource: AdminResource,
        page: Page,
        query: ListQuery,
        *,
        can_add: bool,
        can_change: bool,
        can_delete: bool,
        bulk_actions: Sequence[AdminBulkAction],
    ) -> str:
        list_fields = tuple(field for field in resource.fields if field.list_display)
        controls = self._list_controls(resource, query)
        create = ""
        if can_add:
            create_path = _path(self.prefix, resource, "create")
            create = f"<p>{_link(f'Add {resource.singular_label}', create_path)}</p>"

        if not page.items:
            table = "<p>No matching records.</p>"
        else:
            headings = "".join(
                f'<th scope="col">{self._sort_heading(resource, field, query)}</th>'
                for field in list_fields
            )
            if bulk_actions:
                headings = '<th scope="col">Select</th>' + headings
            headings += '<th scope="col">Actions</th>'
            rows = "".join(
                self._list_row(
                    resource,
                    record,
                    list_fields,
                    can_change=can_change,
                    can_delete=can_delete,
                    selectable=bool(bulk_actions),
                )
                for record in page.items
            )
            table = (
                f"<table><caption>{_e(resource.label)}</caption><thead><tr>{headings}</tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )
            if bulk_actions:
                bulk_path = _path(self.prefix, resource, "bulk")
                options = "".join(
                    f'<option value="{_e(action.slug)}">{_e(action.label)}</option>'
                    for action in bulk_actions
                )
                table = (
                    f'<form method="post" action="{_e(bulk_path)}" '
                    f'hx-post="{_e(bulk_path)}" hx-target="#hayate-admin" '
                    'hx-select="#hayate-admin" hx-swap="outerHTML">'
                    "<fieldset><legend>Bulk action</legend>"
                    '<label for="bulk-action">Action</label>'
                    '<select id="bulk-action" name="action" required>'
                    '<option value="">Choose an action</option>'
                    f"{options}</select>"
                    '<button type="submit">Apply to selected</button>'
                    f"</fieldset>{table}</form>"
                )
        pagination = self._pagination(resource, page, query)
        return (
            f"<h1>{_e(resource.label)}</h1>{create}{controls}"
            f'<p role="status">{page.total} matching record{"s" if page.total != 1 else ""}.</p>'
            f"{table}{pagination}"
        )

    def _list_controls(self, resource: AdminResource, query: ListQuery) -> str:
        action = _path(self.prefix, resource)
        search = "" if query.search is None else query.search
        filters = []
        for field in resource.fields:
            if not field.filterable:
                continue
            current = query.filters.get(field.name, "")
            options = ['<option value="">All</option>']
            options.extend(
                f'<option value="{_e(value)}"{" selected" if value == current else ""}>'
                f"{_e(label)}</option>"
                for value, label in field.choices
            )
            filters.append(
                f"<label>{_e(field.label)}"
                f'<select name="filter_{_e(field.name)}">{"".join(options)}</select></label>'
            )
        return (
            f'<form method="get" action="{_e(action)}" hx-get="{_e(action)}" '
            'hx-target="#hayate-admin" hx-select="#hayate-admin" hx-swap="outerHTML" '
            'hx-push-url="true">'
            f'<label>Search<input type="search" name="q" value="{_e(search)}" '
            'maxlength="200"></label>'
            f'{"".join(filters)}<button type="submit">Apply</button></form>'
        )

    def _sort_heading(
        self,
        resource: AdminResource,
        field: AdminField,
        query: ListQuery,
    ) -> str:
        if not field.sortable:
            return _e(field.label)
        descending = query.order_by == field.name and not query.descending
        params = self._query_params(query, page=1)
        params["sort"] = field.name
        params["direction"] = "desc" if descending else "asc"
        href = f"{_path(self.prefix, resource)}?{urlencode(params)}"
        label = field.label
        if query.order_by == field.name:
            label += " ↓" if query.descending else " ↑"
        return _link(label, href, current=query.order_by == field.name)

    def _list_row(
        self,
        resource: AdminResource,
        record: Record,
        fields: Sequence[AdminField],
        *,
        can_change: bool,
        can_delete: bool,
        selectable: bool,
    ) -> str:
        object_id = _record_id(resource, record)
        detail = _path(self.prefix, resource, "object", object_id)
        cells = []
        if selectable:
            selection_label = f"Select {_record_title(resource, record)}"
            cells.append(
                '<td><input type="checkbox" name="selected" '
                f'value="{_e(object_id)}" aria-label="{_e(selection_label)}">'
                "</td>"
            )
        for index, field in enumerate(fields):
            value = _record_value(record, field.name)
            displayed = _display(value)
            if index == 0:
                displayed = _link(value if value is not None else object_id, detail)
            cells.append(f"<td>{displayed}</td>")
        actions = [_link("View", detail)]
        if can_change:
            actions.append(_link("Edit", f"{detail}/edit"))
        if can_delete:
            actions.append(_link("Delete", f"{detail}/delete"))
        return (
            f'<tr data-object-id="{_e(object_id)}">{"".join(cells)}'
            f"<td>{' · '.join(actions)}</td></tr>"
        )

    def bulk_error(self, resource: AdminResource, message: str) -> str:
        back = _link(f"Return to {resource.label}", _path(self.prefix, resource))
        return (
            '<section role="alert" aria-labelledby="bulk-action-error">'
            '<h1 id="bulk-action-error">Bulk action rejected</h1>'
            f"<p>{_e(message)}</p></section><p>{back}</p>"
        )

    def bulk_result(
        self,
        resource: AdminResource,
        action: AdminBulkAction,
        result: BulkActionResult,
    ) -> str:
        succeeded = len(result.succeeded)
        failed = len(result.failed)
        failures = ""
        if result.failed:
            items = "".join(
                f"<li>{_e(object_id)}: {_e(message)}</li>"
                for object_id, message in result.failed.items()
            )
            failures = (
                '<section aria-labelledby="bulk-action-failures">'
                '<h2 id="bulk-action-failures">Not completed</h2>'
                f"<ul>{items}</ul></section>"
            )
        back = _link(f"Return to {resource.label}", _path(self.prefix, resource))
        return (
            f"<h1>{_e(action.label)}</h1>"
            f'<p role="status">{succeeded} completed; {failed} failed.</p>'
            f"{failures}<p>{back}</p>"
        )

    def _pagination(self, resource: AdminResource, page: Page, query: ListQuery) -> str:
        page_count = max(1, math.ceil(page.total / query.limit))
        current = query.offset // query.limit + 1
        links = []
        if current > 1:
            params = self._query_params(query, page=current - 1)
            links.append(_link("Previous", f"{_path(self.prefix, resource)}?{urlencode(params)}"))
        links.append(f"<span>Page {current} of {page_count}</span>")
        if current < page_count:
            params = self._query_params(query, page=current + 1)
            links.append(_link("Next", f"{_path(self.prefix, resource)}?{urlencode(params)}"))
        return f'<nav aria-label="Pagination">{" · ".join(links)}</nav>'

    @staticmethod
    def _query_params(query: ListQuery, *, page: int) -> dict[str, str]:
        params = {"page": str(page)}
        if query.search:
            params["q"] = query.search
        if query.order_by:
            params["sort"] = query.order_by
            params["direction"] = "desc" if query.descending else "asc"
        params.update({f"filter_{name}": value for name, value in query.filters.items()})
        return params

    def detail(
        self,
        resource: AdminResource,
        record: Record,
        *,
        can_change: bool,
        can_delete: bool,
        can_history: bool,
        inlines: Sequence[AdminInline],
    ) -> str:
        object_id = _record_id(resource, record)
        relationship_map = resource.relationship_map
        display_fields = {relationship.display_field for relationship in resource.relationships}
        entries = []
        for field in resource.fields:
            if field.name in display_fields:
                continue
            relationship = relationship_map.get(field.name)
            value = _record_value(record, field.name)
            if relationship is None or value is None:
                displayed = _display(value)
            else:
                label = _record_value(record, relationship.display_field)
                target = (
                    f"{self.prefix}/{relationship.target_resource}/object/"
                    f"{quote(str(value), safe='')}"
                )
                displayed = _link(label if label is not None else value, target)
            entries.append(f"<dt>{_e(field.label)}</dt><dd>{displayed}</dd>")
        actions = [_link(f"Back to {resource.label}", _path(self.prefix, resource))]
        base = _path(self.prefix, resource, "object", object_id)
        if can_change:
            actions.append(_link("Edit", f"{base}/edit"))
        if can_delete:
            actions.append(_link("Delete", f"{base}/delete"))
        if can_history:
            actions.append(_link("History", f"{base}/history"))
        inline_links = ""
        if inlines:
            links = "".join(
                f"<li>{_link(inline.label, f'{base}/inline/{inline.slug}')}</li>"
                for inline in inlines
            )
            inline_links = f"<h2>Related records</h2><ul>{links}</ul>"
        return (
            f"<h1>{_e(_record_title(resource, record))}</h1>"
            f"<dl>{''.join(entries)}</dl>{inline_links}<p>{' · '.join(actions)}</p>"
        )

    def history(
        self,
        resource: AdminResource,
        object_id: str,
        page: AuditHistoryPage,
        *,
        page_number: int,
        limit: int,
    ) -> str:
        detail = _path(self.prefix, resource, "object", object_id)
        if not page.items:
            table = '<p role="status">No history events are available.</p>'
        else:
            rows = []
            for event in page.items:
                action: str = event.action
                if event.operation is not None:
                    action = f"{action} / {event.operation}"
                result: str = event.phase
                if event.error_type is not None:
                    result = f"{result} ({event.error_type})"
                timestamp = event.occurred_at.isoformat()
                rows.append(
                    "<tr>"
                    f'<td><time datetime="{_e(timestamp)}">{_e(timestamp)}</time></td>'
                    f"<td>{_e(action)}</td>"
                    f"<td>{_display(event.actor_id)}</td>"
                    f"<td>{_e(result)}</td>"
                    "</tr>"
                )
            table = (
                "<table><caption>Redacted audit history</caption>"
                '<thead><tr><th scope="col">Time</th><th scope="col">Action</th>'
                '<th scope="col">Actor</th><th scope="col">Result</th></tr></thead>'
                f"<tbody>{''.join(rows)}</tbody></table>"
            )
        page_count = max(1, math.ceil(page.total / limit))
        links = []
        base = f"{detail}/history"
        if page_number > 1:
            links.append(_link("Previous", f"{base}?{urlencode({'page': page_number - 1})}"))
        links.append(f"<span>Page {page_number} of {page_count}</span>")
        if page_number < page_count:
            links.append(_link("Next", f"{base}?{urlencode({'page': page_number + 1})}"))
        pagination = f'<nav aria-label="History pagination">{" · ".join(links)}</nav>'
        return (
            f"<h1>History for {_e(object_id)}</h1>"
            "<p>Events contain metadata only; submitted values are not recorded.</p>"
            f"{table}{pagination}<p>{_link('Back to record', detail)}</p>"
        )

    def relationship_choices(
        self,
        resource: AdminResource,
        relationship: AdminRelationship,
        page: RelationshipPage,
        *,
        search: str | None,
        page_number: int,
        source_object_id: str | None,
    ) -> str:
        field = resource.field_map[relationship.field]
        action = _path(
            self.prefix,
            resource,
            "relationship",
            relationship.field,
            "choices",
        )
        hidden = (
            ""
            if source_object_id is None
            else f'<input type="hidden" name="object_id" value="{_e(source_object_id)}">'
        )
        search_form = (
            f'<form method="get" action="{_e(action)}" hx-get="{_e(action)}" '
            'hx-target="#hayate-admin" hx-select="#hayate-admin" hx-swap="outerHTML" '
            'hx-push-url="true">'
            f"{hidden}<label>Search {field.label}"
            f'<input type="search" name="q" value="{_e(search or "")}" '
            'maxlength="200"></label><button type="submit">Search</button></form>'
        )
        destination = (
            _path(self.prefix, resource, "create")
            if source_object_id is None
            else _path(self.prefix, resource, "object", source_object_id, "edit")
        )
        if not page.items:
            results = '<p role="status">No authorized related records found.</p>'
        else:
            items = []
            for choice in page.items:
                href = f"{destination}?{urlencode({f'relation_{relationship.field}': choice.id})}"
                items.append(f"<li>{_e(choice.label)} — {_link('Choose', href)}</li>")
            results = (
                f'<p role="status">{page.total} matching authorized '
                f"record{'s' if page.total != 1 else ''}.</p>"
                f'<ul aria-label="{_e(field.label)} choices">{"".join(items)}</ul>'
            )
        page_count = max(1, math.ceil(page.total / relationship.max_choices))
        links = []
        base_params = {}
        if search:
            base_params["q"] = search
        if source_object_id is not None:
            base_params["object_id"] = source_object_id
        if page_number > 1:
            links.append(
                _link(
                    "Previous",
                    f"{action}?{urlencode(base_params | {'page': page_number - 1})}",
                )
            )
        links.append(f"<span>Page {page_number} of {page_count}</span>")
        if page_number < page_count:
            links.append(
                _link(
                    "Next",
                    f"{action}?{urlencode(base_params | {'page': page_number + 1})}",
                )
            )
        pagination = f'<nav aria-label="Relationship pagination">{" · ".join(links)}</nav>'
        return (
            f"<h1>Choose {_e(field.label)}</h1>{search_form}{results}{pagination}"
            f"<p>{_link('Return without choosing', destination)}</p>"
        )

    def form(
        self,
        resource: AdminResource,
        *,
        action: str,
        heading: str,
        values: Mapping[str, object],
        errors: Mapping[str, str],
        submit_label: str,
        relationship_choices: Mapping[str, Sequence[RelationshipChoice]],
        source_object_id: str | None,
    ) -> str:
        summary = ""
        if errors:
            items = "".join(f"<li>{_e(message)}</li>" for message in errors.values())
            summary = (
                '<section role="alert" aria-labelledby="admin-form-errors">'
                '<h2 id="admin-form-errors">Correct the following errors</h2>'
                f"<ul>{items}</ul></section>"
            )
        display_fields = {relationship.display_field for relationship in resource.relationships}
        controls = []
        for field in resource.fields:
            if field.name in display_fields:
                continue
            relationship = resource.relationship_map.get(field.name)
            if relationship is None:
                controls.append(
                    self._field_control(
                        field,
                        values.get(field.name),
                        errors.get(field.name),
                    )
                )
            else:
                controls.append(
                    self._relationship_control(
                        resource,
                        field,
                        relationship,
                        values.get(field.name),
                        errors.get(field.name),
                        relationship_choices.get(field.name, ()),
                        source_object_id=source_object_id,
                    )
                )
        cancel = _link(f"Cancel and return to {resource.label}", _path(self.prefix, resource))
        return (
            f"<h1>{_e(heading)}</h1>{summary}"
            f'<form method="post" action="{_e(action)}" hx-post="{_e(action)}" '
            'hx-target="#hayate-admin" hx-select="#hayate-admin" hx-swap="outerHTML">'
            f'{"".join(controls)}<button type="submit">{_e(submit_label)}</button></form>'
            f"<p>{cancel}</p>"
        )

    def _relationship_control(
        self,
        resource: AdminResource,
        field: AdminField,
        relationship: AdminRelationship,
        value: object | None,
        error: str | None,
        choices: Sequence[RelationshipChoice],
        *,
        source_object_id: str | None,
    ) -> str:
        field_id = f"field-{field.name}"
        required = " required" if field.required else ""
        invalid = ' aria-invalid="true"' if error is not None else ""
        described = f' aria-describedby="{_e(field_id)}-error"' if error is not None else ""
        raw = "" if value is None else str(value)
        options = []
        if not field.required:
            options.append('<option value="">—</option>')
        options.extend(
            f'<option value="{_e(choice.id)}"{" selected" if choice.id == raw else ""}>'
            f"{_e(choice.label)}</option>"
            for choice in choices
        )
        chooser = _path(
            self.prefix,
            resource,
            "relationship",
            relationship.field,
            "choices",
        )
        if source_object_id is not None:
            chooser = f"{chooser}?{urlencode({'object_id': source_object_id})}"
        message = (
            f'<p id="{_e(field_id)}-error" role="alert">{_e(error)}</p>'
            if error is not None
            else ""
        )
        return (
            f'<div><label for="{_e(field_id)}">{_e(field.label)}</label>'
            f'<select id="{_e(field_id)}" name="{_e(field.name)}"'
            f"{required}{invalid}{described}>{''.join(options)}</select>"
            f"<span> {_link(f'Search {field.label}', chooser)}</span>{message}</div>"
        )

    def _field_control(
        self,
        field: AdminField,
        value: object | None,
        error: str | None,
        *,
        control_name: str | None = None,
        control_id: str | None = None,
    ) -> str:
        field_id = control_id or f"field-{field.name}"
        field_name = control_name or field.name
        if field.read_only:
            return (
                f'<div><span id="{_e(field_id)}">{_e(field.label)}</span>'
                f'<output aria-labelledby="{_e(field_id)}">{_display(value)}</output></div>'
            )
        required = " required" if field.required else ""
        invalid = ' aria-invalid="true"' if error is not None else ""
        described = f' aria-describedby="{_e(field_id)}-error"' if error is not None else ""
        raw = "" if value is None else str(value)
        if field.kind == "textarea":
            control = (
                f'<textarea id="{_e(field_id)}" name="{_e(field_name)}" '
                f'maxlength="{field.max_length}"{required}{invalid}{described}>'
                f"{_e(raw)}</textarea>"
            )
        elif field.kind == "select":
            options = []
            if not field.required:
                options.append('<option value="">—</option>')
            options.extend(
                f'<option value="{_e(choice)}"{" selected" if choice == raw else ""}>'
                f"{_e(label)}</option>"
                for choice, label in field.choices
            )
            control = (
                f'<select id="{_e(field_id)}" name="{_e(field_name)}"'
                f"{required}{invalid}{described}>{''.join(options)}</select>"
            )
        elif field.kind == "checkbox":
            checked = " checked" if bool(value) else ""
            control = (
                f'<input id="{_e(field_id)}" name="{_e(field_name)}" '
                f'type="checkbox" value="true"{checked}{invalid}{described}>'
            )
        else:
            input_type = field.kind if field.kind != "integer" else "number"
            step = ' step="any"' if field.kind == "number" else ""
            control = (
                f'<input id="{_e(field_id)}" name="{_e(field_name)}" '
                f'type="{_e(input_type)}" value="{_e(raw)}" maxlength="{field.max_length}"'
                f"{step}{required}{invalid}{described}>"
            )
        message = (
            f'<p id="{_e(field_id)}-error" role="alert">{_e(error)}</p>'
            if error is not None
            else ""
        )
        return f'<div><label for="{_e(field_id)}">{_e(field.label)}</label>{control}{message}</div>'

    def inline_editor(
        self,
        parent_resource: AdminResource,
        parent: Record,
        target_resource: AdminResource,
        inline: AdminInline,
        collection: InlineCollection,
        *,
        permissions: Mapping[str, tuple[bool, bool]],
        can_add: bool,
        errors: Mapping[str, str],
        error_object_id: str | None,
        error_values: Mapping[str, object] | None = None,
        error_operation: InlineOperation | None = None,
    ) -> str:
        parent_id = _record_id(parent_resource, parent)
        parent_detail = _path(
            self.prefix,
            parent_resource,
            "object",
            parent_id,
        )
        action = f"{parent_detail}/inline/{inline.slug}"
        sections = []
        for record in collection.items:
            object_id = _record_id(target_resource, record)
            can_change, can_delete = permissions.get(object_id, (False, False))
            row_errors = (
                errors
                if error_operation in ("update", "delete") and error_object_id == object_id
                else {}
            )
            values = error_values if row_errors and error_values is not None else record
            if not can_change and not can_delete:
                rendered = "".join(
                    f"<dt>{_e(target_resource.field_map[name].label)}</dt>"
                    f"<dd>{_display(record.get(name))}</dd>"
                    for name in inline.fields
                )
                sections.append(
                    f'<section aria-labelledby="inline-{_e(object_id)}">'
                    f'<h2 id="inline-{_e(object_id)}">{_e(object_id)}</h2>'
                    f"<dl>{rendered}</dl></section>"
                )
                continue
            controls = "".join(
                self._field_control(
                    target_resource.field_map[name],
                    values.get(name) if values is not None else None,
                    row_errors.get(name),
                    control_name=name,
                    control_id=f"inline-{object_id}-{name}",
                )
                for name in inline.fields
            )
            buttons = []
            if can_change:
                buttons.append(
                    '<button type="submit" name="operation" value="update">'
                    "Save inline record</button>"
                )
            if can_delete:
                buttons.append(
                    '<button type="submit" name="operation" value="delete" '
                    "formnovalidate>Delete inline record</button>"
                )
            sections.append(
                f'<section aria-labelledby="inline-{_e(object_id)}">'
                f'<h2 id="inline-{_e(object_id)}">{_e(object_id)}</h2>'
                f"{self._error_summary(row_errors, f'inline-{object_id}-errors')}"
                f'<form method="post" action="{_e(action)}" hx-post="{_e(action)}" '
                'hx-target="#hayate-admin" hx-select="#hayate-admin" '
                'hx-swap="outerHTML">'
                f'<input type="hidden" name="object_id" value="{_e(object_id)}">'
                f"{controls}{' '.join(buttons)}</form></section>"
            )
        add = ""
        if can_add:
            add_errors = errors if error_operation == "create" and error_object_id is None else {}
            values = error_values if add_errors and error_values is not None else {}
            controls = "".join(
                self._field_control(
                    target_resource.field_map[name],
                    values.get(name),
                    add_errors.get(name),
                    control_name=name,
                    control_id=f"inline-new-{name}",
                )
                for name in inline.fields
            )
            add = (
                '<section aria-labelledby="inline-add">'
                f'<h2 id="inline-add">Add {_e(target_resource.singular_label)}</h2>'
                f"{self._error_summary(add_errors, 'inline-new-errors')}"
                f'<form method="post" action="{_e(action)}" hx-post="{_e(action)}" '
                'hx-target="#hayate-admin" hx-select="#hayate-admin" '
                'hx-swap="outerHTML">'
                f'{controls}<button type="submit" name="operation" value="create">'
                "Add inline record</button></form></section>"
            )
        elif collection.total >= inline.max_items:
            add = (
                f'<p role="status">The {inline.max_items}-record inline limit has been reached.</p>'
            )
        general_errors = (
            errors
            if errors
            and (
                error_operation is None
                or (error_operation == "create" and not can_add)
                or (error_operation in ("update", "delete") and error_object_id not in permissions)
            )
            else {}
        )
        return (
            f"<h1>{_e(inline.label)} for {_e(_record_title(parent_resource, parent))}</h1>"
            f"{self._error_summary(general_errors, 'inline-general-errors')}"
            f'<p role="status">{collection.total} of {inline.max_items} allowed records.</p>'
            f"{''.join(sections)}{add}<p>{_link('Back to parent record', parent_detail)}</p>"
        )

    @staticmethod
    def _error_summary(errors: Mapping[str, str], identifier: str) -> str:
        if not errors:
            return ""
        items = "".join(f"<li>{_e(message)}</li>" for message in errors.values())
        return (
            f'<section role="alert" aria-labelledby="{_e(identifier)}">'
            f'<h3 id="{_e(identifier)}">Correct the following errors</h3>'
            f"<ul>{items}</ul></section>"
        )

    def delete_confirmation(self, resource: AdminResource, record: Record, *, action: str) -> str:
        object_id = _record_id(resource, record)
        cancel = _link("Cancel", _path(self.prefix, resource, "object", object_id))
        return (
            f"<h1>Delete {_e(_record_title(resource, record))}?</h1>"
            "<p>This operation cannot be undone by hayate-admin.</p>"
            f'<form method="post" action="{_e(action)}" hx-post="{_e(action)}">'
            '<button type="submit">Confirm delete</button></form>'
            f"<p>{cancel}</p>"
        )
