import uuid
from unittest.mock import MagicMock

import pytest
from docker.errors import DockerException

from app.sandbox.runner import (
    SandboxConfigError,
    SandboxLimits,
    SandboxRunner,
    SandboxRunRequest,
    SandboxRunStatus,
    _MAX_OUTPUT_CHARS,
)


def _limits(**overrides) -> SandboxLimits:
    kwargs = dict(memory_limit="512m", cpu_limit="1", timeout_seconds=120)
    kwargs.update(overrides)
    return SandboxLimits(**kwargs)


def _request(tmp_path, **overrides) -> SandboxRunRequest:
    workload_dir = tmp_path / "workload"
    output_dir = tmp_path / "output"
    workload_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    kwargs = dict(
        run_id=uuid.uuid4(),
        image="reprox-sklearn-runner:latest",
        workload_dir=workload_dir,
        output_dir=output_dir,
        entrypoint_script="train.py",
        limits=_limits(),
    )
    kwargs.update(overrides)
    return SandboxRunRequest(**kwargs)


def test_config_error_for_absolute_entrypoint_script(tmp_path):
    runner = SandboxRunner(client=MagicMock())
    request = _request(tmp_path, entrypoint_script="/etc/passwd")
    with pytest.raises(SandboxConfigError):
        runner.run(request)
    runner._client.containers.run.assert_not_called()


def test_config_error_for_path_traversal_entrypoint_script(tmp_path):
    runner = SandboxRunner(client=MagicMock())
    request = _request(tmp_path, entrypoint_script="../../etc/passwd")
    with pytest.raises(SandboxConfigError):
        runner.run(request)
    runner._client.containers.run.assert_not_called()


def _make_container(exit_code=0, stdout=b"out\n", stderr=b""):
    container = MagicMock()
    container.wait.return_value = {"StatusCode": exit_code}

    def logs(stdout=False, stderr=False):
        if stdout:
            return container._stdout_bytes
        return container._stderr_bytes

    container.logs.side_effect = logs
    container._stdout_bytes = stdout
    container._stderr_bytes = stderr
    return container


def test_successful_run_reports_completed_and_captures_output(tmp_path):
    container = _make_container(exit_code=0, stdout=b"training done\n")
    client = MagicMock()
    client.containers.run.return_value = container

    runner = SandboxRunner(client=client)
    result = runner.run(_request(tmp_path))

    assert result.status == SandboxRunStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "training done\n"
    container.remove.assert_called_once_with(force=True)


def test_nonzero_exit_code_is_failed(tmp_path):
    container = _make_container(exit_code=1, stderr=b"traceback\n")
    client = MagicMock()
    client.containers.run.return_value = container

    runner = SandboxRunner(client=client)
    result = runner.run(_request(tmp_path))

    assert result.status == SandboxRunStatus.FAILED
    assert result.exit_code == 1
    container.remove.assert_called_once_with(force=True)


def test_timeout_kills_container_and_reports_timed_out(tmp_path):
    container = _make_container()
    container.wait.side_effect = Exception("timed out")
    client = MagicMock()
    client.containers.run.return_value = container

    runner = SandboxRunner(client=client)
    result = runner.run(_request(tmp_path, limits=_limits(timeout_seconds=1)))

    assert result.status == SandboxRunStatus.TIMED_OUT
    assert result.exit_code is None
    container.kill.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_docker_exception_on_run_is_reported_as_error(tmp_path):
    client = MagicMock()
    client.containers.run.side_effect = DockerException("daemon unreachable")

    runner = SandboxRunner(client=client)
    result = runner.run(_request(tmp_path))

    assert result.status == SandboxRunStatus.ERROR
    assert "daemon unreachable" in result.stderr


def test_container_removed_even_when_wait_raises(tmp_path):
    container = _make_container()
    container.wait.side_effect = Exception("boom")
    client = MagicMock()
    client.containers.run.return_value = container

    runner = SandboxRunner(client=client)
    runner.run(_request(tmp_path))

    container.remove.assert_called_once_with(force=True)


def test_output_is_truncated_at_max_size(tmp_path):
    huge_output = b"x" * (_MAX_OUTPUT_CHARS + 500)
    container = _make_container(stdout=huge_output)
    client = MagicMock()
    client.containers.run.return_value = container

    runner = SandboxRunner(client=client)
    result = runner.run(_request(tmp_path))

    assert len(result.stdout) <= _MAX_OUTPUT_CHARS + len("\n... [output truncated]")
    assert result.stdout.endswith("... [output truncated]")


def test_container_run_receives_correct_resource_and_isolation_config(tmp_path):
    container = _make_container()
    client = MagicMock()
    client.containers.run.return_value = container

    runner = SandboxRunner(client=client)
    request = _request(tmp_path, limits=_limits(memory_limit="1g", cpu_limit="2", pids_limit=64, network_disabled=True))
    runner.run(request)

    _, kwargs = client.containers.run.call_args
    assert kwargs["mem_limit"] == "1g"
    assert kwargs["nano_cpus"] == 2_000_000_000
    assert kwargs["pids_limit"] == 64
    assert kwargs["network_disabled"] is True
    assert kwargs["read_only"] is True
    assert kwargs["environment"] == {}
    assert kwargs["volumes"][str(request.workload_dir.resolve())]["mode"] == "ro"
    assert kwargs["volumes"][str(request.output_dir.resolve())]["mode"] == "rw"


def test_lazy_client_not_required_at_construction():
    # No Docker daemon needed just to instantiate the runner.
    runner = SandboxRunner()
    assert runner._client is None
