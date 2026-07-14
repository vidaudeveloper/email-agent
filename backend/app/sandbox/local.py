"""Local workspace sandbox for Dev Profile (no Firecracker).

Each session gets ``{sandbox_root}/{session_id}/`` on the host disk.
Not multi-tenant safe — for single-developer testing only.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.sandbox.base import CommandResult, SandboxState


class LocalSandboxProvider:
    def __init__(self, root: Path):
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._allocated: set[str] = set()

    @property
    def provider(self) -> str:
        return "local"

    def _workspace(self, session_id: str) -> Path:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self._root / safe

    def _resolve(self, session_id: str, relative_path: str) -> Path:
        workspace = self._workspace(session_id).resolve()
        target = (workspace / relative_path).resolve()
        if not str(target).startswith(str(workspace)):
            raise ValueError("Path escapes sandbox workspace")
        return target

    async def allocate(self, session_id: str) -> SandboxState:
        workspace = self._workspace(session_id)
        workspace.mkdir(parents=True, exist_ok=True)
        self._allocated.add(session_id)
        return SandboxState(
            provider=self.provider,
            allocated=True,
            sandbox_id=session_id,
            workspace=str(workspace),
        )

    async def pause(self, session_id: str) -> None:
        return None

    async def destroy(self, session_id: str) -> None:
        self._allocated.discard(session_id)
        # Keep files for debugging; wipe on explicit cleanup later if needed.
        return None

    async def write_file(self, session_id: str, relative_path: str, content: str) -> str:
        if session_id not in self._allocated:
            await self.allocate(session_id)
        path = self._resolve(session_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    async def read_file(self, session_id: str, relative_path: str) -> str:
        if session_id not in self._allocated:
            await self.allocate(session_id)
        path = self._resolve(session_id, relative_path)
        return path.read_text(encoding="utf-8")

    async def run_command(
        self, session_id: str, command: str, timeout_sec: float = 30.0
    ) -> CommandResult:
        if session_id not in self._allocated:
            await self.allocate(session_id)
        workspace = self._workspace(session_id)
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return CommandResult(
                ok=False,
                stdout="",
                stderr=f"Command timed out after {timeout_sec}s",
                exit_code=-1,
            )
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        code = proc.returncode or 0
        return CommandResult(
            ok=code == 0, stdout=stdout, stderr=stderr, exit_code=code
        )
