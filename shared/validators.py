"""Reusable schema validation helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class SharedValidationError(ValueError):
    """Raised when a shared contract is invalid."""


def require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SharedValidationError(f"{path} must be a dict")
    return value


def require_keys(data: dict[str, Any], keys: tuple[str, ...], path: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise SharedValidationError(f"{path} missing required fields: {', '.join(missing)}")


def require_str(value: Any, path: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise SharedValidationError(f"{path} must be a str")
    if not allow_empty and not value.strip():
        raise SharedValidationError(f"{path} must not be empty")
    return value


def optional_str(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return require_str(value, path)


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise SharedValidationError(f"{path} must be a bool")
    return value


def require_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SharedValidationError(f"{path} must be an int")
    return value


def string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise SharedValidationError(f"{path} must be a list")
    return [require_str(item, f"{path}[{index}]") for index, item in enumerate(value)]


def int_list(value: Any, path: str) -> list[int]:
    if not isinstance(value, list):
        raise SharedValidationError(f"{path} must be a list")
    return [require_int(item, f"{path}[{index}]") for index, item in enumerate(value)]


def dict_copy(value: Any, path: str) -> dict[str, Any]:
    return deepcopy(require_dict(value, path))
