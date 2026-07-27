import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from create_hayate import cli
from create_hayate.frontend_compatibility import (
    BROWSER_IDS,
    FRONTEND_PROFILES,
    FULL_SHARDS,
    SMOKE_IDS,
    SUPPORTED_FRONTEND_CASE_IDS,
    SUPPORTED_FRONTEND_CASES,
    WORKERD_IDS,
    smoke_frontend_cases,
    supports_frontend_plan,
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


matrix_runner = _load_module(
    "frontend_matrix_runner",
    Path("scripts/check_frontend_matrix.py"),
)


def _script(*arguments: str) -> str:
    return subprocess.run(
        [sys.executable, "scripts/check_frontend_matrix.py", *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_frontend_compatibility_data_enumerates_unique_effective_plans():
    assert len(SUPPORTED_FRONTEND_CASES) == 112
    assert len(SUPPORTED_FRONTEND_CASE_IDS) == len(SUPPORTED_FRONTEND_CASES)
    assert tuple(FRONTEND_PROFILES) == ("htmx", "react", "astro")

    for case in SUPPORTED_FRONTEND_CASES:
        assert supports_frontend_plan(
            frontend=case.frontend,
            template=case.template,
            features=case.effective_features,
            auth=case.auth,
            entrypoint=case.entrypoint,
            production=False,
        )
        if case.frontend in {"react", "astro"}:
            assert "openapi" in case.effective_features
            assert "openapi" not in case.requested_features
        if case.template == "mcp":
            assert "mcp" in case.effective_features
            assert "mcp" not in case.requested_features


def test_every_supported_frontend_case_builds_the_cli_plan():
    parser = argparse.ArgumentParser()
    for case in SUPPORTED_FRONTEND_CASES:
        arguments = argparse.Namespace(
            frontend=case.frontend,
            renderer=None,
            features=",".join(case.requested_features) or None,
            preset=None,
            auth=None if case.auth == "none" else case.auth,
            workers_entrypoint=case.entrypoint,
        )
        plan = cli._build_plan(arguments, case.template, parser)
        assert plan.frontend == case.frontend
        assert plan.template == case.template
        assert set(plan.features) == set(case.effective_features)
        assert plan.auth == case.auth
        assert plan.workers_entrypoint == case.entrypoint


def test_cli_fails_closed_when_a_frontend_plan_is_not_in_compatibility_data(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "supports_frontend_plan", lambda **_kwargs: False)
    with pytest.raises(SystemExit, match="2"):
        cli.main(["demo-app", "--frontend", "react", "--no-input"])
    assert not (tmp_path / "demo-app").exists()


def test_bounded_and_full_matrices_cover_the_declared_cases_once():
    smoke = smoke_frontend_cases()
    assert tuple(case.id for case in smoke) == SMOKE_IDS
    assert BROWSER_IDS.union(WORKERD_IDS) == frozenset(SMOKE_IDS)
    assert BROWSER_IDS.isdisjoint(WORKERD_IDS)

    smoke_matrix = json.loads(_script("matrix", "--scope", "smoke"))["include"]
    assert [entry["id"] for entry in smoke_matrix] == list(SMOKE_IDS)

    full_matrix = json.loads(_script("matrix", "--scope", "full"))["include"]
    assert len(full_matrix) == FULL_SHARDS
    assert [entry["selector"] for entry in full_matrix] == [
        str(shard) for shard in range(FULL_SHARDS)
    ]
    shard_sizes = [
        sum(index % FULL_SHARDS == shard for index, _case in enumerate(SUPPORTED_FRONTEND_CASES))
        for shard in range(FULL_SHARDS)
    ]
    assert sum(shard_sizes) == len(SUPPORTED_FRONTEND_CASE_IDS)
    assert all(shard_sizes)


def test_exact_toolchain_contract_fails_closed_on_drift():
    expected = matrix_runner._expected_toolchains("3.14.6")

    assert expected == {
        "python": "3.14.6",
        "uv": "0.11.28",
        "node": "24.18.0",
        "npm": "11.16.0",
    }
    matrix_runner._verify_toolchains(expected, expected)
    with pytest.raises(RuntimeError, match=r"node: expected 24\.18\.0, got 25\.0\.0"):
        matrix_runner._verify_toolchains({**expected, "node": "25.0.0"}, expected)


def test_browser_matrix_uses_isolated_dynamic_ports():
    environment = matrix_runner._browser_environment()

    assert environment["HAYATE_E2E_ISOLATED"] == "1"
    assert environment["HAYATE_E2E_BACKEND_PORT"] != environment["HAYATE_E2E_FRONTEND_PORT"]
    assert environment["HAYATE_DEV_ORIGIN"] == (
        f"http://127.0.0.1:{environment['HAYATE_E2E_BACKEND_PORT']}"
    )


def test_evidence_summary_fails_closed_on_incomplete_duplicate_or_failed_cases(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    cases = smoke_frontend_cases()
    for index, case in enumerate(cases):
        (evidence / f"{index}.json").write_text(
            json.dumps({"case": {"id": case.id}, "status": "passed"}),
            encoding="utf-8",
        )

    output = tmp_path / "summary.json"
    assert (
        matrix_runner._summarize(
            evidence,
            scope="smoke",
            output=output,
            markdown=None,
        )
        == 0
    )

    duplicate = evidence / "duplicate.json"
    duplicate.write_text((evidence / "0.json").read_text(encoding="utf-8"), encoding="utf-8")
    assert matrix_runner._summarize(evidence, scope="smoke", output=output, markdown=None) == 1
    duplicate.unlink()

    failed = json.loads((evidence / "0.json").read_text(encoding="utf-8"))
    failed["status"] = "failed"
    (evidence / "0.json").write_text(json.dumps(failed), encoding="utf-8")
    assert matrix_runner._summarize(evidence, scope="smoke", output=output, markdown=None) == 1
    (evidence / "0.json").unlink()
    assert matrix_runner._summarize(evidence, scope="smoke", output=output, markdown=None) == 1


def test_published_frontend_compatibility_document_is_generated_from_data():
    document = Path("docs/FRONTEND_COMPATIBILITY.md").read_text(encoding="utf-8")
    assert document == _script("document")
