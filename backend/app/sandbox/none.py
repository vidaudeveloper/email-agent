from __future__ import annotations

from app.sandbox.base import CommandResult, SandboxState


class NoneSandboxProvider:
    @property
    def provider(self) -> str:
        return "none"

    async def allocate(self, session_id: str) -> SandboxState:
        return SandboxState(provider=self.provider, allocated=False)

    async def pause(self, session_id: str) -> None:
        return None

    async def destroy(self, session_id: str) -> None:
        return None

    async def write_file(self, session_id: str, relative_path: str, content: str) -> str:
        raise RuntimeError("Sandbox provider is none — cannot write files")

    async def read_file(self, session_id: str, relative_path: str) -> str:
        raise RuntimeError("Sandbox provider is none — cannot read files")

    async def run_command(
        self, session_id: str, command: str, timeout_sec: float = 30.0
    ) -> CommandResult:
        raise RuntimeError("Sandbox provider is none — cannot run commands")
