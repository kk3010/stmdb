from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable

try:
    from langgraph.errors import GraphInterrupt as _GraphInterrupt
except ImportError:  # pragma: no cover
    _GraphInterrupt = None  # type: ignore[assignment,misc]


_WRAPPED_ATTR = "__smtdb_log_wrapped__"


def _short_repr(value: Any, max_len: int = 120) -> str:
    try:
        text = repr(value)
    except Exception:  # noqa: BLE001
        text = f"<{type(value).__name__}>"
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _sync_wrapper(fn: Callable[..., Any], logger: logging.Logger) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        logger.info("step %s", fn.__qualname__)
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if _GraphInterrupt is not None and isinstance(exc, _GraphInterrupt):
                raise
            logger.exception("error %s: %s", fn.__qualname__, exc)
            raise

    setattr(wrapped, _WRAPPED_ATTR, True)
    return wrapped


def _async_wrapper(fn: Callable[..., Any], logger: logging.Logger) -> Callable[..., Any]:
    @functools.wraps(fn)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        logger.info("step %s", fn.__qualname__)
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if _GraphInterrupt is not None and isinstance(exc, _GraphInterrupt):
                raise
            logger.exception("error %s: %s", fn.__qualname__, exc)
            raise

    setattr(wrapped, _WRAPPED_ATTR, True)
    return wrapped


def instrument_module_functions(
    module_globals: dict[str, Any],
    logger: logging.Logger,
    exclude: set[str] | None = None,
    include: set[str] | None = None,
) -> None:
    if include is None:
        return

    exclude = exclude or set()
    module_name = str(module_globals.get("__name__", ""))

    for name, obj in list(module_globals.items()):
        if name in exclude or name.startswith("__"):
            continue
        if name not in include:
            continue
        if not inspect.isfunction(obj):
            continue
        if getattr(obj, _WRAPPED_ATTR, False):
            continue
        if getattr(obj, "__module__", "") != module_name:
            continue

        if inspect.iscoroutinefunction(obj):
            module_globals[name] = _async_wrapper(obj, logger)
        else:
            module_globals[name] = _sync_wrapper(obj, logger)
