import sys

import pytest

from conclave.tools import (
    SandboxError,
    dispatch,
    grep,
    list_dir,
    read_file,
    run_shell,
    schemas_for_tier,
    write_file,
)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    return 42\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hello world", encoding="utf-8")
    return tmp_path


def test_read_file(workspace):
    result = read_file(workspace, "src/main.py")
    assert result.ok
    assert "return 42" in result.output


def test_read_file_missing(workspace):
    result = read_file(workspace, "nope.py")
    assert not result.ok


def test_read_file_rejects_escape(workspace):
    with pytest.raises(SandboxError):
        read_file(workspace, "../outside.txt")


def test_read_file_rejects_absolute_escape(workspace, tmp_path_factory):
    other = tmp_path_factory.mktemp("elsewhere") / "secret.txt"
    other.write_text("nope", encoding="utf-8")
    with pytest.raises(SandboxError):
        read_file(workspace, str(other))


def test_list_dir(workspace):
    result = list_dir(workspace, ".")
    assert result.ok
    assert "src" in result.output
    assert "README.md" in result.output


def test_grep_finds_match(workspace):
    result = grep(workspace, "return", "src")
    assert result.ok
    assert "main.py:2" in result.output


def test_grep_no_match(workspace):
    result = grep(workspace, "nonexistent_pattern_xyz", ".")
    assert result.ok
    assert "no matches" in result.output


def test_grep_invalid_regex(workspace):
    result = grep(workspace, "(unclosed", ".")
    assert not result.ok


def test_write_file(workspace):
    result = write_file(workspace, "out.txt", "content")
    assert result.ok
    assert (workspace / "out.txt").read_text(encoding="utf-8") == "content"


def test_write_file_rejects_escape(workspace):
    with pytest.raises(SandboxError):
        write_file(workspace, "../escape.txt", "x")


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX shell builtin")
def test_run_shell(workspace):
    result = run_shell(workspace, "echo hello")
    assert result.ok
    assert "hello" in result.output


def test_run_shell_cwd_is_workspace(workspace):
    cmd = "cd" if sys.platform == "win32" else "pwd"
    result = run_shell(workspace, cmd)
    assert result.ok
    assert str(workspace) in result.output or workspace.name in result.output


def test_schemas_for_tier_read_only():
    names = {s["function"]["name"] for s in schemas_for_tier("read")}
    assert names == {"read_file", "list_dir", "grep"}


def test_schemas_for_tier_read_write():
    names = {s["function"]["name"] for s in schemas_for_tier("read_write")}
    assert "write_file" in names
    assert "run_shell" not in names


def test_schemas_for_tier_full():
    names = {s["function"]["name"] for s in schemas_for_tier("full")}
    assert "run_shell" in names


def test_schemas_for_tier_invalid():
    with pytest.raises(ValueError):
        schemas_for_tier("nonsense")


def test_dispatch_unknown_tool(workspace):
    result = dispatch(workspace, "full", "not_a_real_tool", {})
    assert not result.ok


def test_dispatch_bad_arguments(workspace):
    result = dispatch(workspace, "full", "read_file", {"wrong_kwarg": "x"})
    assert not result.ok


def test_dispatch_sandbox_escape_becomes_tool_result(workspace):
    result = dispatch(workspace, "full", "read_file", {"path": "../escape.txt"})
    assert not result.ok
    assert "escapes the workspace" in result.output


def test_dispatch_enforces_tier_even_if_model_calls_disallowed_tool(workspace):
    result = dispatch(workspace, "read", "write_file", {"path": "x.txt", "content": "y"})
    assert not result.ok
    assert "not permitted" in result.output
    assert not (workspace / "x.txt").exists()


def test_dispatch_read_write_tier_cannot_run_shell(workspace):
    result = dispatch(workspace, "read_write", "run_shell", {"command": "echo hi"})
    assert not result.ok
    assert "not permitted" in result.output


def test_dispatch_invalid_tier_raises():
    with pytest.raises(ValueError):
        dispatch(None, "nonsense", "read_file", {})
