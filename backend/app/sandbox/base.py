from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SandboxState:
    provider: str
    allocated: bool
    sandbox_id: str | None = None
    workspace: str | None = None


@dataclass
class CommandResult:
    ok: bool
    stdout: str
    stderr: str
    exit_code: int


class SandboxProvider(Protocol):
    @property
    def provider(self) -> str: ...

    async def allocate(self, session_id: str) -> SandboxState: ...

    async def pause(self, session_id: str) -> None: ...

    async def destroy(self, session_id: str) -> None: ...

    async def write_file(self, session_id: str, relative_path: str, content: str) -> str: ...

    async def read_file(self, session_id: str, relative_path: str) -> str: ...

    async def run_command(
        self, session_id: str, command: str, timeout_sec: float = 30.0
    ) -> CommandResult: ...
