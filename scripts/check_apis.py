from __future__ import annotations

import asyncio
import sys

from app.logging_utils import instrument_module_functions
from app.tools.llm import chat_complete, embed, get_llm_client


async def _run() -> int:
	try:
		text = await chat_complete("You are concise.", [{"role": "user", "content": "Say hello"}])
		print(f"Claude response: {text[:120]}")
		print(f"Claude model: {get_llm_client()._default_model if hasattr(get_llm_client(), '_default_model') else 'configured'}")

		vec = await embed("hello world", input_type="query")
		print(f"Voyage embedding dims: {len(vec)}")
		print(f"Voyage first 3: {vec[:3]}")
		return 0
	except Exception as exc:  # noqa: BLE001
		print(f"API check failed: {exc}")
		return 1


if __name__ == "__main__":
	raise SystemExit(asyncio.run(_run()))


import logging

instrument_module_functions(globals(), logging.getLogger("smtdb.scripts.check_apis"), exclude={"instrument_module_functions"})
