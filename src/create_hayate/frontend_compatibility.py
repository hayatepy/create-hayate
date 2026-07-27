"""Data-backed compatibility contract for generated frontend profiles."""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import cast


@dataclass(frozen=True)
class RuntimeAxis:
    auth: tuple[str, ...]
    entrypoints: tuple[str, ...]


@dataclass(frozen=True)
class FrontendProfile:
    description: str
    templates: tuple[str, ...]
    required_features: tuple[str, ...]
    optional_features: tuple[str, ...]


@dataclass(frozen=True)
class FrontendCase:
    id: str
    frontend: str
    template: str
    runtime: str
    requested_features: tuple[str, ...]
    effective_features: tuple[str, ...]
    auth: str
    entrypoint: str
    browser: bool
    workerd: bool
    renderer: str = "jinja"


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a string array")
    return tuple(value)


def _objects(value: object, field: str) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return tuple(value)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


_RAW = _mapping(
    json.loads(
        files("create_hayate").joinpath("frontend_compatibility.json").read_text(encoding="utf-8")
    ),
    "root",
)
SCHEMA_VERSION = _integer(_RAW.get("schema"), "schema")
FULL_SHARDS = _integer(_RAW.get("full_shards"), "full_shards")
TOOLCHAINS = {
    name: _string(version, f"toolchains.{name}")
    for name, version in _mapping(_RAW.get("toolchains"), "toolchains").items()
}
RUNTIME_AXES = {
    runtime: RuntimeAxis(
        auth=_strings(data.get("auth"), f"runtime_axes.{runtime}.auth"),
        entrypoints=_strings(data.get("entrypoints"), f"runtime_axes.{runtime}.entrypoints"),
    )
    for runtime, raw_data in _mapping(_RAW.get("runtime_axes"), "runtime_axes").items()
    for data in (_mapping(raw_data, f"runtime_axes.{runtime}"),)
}
FRONTEND_PROFILES = {
    name: FrontendProfile(
        description=_string(data.get("description"), f"profiles.{name}.description"),
        templates=_strings(data.get("templates"), f"profiles.{name}.templates"),
        required_features=_strings(
            data.get("required_features"),
            f"profiles.{name}.required_features",
        ),
        optional_features=_strings(
            data.get("optional_features"),
            f"profiles.{name}.optional_features",
        ),
    )
    for name, raw_data in _mapping(_RAW.get("profiles"), "profiles").items()
    for data in (_mapping(raw_data, f"profiles.{name}"),)
}


def _renderer_case(raw_case: object, index: int) -> FrontendCase:
    field = f"renderer_cases[{index}]"
    data = _mapping(raw_case, field)
    template = _string(data.get("template"), f"{field}.template")
    requested = _strings(data.get("requested_features"), f"{field}.requested_features")
    implicit = ("mcp",) if template == "mcp" else ()
    return FrontendCase(
        id=_string(data.get("id"), f"{field}.id"),
        frontend="htmx",
        template=template,
        runtime="api" if template == "api" else "workers",
        requested_features=requested,
        effective_features=tuple(sorted({*requested, *implicit})),
        auth=_string(data.get("auth"), f"{field}.auth"),
        entrypoint=_string(data.get("entrypoint"), f"{field}.entrypoint"),
        browser=_boolean(data.get("browser"), f"{field}.browser"),
        workerd=_boolean(data.get("workerd"), f"{field}.workerd"),
        renderer=_string(data.get("renderer"), f"{field}.renderer"),
    )


RENDERER_CASES = tuple(
    _renderer_case(raw_case, index)
    for index, raw_case in enumerate(_objects(_RAW.get("renderer_cases"), "renderer_cases"))
)
SMOKE_IDS = _strings(_RAW.get("smoke_ids"), "smoke_ids")
BROWSER_IDS = frozenset(_strings(_RAW.get("browser_ids"), "browser_ids"))
WORKERD_IDS = frozenset(_strings(_RAW.get("workerd_ids"), "workerd_ids"))


def _subsets(values: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        combination
        for size in range(len(values) + 1)
        for combination in itertools.combinations(values, size)
    )


def _case_id(
    frontend: str,
    template: str,
    auth: str,
    entrypoint: str,
    effective_features: tuple[str, ...],
) -> str:
    feature_label = "-".join(effective_features) if effective_features else "base"
    return f"{frontend}-{template}-{auth}-{entrypoint}-{feature_label}"


def supported_frontend_cases() -> tuple[FrontendCase, ...]:
    cases: list[FrontendCase] = []
    for frontend, profile in FRONTEND_PROFILES.items():
        for template in profile.templates:
            runtime = "api" if template == "api" else "workers"
            runtime_axis = RUNTIME_AXES[runtime]
            implicit = {"mcp"} if template == "mcp" else set()
            available_optional = tuple(
                feature for feature in profile.optional_features if feature not in implicit
            )
            for optional in _subsets(available_optional):
                effective = tuple(sorted({*profile.required_features, *optional, *implicit}))
                requested = tuple(
                    sorted(
                        set(effective).difference(profile.required_features).difference(implicit)
                    )
                )
                for auth, entrypoint in itertools.product(
                    runtime_axis.auth,
                    runtime_axis.entrypoints,
                ):
                    identifier = _case_id(
                        frontend,
                        template,
                        auth,
                        entrypoint,
                        effective,
                    )
                    cases.append(
                        FrontendCase(
                            id=identifier,
                            frontend=frontend,
                            template=template,
                            runtime=runtime,
                            requested_features=requested,
                            effective_features=effective,
                            auth=auth,
                            entrypoint=entrypoint,
                            browser=identifier in BROWSER_IDS,
                            workerd=identifier in WORKERD_IDS,
                            renderer="jinja" if frontend == "htmx" else "none",
                        )
                    )
    return tuple(cases)


SUPPORTED_FRONTEND_CASES = supported_frontend_cases()
SUPPORTED_FRONTEND_CASE_IDS = frozenset(case.id for case in SUPPORTED_FRONTEND_CASES)


def supports_frontend_plan(
    *,
    frontend: str,
    template: str,
    features: tuple[str, ...],
    auth: str,
    entrypoint: str,
    production: bool,
) -> bool:
    if frontend == "none":
        return True
    if production:
        return False
    identifier = _case_id(
        frontend,
        template,
        auth,
        entrypoint,
        tuple(sorted(features)),
    )
    return identifier in SUPPORTED_FRONTEND_CASE_IDS


def smoke_frontend_cases() -> tuple[FrontendCase, ...]:
    by_id = {
        case.id: case
        for case in (
            *SUPPORTED_FRONTEND_CASES,
            *RENDERER_CASES,
        )
    }
    return tuple(by_id[identifier] for identifier in SMOKE_IDS)
