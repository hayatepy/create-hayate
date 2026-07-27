"""Typed, database-independent admin contracts."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date, datetime
from math import isfinite
from types import MappingProxyType
from typing import Literal, Protocol, cast

from hayate import Context

type AdminAction = Literal[
    "site:view",
    "resource:view",
    "resource:add",
    "resource:change",
    "resource:delete",
    "resource:bulk",
    "resource:history",
]
type FieldKind = Literal[
    "text",
    "email",
    "integer",
    "number",
    "checkbox",
    "textarea",
    "select",
    "date",
    "datetime-local",
]
type AuditPhase = Literal["attempt", "success", "failure"]
type InlineOperation = Literal["create", "update", "delete"]
type Record = Mapping[str, object]
type FieldValidator = Callable[[object], str | None]

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_SLUG = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_SRI = re.compile(r"^sha(?:256|384|512)-[A-Za-z0-9+/]+={0,2}$")
_FIELD_KINDS = frozenset(
    {
        "text",
        "email",
        "integer",
        "number",
        "checkbox",
        "textarea",
        "select",
        "date",
        "datetime-local",
    }
)


@dataclass(frozen=True, slots=True)
class Actor:
    """Authenticated administrator identity returned by application policy."""

    id: str
    display: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, str)
            or not self.id
            or len(self.id) > 255
            or any(ord(char) < 0x20 for char in self.id)
        ):
            raise ValueError("actor id must be 1-255 characters")
        if not isinstance(self.display, str) or not self.display or len(self.display) > 255:
            raise ValueError("actor display must be 1-255 characters")


@dataclass(frozen=True, slots=True)
class AdminAsset:
    """Optional self-hosted htmx browser asset."""

    url: str
    integrity: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.url, str)
            or not self.url.startswith("/")
            or self.url.startswith("//")
        ):
            raise ValueError("admin asset URL must be a same-origin absolute path")
        if not isinstance(self.integrity, str) or not _SRI.fullmatch(self.integrity):
            raise ValueError("admin asset integrity must be an sha256/384/512 SRI value")


@dataclass(frozen=True, slots=True)
class AdminField:
    """One explicitly exposed record field."""

    name: str
    label: str
    kind: FieldKind = "text"
    required: bool = True
    read_only: bool = False
    list_display: bool = True
    searchable: bool = False
    sortable: bool = False
    filterable: bool = False
    max_length: int = 255
    choices: tuple[tuple[str, str], ...] = ()
    validator: FieldValidator | None = dataclass_field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _IDENTIFIER.fullmatch(self.name):
            raise ValueError(f"unsafe admin field name: {self.name!r}")
        if not isinstance(self.label, str) or not self.label or len(self.label) > 120:
            raise ValueError(f"{self.name}: label must be 1-120 characters")
        if self.kind not in _FIELD_KINDS:
            raise ValueError(f"{self.name}: unsupported field kind: {self.kind!r}")
        flags = (
            self.required,
            self.read_only,
            self.list_display,
            self.searchable,
            self.sortable,
            self.filterable,
        )
        if any(not isinstance(flag, bool) for flag in flags):
            raise ValueError(f"{self.name}: field flags must be booleans")
        if (
            not isinstance(self.max_length, int)
            or isinstance(self.max_length, bool)
            or not 1 <= self.max_length <= 16_384
        ):
            raise ValueError(f"{self.name}: max_length must be in 1-16384")
        if not isinstance(self.choices, tuple) or any(
            not isinstance(choice, tuple)
            or len(choice) != 2
            or not all(isinstance(item, str) for item in choice)
            for choice in self.choices
        ):
            raise ValueError(f"{self.name}: choices must contain string pairs")
        choice_values = [value for value, _ in self.choices]
        if any(not value or not label for value, label in self.choices):
            raise ValueError(f"{self.name}: choice values and labels must not be empty")
        if len(self.choices) > 100:
            raise ValueError(f"{self.name}: choices must not exceed 100 entries")
        if any(len(value) > 255 or len(label) > 120 for value, label in self.choices):
            raise ValueError(f"{self.name}: choice values or labels are too long")
        if len(choice_values) != len(set(choice_values)):
            raise ValueError(f"{self.name}: choice values must be unique")
        if self.kind == "select" and not self.choices:
            raise ValueError(f"{self.name}: select fields require choices")
        if self.kind != "select" and self.choices:
            raise ValueError(f"{self.name}: choices are only valid for select fields")
        if self.filterable and not self.choices:
            raise ValueError(f"{self.name}: filters require an explicit choice allowlist")
        if self.read_only and self.required:
            raise ValueError(f"{self.name}: read-only fields cannot be required input")
        if self.validator is not None and not callable(self.validator):
            raise ValueError(f"{self.name}: validator must be callable")

    def parse(self, raw: str | None) -> tuple[object | None, str | None]:
        """Convert one bounded HTML form value without executing application code."""
        if self.read_only:
            return None, None
        if self.kind == "checkbox":
            value: object = raw is not None
        else:
            value_text = "" if raw is None else raw
            if len(value_text) > self.max_length:
                return None, f"Must be at most {self.max_length} characters."
            if not value_text:
                if self.required:
                    return None, "This field is required."
                return None, None
            try:
                if self.kind == "integer":
                    value = int(value_text)
                elif self.kind == "number":
                    value = float(value_text)
                    if not isfinite(value):
                        raise ValueError
                elif self.kind == "date":
                    date.fromisoformat(value_text)
                    value = value_text
                elif self.kind == "datetime-local":
                    datetime.fromisoformat(value_text)
                    value = value_text
                else:
                    value = value_text
            except ValueError:
                expected = {
                    "integer": "an integer",
                    "number": "a finite number",
                    "date": "a valid date",
                    "datetime-local": "a valid date and time",
                }.get(self.kind, "a valid value")
                return None, f"Enter {expected}."
            if self.kind == "email" and (
                value_text.count("@") != 1 or value_text.startswith("@") or value_text.endswith("@")
            ):
                return None, "Enter a valid email address."

        if self.choices and str(value) not in {choice for choice, _ in self.choices}:
            return None, "Select a valid choice."
        if self.validator is not None:
            message = self.validator(value)
            if message is not None:
                return None, message
        return value, None


@dataclass(frozen=True, slots=True)
class ListQuery:
    """Allowlisted list controls passed to repository code."""

    search: str | None
    filters: Mapping[str, str]
    order_by: str | None
    descending: bool
    offset: int
    limit: int

    def __post_init__(self) -> None:
        if self.search is not None and (not isinstance(self.search, str) or len(self.search) > 200):
            raise ValueError("admin search must not exceed 200 characters")
        if not isinstance(self.filters, Mapping):
            raise ValueError("admin filters must be a mapping")
        if self.order_by is not None and not isinstance(self.order_by, str):
            raise ValueError("admin order_by must be a safe field identifier")
        if not isinstance(self.descending, bool):
            raise ValueError("admin descending must be a boolean")
        if not isinstance(self.offset, int) or isinstance(self.offset, bool) or self.offset < 0:
            raise ValueError("admin offset must be non-negative")
        if (
            not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or not 1 <= self.limit <= 100
        ):
            raise ValueError("admin limit must be in 1-100")
        if self.order_by is not None and not _IDENTIFIER.fullmatch(self.order_by):
            raise ValueError("admin order_by must be a safe field identifier")
        if any(
            not isinstance(name, str)
            or not _IDENTIFIER.fullmatch(name)
            or not isinstance(value, str)
            or len(value) > 255
            for name, value in self.filters.items()
        ):
            raise ValueError("admin filters must contain bounded safe field values")
        object.__setattr__(self, "filters", MappingProxyType(dict(self.filters)))


@dataclass(frozen=True, slots=True)
class Page:
    """One bounded repository page and its filtered total."""

    items: Sequence[Record]
    total: int

    def __post_init__(self) -> None:
        if not isinstance(self.total, int) or isinstance(self.total, bool) or self.total < 0:
            raise ValueError("admin page total must be non-negative")
        if (
            not isinstance(self.items, Sequence)
            or isinstance(self.items, (str, bytes))
            or any(not isinstance(item, Mapping) for item in self.items)
        ):
            raise ValueError("admin page items must be a sequence of records")
        if self.total < len(self.items):
            raise ValueError("admin page total cannot be smaller than its item count")
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class RelationshipChoice:
    """One bounded, already tenant-scoped related-object choice."""

    id: str
    label: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, str)
            or not self.id
            or len(self.id) > 255
            or any(ord(character) < 0x20 for character in self.id)
        ):
            raise ValueError("relationship choice ID must be a bounded printable string")
        if (
            not isinstance(self.label, str)
            or not self.label
            or len(self.label) > 255
            or any(ord(character) < 0x20 for character in self.label)
        ):
            raise ValueError("relationship choice label must be a bounded printable string")


@dataclass(frozen=True, slots=True)
class RelationshipQuery:
    """Bounded search controls passed to an explicit relationship source."""

    search: str | None
    offset: int
    limit: int

    def __post_init__(self) -> None:
        if self.search is not None and (not isinstance(self.search, str) or len(self.search) > 200):
            raise ValueError("relationship search must not exceed 200 characters")
        if not isinstance(self.offset, int) or isinstance(self.offset, bool) or self.offset < 0:
            raise ValueError("relationship offset must be non-negative")
        if (
            not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or not 1 <= self.limit <= 100
        ):
            raise ValueError("relationship limit must be in 1-100")


@dataclass(frozen=True, slots=True)
class RelationshipPage:
    """One bounded page from a tenant-scoped relationship search."""

    items: Sequence[RelationshipChoice]
    total: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.items, Sequence)
            or isinstance(self.items, (str, bytes))
            or any(not isinstance(item, RelationshipChoice) for item in self.items)
        ):
            raise ValueError("relationship items must contain RelationshipChoice values")
        if not isinstance(self.total, int) or isinstance(self.total, bool) or self.total < 0:
            raise ValueError("relationship total must be non-negative")
        if self.total < len(self.items):
            raise ValueError("relationship total cannot be smaller than its item count")
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("relationship choice IDs must be unique")
        object.__setattr__(self, "items", tuple(self.items))


class RelationshipSearcher(Protocol):
    """Search only choices visible in the current application/tenant scope."""

    def __call__(
        self,
        context: Context,
        source_resource: AdminResource,
        target_resource: AdminResource,
        relationship: AdminRelationship,
        source_object_id: str | None,
        query: RelationshipQuery,
    ) -> Awaitable[RelationshipPage]: ...


class RelationshipResolver(Protocol):
    """Resolve one submitted ID inside the current application/tenant scope."""

    def __call__(
        self,
        context: Context,
        source_resource: AdminResource,
        target_resource: AdminResource,
        relationship: AdminRelationship,
        source_object_id: str | None,
        related_object_id: str,
    ) -> Awaitable[RelationshipChoice | None]: ...


@dataclass(frozen=True, slots=True)
class AdminRelationship:
    """Explicit to-one relationship with no reflection or lazy loading."""

    field: str
    target_resource: str
    display_field: str
    search: RelationshipSearcher = dataclass_field(repr=False, compare=False)
    resolve: RelationshipResolver = dataclass_field(repr=False, compare=False)
    max_choices: int = 25

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not _IDENTIFIER.fullmatch(self.field):
            raise ValueError(f"unsafe relationship field: {self.field!r}")
        if not isinstance(self.target_resource, str) or not _SLUG.fullmatch(self.target_resource):
            raise ValueError(f"unsafe relationship target: {self.target_resource!r}")
        if not isinstance(self.display_field, str) or not _IDENTIFIER.fullmatch(self.display_field):
            raise ValueError(f"unsafe relationship display field: {self.display_field!r}")
        if self.display_field == self.field:
            raise ValueError(f"{self.field}: relationship display field must be separate")
        if not callable(self.search) or not callable(self.resolve):
            raise ValueError(f"{self.field}: relationship callbacks must be callable")
        if (
            not isinstance(self.max_choices, int)
            or isinstance(self.max_choices, bool)
            or not 1 <= self.max_choices <= 100
        ):
            raise ValueError(f"{self.field}: max_choices must be in 1-100")


@dataclass(frozen=True, slots=True)
class InlineCollection:
    """A complete, bounded child snapshot for one parent object."""

    items: Sequence[Record]
    total: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.items, Sequence)
            or isinstance(self.items, (str, bytes))
            or any(not isinstance(item, Mapping) for item in self.items)
        ):
            raise ValueError("inline items must be a sequence of records")
        if (
            not isinstance(self.total, int)
            or isinstance(self.total, bool)
            or not 0 <= self.total <= 100
        ):
            raise ValueError("inline total must be in 0-100")
        if self.total != len(self.items):
            raise ValueError("inline collection must be a complete bounded snapshot")
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True, slots=True)
class InlineMutation:
    """Exactly one inline write; repositories never receive a generic cascade."""

    operation: InlineOperation
    object_id: str | None
    values: Mapping[str, object] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.operation not in ("create", "update", "delete"):
            raise ValueError(f"unsupported inline operation: {self.operation!r}")
        if self.operation == "create":
            if self.object_id is not None:
                raise ValueError("inline create must not include an object ID")
        elif (
            not isinstance(self.object_id, str)
            or not self.object_id
            or len(self.object_id) > 255
            or any(ord(character) < 0x20 for character in self.object_id)
        ):
            raise ValueError("inline update/delete requires a bounded object ID")
        if not isinstance(self.values, Mapping) or len(self.values) > 32:
            raise ValueError("inline values must be a bounded mapping")
        if self.operation == "delete" and self.values:
            raise ValueError("inline delete must not include values")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class InlineMutationResult:
    """Result of one repository-owned atomic inline write."""

    record: Record | None = None
    deleted: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.deleted, bool):
            raise ValueError("inline deleted must be a boolean")
        if self.record is not None and not isinstance(self.record, Mapping):
            raise ValueError("inline result record must be a mapping")
        if (self.record is None) == (not self.deleted):
            raise ValueError("inline result must contain one record or confirm deletion")
        if self.record is not None:
            object.__setattr__(self, "record", MappingProxyType(dict(self.record)))


class InlineReader(Protocol):
    """Load one complete bounded child collection without per-row queries."""

    def __call__(
        self,
        context: Context,
        parent_resource: AdminResource,
        target_resource: AdminResource,
        inline: AdminInline,
        parent_object_id: str,
        limit: int,
    ) -> Awaitable[InlineCollection]: ...


class InlineMutator(Protocol):
    """Own one atomic write and re-check tenant and parent membership in storage."""

    def __call__(
        self,
        context: Context,
        parent_resource: AdminResource,
        target_resource: AdminResource,
        inline: AdminInline,
        parent_object_id: str,
        mutation: InlineMutation,
    ) -> Awaitable[InlineMutationResult]: ...


@dataclass(frozen=True, slots=True)
class AdminInline:
    """One explicit bounded child editor attached to a parent resource."""

    slug: str
    label: str
    target_resource: str
    parent_field: str
    fields: tuple[str, ...]
    read: InlineReader = dataclass_field(repr=False, compare=False)
    mutate: InlineMutator = dataclass_field(repr=False, compare=False)
    max_items: int = 20

    def __post_init__(self) -> None:
        if not isinstance(self.slug, str) or not _SLUG.fullmatch(self.slug):
            raise ValueError(f"unsafe inline slug: {self.slug!r}")
        if not isinstance(self.label, str) or not self.label or len(self.label) > 120:
            raise ValueError(f"{self.slug}: inline label must be 1-120 characters")
        if not isinstance(self.target_resource, str) or not _SLUG.fullmatch(self.target_resource):
            raise ValueError(f"unsafe inline target: {self.target_resource!r}")
        if not isinstance(self.parent_field, str) or not _IDENTIFIER.fullmatch(self.parent_field):
            raise ValueError(f"unsafe inline parent field: {self.parent_field!r}")
        if (
            not isinstance(self.fields, tuple)
            or not self.fields
            or len(self.fields) > 32
            or any(
                not isinstance(name, str) or not _IDENTIFIER.fullmatch(name) for name in self.fields
            )
            or len(self.fields) != len(set(self.fields))
        ):
            raise ValueError(f"{self.slug}: inline fields must be unique safe identifiers")
        if not callable(self.read) or not callable(self.mutate):
            raise ValueError(f"{self.slug}: inline callbacks must be callable")
        if (
            not isinstance(self.max_items, int)
            or isinstance(self.max_items, bool)
            or not 1 <= self.max_items <= 100
        ):
            raise ValueError(f"{self.slug}: max_items must be in 1-100")


class AdminRepository(Protocol):
    """Storage operations normally implemented with generated hayate-sql calls."""

    async def list(self, query: ListQuery) -> Page: ...

    async def get(self, object_id: str) -> Record | None: ...

    async def create(self, values: Mapping[str, object]) -> Record: ...

    async def update(self, object_id: str, values: Mapping[str, object]) -> Record | None: ...

    async def delete(self, object_id: str) -> bool: ...


class AdminRepositoryFactory(Protocol):
    """Resolve a repository from request-local runtime bindings."""

    def __call__(self, context: Context) -> AdminRepository: ...


def _is_repository(value: object) -> bool:
    operations = ("list", "get", "create", "update", "delete")
    return all(callable(getattr(value, operation, None)) for operation in operations)


@dataclass(frozen=True, slots=True)
class BulkActionResult:
    """Complete per-object outcome returned by an explicit bulk callback."""

    succeeded: Sequence[str]
    failed: Mapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.succeeded, Sequence)
            or isinstance(self.succeeded, (str, bytes))
            or any(not isinstance(object_id, str) or not object_id for object_id in self.succeeded)
        ):
            raise ValueError("bulk succeeded IDs must be a sequence of non-empty strings")
        succeeded = tuple(self.succeeded)
        if len(succeeded) != len(set(succeeded)):
            raise ValueError("bulk succeeded IDs must be unique")
        if not isinstance(self.failed, Mapping) or any(
            not isinstance(object_id, str)
            or not object_id
            or not isinstance(message, str)
            or not message
            or len(message) > 500
            for object_id, message in self.failed.items()
        ):
            raise ValueError("bulk failures must contain bounded object messages")
        if set(succeeded) & set(self.failed):
            raise ValueError("bulk succeeded and failed IDs must not overlap")
        if len(succeeded) + len(self.failed) > 100:
            raise ValueError("bulk results must not exceed 100 objects")
        object.__setattr__(self, "succeeded", succeeded)
        object.__setattr__(self, "failed", MappingProxyType(dict(self.failed)))


class BulkActionHandler(Protocol):
    """Execute one allowlisted action against already-authorized object IDs."""

    def __call__(
        self,
        context: Context,
        repository: AdminRepository,
        object_ids: tuple[str, ...],
    ) -> Awaitable[BulkActionResult]: ...


@dataclass(frozen=True, slots=True)
class AdminBulkAction:
    """One bounded resource action with an explicit permission and callback."""

    slug: str
    label: str
    required_action: AdminAction
    handler: BulkActionHandler = dataclass_field(repr=False, compare=False)
    max_selected: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.slug, str) or not _SLUG.fullmatch(self.slug):
            raise ValueError(f"unsafe admin bulk action slug: {self.slug!r}")
        if not isinstance(self.label, str) or not self.label or len(self.label) > 120:
            raise ValueError(f"{self.slug}: bulk action label must be 1-120 characters")
        if self.required_action not in ("resource:change", "resource:delete"):
            raise ValueError(
                f"{self.slug}: bulk action permission must be resource:change or resource:delete"
            )
        if not callable(self.handler):
            raise ValueError(f"{self.slug}: bulk action handler must be callable")
        if (
            not isinstance(self.max_selected, int)
            or isinstance(self.max_selected, bool)
            or not 1 <= self.max_selected <= 100
        ):
            raise ValueError(f"{self.slug}: max_selected must be in 1-100")


@dataclass(frozen=True, slots=True)
class AdminResource:
    """Explicit operational surface for one record family."""

    slug: str
    label: str
    singular_label: str
    fields: tuple[AdminField, ...]
    repository: AdminRepository | AdminRepositoryFactory
    bulk_actions: tuple[AdminBulkAction, ...] = ()
    id_field: str = "id"
    title_field: str = "id"
    page_size: int = 50
    relationships: tuple[AdminRelationship, ...] = ()
    inlines: tuple[AdminInline, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.slug, str) or not _SLUG.fullmatch(self.slug):
            raise ValueError(f"unsafe admin resource slug: {self.slug!r}")
        if (
            not isinstance(self.label, str)
            or not isinstance(self.singular_label, str)
            or not self.label
            or not self.singular_label
        ):
            raise ValueError(f"{self.slug}: labels must not be empty")
        if len(self.label) > 120 or len(self.singular_label) > 120:
            raise ValueError(f"{self.slug}: labels must not exceed 120 characters")
        if (
            not isinstance(self.fields, tuple)
            or not self.fields
            or any(not isinstance(admin_field, AdminField) for admin_field in self.fields)
        ):
            raise ValueError(f"{self.slug}: at least one field is required")
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError(f"{self.slug}: field names must be unique")
        if not isinstance(self.id_field, str) or self.id_field not in names:
            raise ValueError(f"{self.slug}: id_field must name a declared field")
        if not isinstance(self.title_field, str) or self.title_field not in names:
            raise ValueError(f"{self.slug}: title_field must name a declared field")
        if not any(admin_field.list_display for admin_field in self.fields):
            raise ValueError(f"{self.slug}: at least one field must be shown in lists")
        if not _is_repository(self.repository) and not callable(self.repository):
            raise ValueError(
                f"{self.slug}: repository must implement all operations or be a factory"
            )
        if not isinstance(self.bulk_actions, tuple) or any(
            not isinstance(action, AdminBulkAction) for action in self.bulk_actions
        ):
            raise ValueError(f"{self.slug}: bulk_actions must contain AdminBulkAction values")
        action_slugs = [action.slug for action in self.bulk_actions]
        if len(action_slugs) != len(set(action_slugs)):
            raise ValueError(f"{self.slug}: bulk action slugs must be unique")
        if not isinstance(self.relationships, tuple) or any(
            not isinstance(relationship, AdminRelationship) for relationship in self.relationships
        ):
            raise ValueError(f"{self.slug}: relationships must contain AdminRelationship values")
        relationship_fields = [relationship.field for relationship in self.relationships]
        if len(relationship_fields) != len(set(relationship_fields)):
            raise ValueError(f"{self.slug}: relationship fields must be unique")
        for relationship in self.relationships:
            relation_field = self.field_map.get(relationship.field)
            display_field = self.field_map.get(relationship.display_field)
            if (
                relation_field is None
                or relation_field.read_only
                or relation_field.kind != "text"
                or relation_field.max_length > 255
            ):
                raise ValueError(
                    f"{self.slug}.{relationship.field}: relationship field must be "
                    "a writable text field bounded to 255 characters"
                )
            if display_field is None or not display_field.read_only:
                raise ValueError(
                    f"{self.slug}.{relationship.field}: display_field must be a "
                    "declared read-only field"
                )
            if relationship.field in (self.id_field, self.title_field):
                raise ValueError(
                    f"{self.slug}.{relationship.field}: ID/title fields cannot be relationships"
                )
        if not isinstance(self.inlines, tuple) or any(
            not isinstance(inline, AdminInline) for inline in self.inlines
        ):
            raise ValueError(f"{self.slug}: inlines must contain AdminInline values")
        inline_slugs = [inline.slug for inline in self.inlines]
        if len(inline_slugs) != len(set(inline_slugs)):
            raise ValueError(f"{self.slug}: inline slugs must be unique")
        if (
            not isinstance(self.page_size, int)
            or isinstance(self.page_size, bool)
            or not 1 <= self.page_size <= 100
        ):
            raise ValueError(f"{self.slug}: page_size must be in 1-100")

    @property
    def field_map(self) -> Mapping[str, AdminField]:
        return MappingProxyType({field.name: field for field in self.fields})

    def repository_for(self, context: Context) -> AdminRepository:
        """Resolve a static repository or one backed by request-local bindings."""
        if _is_repository(self.repository):
            return cast(AdminRepository, self.repository)
        resolved = cast(AdminRepositoryFactory, self.repository)(context)
        if not _is_repository(resolved):
            raise TypeError(f"{self.slug}: repository factory returned an invalid repository")
        return resolved

    @property
    def bulk_action_map(self) -> Mapping[str, AdminBulkAction]:
        return MappingProxyType({action.slug: action for action in self.bulk_actions})

    @property
    def relationship_map(self) -> Mapping[str, AdminRelationship]:
        return MappingProxyType(
            {relationship.field: relationship for relationship in self.relationships}
        )

    @property
    def inline_map(self) -> Mapping[str, AdminInline]:
        return MappingProxyType({inline.slug: inline for inline in self.inlines})


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Parameter-free security event: submitted values are deliberately absent."""

    occurred_at: datetime
    phase: AuditPhase
    action: AdminAction
    resource: str | None
    object_id: str | None
    actor_id: str | None
    error_type: str | None = None
    operation: str | None = None


@dataclass(frozen=True, slots=True)
class AuditHistoryPage:
    """One bounded page of already-redacted object audit events."""

    items: Sequence[AuditEvent]
    total: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.items, Sequence)
            or isinstance(self.items, (str, bytes))
            or any(not isinstance(event, AuditEvent) for event in self.items)
        ):
            raise ValueError("audit history items must contain AuditEvent values")
        if not isinstance(self.total, int) or isinstance(self.total, bool) or self.total < 0:
            raise ValueError("audit history total must be non-negative")
        if self.total < len(self.items):
            raise ValueError("audit history total cannot be smaller than its item count")
        object.__setattr__(self, "items", tuple(self.items))


class AuditHistoryReader(Protocol):
    """Read only redacted events for one already-authorized object."""

    def __call__(
        self,
        context: Context,
        resource: AdminResource,
        object_id: str,
        offset: int,
        limit: int,
    ) -> Awaitable[AuditHistoryPage]: ...


class AuditHistoryReaderFactory(Protocol):
    """Resolve a history reader from request-local runtime bindings."""

    def __call__(self, context: Context) -> AuditHistoryReader: ...


class Authorizer(Protocol):
    """Return an actor only when this exact operation is allowed."""

    def __call__(
        self,
        context: Context,
        action: AdminAction,
        resource: AdminResource | None,
        object_id: str | None,
    ) -> Awaitable[Actor | None]: ...


class AuditSink(Protocol):
    """Persist or forward redacted security events."""

    def __call__(self, event: AuditEvent) -> Awaitable[None]: ...


class AuditSinkFactory(Protocol):
    """Resolve an audit sink from request-local runtime bindings."""

    def __call__(self, context: Context) -> AuditSink: ...


class AdminValidationError(ValueError):
    """Repository-level domain validation keyed by declared field name."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        if not isinstance(errors, Mapping) or not errors:
            raise ValueError("admin validation errors must not be empty")
        if len(errors) > 101 or any(
            (
                not isinstance(name, str)
                or (name != "__all__" and not _IDENTIFIER.fullmatch(name))
                or not isinstance(message, str)
                or not message
                or len(message) > 500
            )
            for name, message in errors.items()
        ):
            raise ValueError("admin validation errors must contain bounded field messages")
        self.errors = MappingProxyType(dict(errors))
        super().__init__("admin record validation failed")
