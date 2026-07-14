from pathlib import Path

from app.config import Settings
from app.sandbox.base import CommandResult, SandboxProvider, SandboxState
from app.sandbox.local import LocalSandboxProvider
from app.sandbox.none import NoneSandboxProvider

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent


def get_sandbox_provider(settings: Settings) -> SandboxProvider:
    name = (settings.sandbox_provider or "none").strip().lower()
    if name == "none":
        return NoneSandboxProvider()
    if name in {"local", "dev_local"}:
        root = Path(settings.sandbox_root)
        if not root.is_absolute():
            root = _PACKAGE_ROOT / root
        return LocalSandboxProvider(root)
    raise ValueError(f"Unknown sandbox provider: {settings.sandbox_provider}")


__all__ = [
    "SandboxProvider",
    "SandboxState",
    "CommandResult",
    "NoneSandboxProvider",
    "LocalSandboxProvider",
    "get_sandbox_provider",
]
