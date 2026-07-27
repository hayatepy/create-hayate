"""Immutable, application-scoped messages for the admin user interface."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from string import Formatter
from types import MappingProxyType

_LOCALE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
_MESSAGE_KEY = re.compile(r"^[a-z][a-z0-9_.]{0,79}$")

_ENGLISH = MappingProxyType(
    {
        "accessibility.skip_to_main": "Skip to main content",
        "accessibility.breadcrumb": "Breadcrumb",
        "accessibility.signed_in": "Signed in administrator",
        "accessibility.resources": "Resources",
        "accessibility.empty": "empty",
        "value.yes": "Yes",
        "value.no": "No",
        "index.no_resources": "No resources are available to this administrator.",
        "list.add": "Add {item}",
        "list.no_matching": "No matching records.",
        "list.select": "Select",
        "list.actions": "Actions",
        "list.select_record": "Select {record}",
        "list.bulk_action": "Bulk action",
        "list.action": "Action",
        "list.choose_action": "Choose an action",
        "list.apply_selected": "Apply to selected",
        "list.cursor_status.one": "Showing {count} record on this cursor page.",
        "list.cursor_status.other": "Showing {count} records on this cursor page.",
        "list.matching.one": "{count} matching record.",
        "list.matching.other": "{count} matching records.",
        "list.all_records": "All records",
        "list.saved_views": "Saved views",
        "list.all": "All",
        "list.search": "Search",
        "list.apply": "Apply",
        "action.view": "View",
        "action.edit": "Edit",
        "action.delete": "Delete",
        "bulk.rejected": "Bulk action rejected",
        "bulk.return": "Return to {resource}",
        "bulk.not_completed": "Not completed",
        "bulk.result": "{succeeded} completed; {failed} failed.",
        "pagination.first": "First",
        "pagination.end": "End of results",
        "pagination.next": "Next",
        "pagination.previous": "Previous",
        "pagination.page": "Page {current} of {total}",
        "pagination.cursor": "Cursor pagination",
        "pagination.default": "Pagination",
        "pagination.history": "History pagination",
        "pagination.relationship": "Relationship pagination",
        "detail.back": "Back to {resource}",
        "detail.history": "History",
        "detail.related": "Related records",
        "history.empty": "No history events are available.",
        "history.caption": "Redacted audit history",
        "history.time": "Time",
        "history.action": "Action",
        "history.actor": "Actor",
        "history.result": "Result",
        "history.admin_action.site_view": "View admin site",
        "history.admin_action.resource_view": "View resource",
        "history.admin_action.resource_add": "Add record",
        "history.admin_action.resource_change": "Change record",
        "history.admin_action.resource_delete": "Delete record",
        "history.admin_action.resource_bulk": "Run bulk action",
        "history.admin_action.resource_export": "Export resource",
        "history.admin_action.resource_history": "View record history",
        "history.phase.attempt": "Attempt",
        "history.phase.success": "Success",
        "history.phase.failure": "Failure",
        "history.heading": "History for {object_id}",
        "history.privacy": "Events contain metadata only; submitted values are not recorded.",
        "history.back": "Back to record",
        "relationship.search_field": "Search {field}",
        "relationship.search": "Search",
        "relationship.empty": "No authorized related records found.",
        "relationship.matching.one": "{count} matching authorized record.",
        "relationship.matching.other": "{count} matching authorized records.",
        "relationship.choices": "{field} choices",
        "relationship.choose": "Choose",
        "relationship.heading": "Choose {field}",
        "relationship.return": "Return without choosing",
        "form.correct_errors": "Correct the following errors",
        "form.cancel": "Cancel and return to {resource}",
        "form.search_field": "Search {field}",
        "form.create_heading": "Add {item}",
        "form.create": "Create",
        "form.edit_heading": "Edit {record}",
        "form.save": "Save changes",
        "inline.save": "Save inline record",
        "inline.delete": "Delete inline record",
        "inline.add_heading": "Add {item}",
        "inline.add": "Add inline record",
        "inline.limit": "The {limit}-record inline limit has been reached.",
        "inline.heading": "{inline} for {parent}",
        "inline.count": "{count} of {limit} allowed records.",
        "inline.back": "Back to parent record",
        "delete.cancel": "Cancel",
        "delete.heading": "Delete {record}?",
        "delete.warning": "This operation cannot be undone by hayate-admin.",
        "delete.confirm": "Confirm delete",
        "problem.forbidden": "Admin operation forbidden",
        "problem.not_found": "Admin record not found",
        "problem.list_query": "Invalid admin list query",
        "problem.cursor": "Admin cursor is unsupported",
        "problem.history_page": "Invalid admin history page",
        "problem.relationship_source": "Invalid relationship source object",
        "problem.relationship_search": "Invalid relationship search",
        "problem.relationship_page": "Invalid relationship page",
        "problem.export_query": "Invalid admin export query",
        "problem.export_rows": "Admin CSV export exceeds its row limit",
        "problem.export_rows_detail": "Refine the list query below {limit} records.",
        "problem.export_bytes": "Admin CSV export exceeds its byte limit",
        "problem.export_bytes_detail": "Refine the list query below {limit} bytes.",
        "problem.form_content_type": "Admin forms require application/x-www-form-urlencoded",
        "problem.inline_form": "Admin inline form rejected",
        "problem.cross_site": "Cross-site admin mutation rejected",
        "problem.origin": "Admin mutation origin rejected",
        "problem.form": "Admin form rejected",
        "problem.bulk_form": "Admin bulk form rejected",
        "validation.max_length": "Must be at most {max_length} characters.",
        "validation.required": "This field is required.",
        "validation.integer": "Enter an integer.",
        "validation.number": "Enter a finite number.",
        "validation.date": "Enter a valid date.",
        "validation.datetime": "Enter a valid date and time.",
        "validation.value": "Enter a valid value.",
        "validation.email": "Enter a valid email address.",
        "validation.choice": "Select a valid choice.",
        "validation.form.unexpected": "The form contains an unexpected field.",
        "validation.form.duplicate": "Submit exactly one value for this field.",
        "validation.form.upload": "File uploads are not supported by this field.",
        "validation.form.relationship": "Select an authorized related record.",
        "validation.form.save": "The record could not be saved.",
        "validation.inline.unexpected": "The inline form contains an unexpected field.",
        "validation.inline.duplicate": "Submit exactly one value for each inline field.",
        "validation.inline.upload": "File uploads are not supported by inline fields.",
        "validation.inline.operation": "Choose one inline operation.",
        "validation.inline.parent": "The inline record does not belong to this parent.",
        "validation.inline.create_id": "Inline create must not include an object ID.",
        "validation.inline.limit": "At most {limit} inline records are allowed.",
        "validation.inline.save": "The inline record could not be saved.",
        "validation.bulk.upload": "File uploads are not accepted by bulk actions.",
        "validation.bulk.duplicate_action": "Submit exactly one bulk action.",
        "validation.bulk.object_ids": "Selected object IDs must be bounded printable strings.",
        "validation.bulk.unexpected": "The bulk form contains an unexpected field.",
        "validation.bulk.choose": "Choose a bulk action.",
        "validation.bulk.registered": "Choose a registered bulk action.",
        "validation.bulk.select_one": "Select at least one record.",
        "validation.bulk.limit": "Select at most {limit} records.",
        "validation.bulk.invalid": "The bulk form is invalid.",
    }
)


def _fields(template: str) -> frozenset[str]:
    names = set()
    for _, field_name, format_spec, conversion in Formatter().parse(template):
        if field_name is None:
            continue
        if (
            not field_name.isidentifier()
            or format_spec
            or conversion is not None
            or "." in field_name
            or "[" in field_name
        ):
            raise ValueError("admin message templates accept only simple named placeholders")
        names.add(field_name)
    return frozenset(names)


def _validate_text(value: str, *, name: str, maximum: int = 500) -> None:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"{name} must be 1-{maximum} characters")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{name} must not contain control characters")


@dataclass(frozen=True, slots=True)
class AdminMessages:
    """A validated locale and optional overrides over the complete English catalog."""

    locale: str = "en"
    overrides: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.locale, str) or not _LOCALE.fullmatch(self.locale):
            raise ValueError("admin locale must be a bounded well-formed language tag")
        if not isinstance(self.overrides, Mapping):
            raise ValueError("admin message overrides must be a mapping")
        copied: dict[str, str] = {}
        for key, template in self.overrides.items():
            if not isinstance(key, str) or not _MESSAGE_KEY.fullmatch(key) or key not in _ENGLISH:
                raise ValueError(f"unknown admin message key: {key!r}")
            _validate_text(template, name=f"admin message {key!r}")
            if _fields(template) != _fields(_ENGLISH[key]):
                raise ValueError(f"admin message {key!r} must preserve its named placeholders")
            copied[key] = template
        object.__setattr__(self, "overrides", MappingProxyType(copied))

    def text(self, key: str, **values: object) -> str:
        """Render one known message without attribute access or format directives."""
        if key not in _ENGLISH:
            raise KeyError(key)
        template = self.overrides.get(key, _ENGLISH[key])
        expected = _fields(template)
        if set(values) != expected:
            raise ValueError(f"admin message {key!r} requires {sorted(expected)!r}")
        return template.format_map(values)

    @property
    def keys(self) -> tuple[str, ...]:
        """Return the stable catalog keys for translation tooling and completeness checks."""
        return tuple(_ENGLISH)


ENGLISH_MESSAGES = AdminMessages()
