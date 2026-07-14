import pytest

from app.config import Settings
from app.sandbox import get_sandbox_provider


@pytest.mark.asyncio
async def test_local_sandbox_write_read_and_shell(tmp_path):
    settings = Settings(sandbox_provider="local", sandbox_root=str(tmp_path / "sb"))
    sb = get_sandbox_provider(settings)
    assert sb.provider == "local"

    state = await sb.allocate("sess-1")
    assert state.allocated is True
    assert state.workspace

    path = await sb.write_file("sess-1", "notes.txt", "hello sandbox")
    assert path.endswith("notes.txt")
    text = await sb.read_file("sess-1", "notes.txt")
    assert text == "hello sandbox"

    result = await sb.run_command("sess-1", "echo hi && ls notes.txt")
    assert result.ok
    assert "hi" in result.stdout
    assert "notes.txt" in result.stdout


@pytest.mark.asyncio
async def test_none_sandbox_rejects_file_ops():
    sb = get_sandbox_provider(Settings(sandbox_provider="none"))
    with pytest.raises(RuntimeError, match="none"):
        await sb.write_file("s", "a.txt", "x")
