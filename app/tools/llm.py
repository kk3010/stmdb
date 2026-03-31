from __future__ import annotations

import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.logging_utils import instrument_module_functions

logger = logging.getLogger("smtdb.llm")

_claude: AsyncAnthropic | None = None
_voyage: Any | None = None


def get_llm_client() -> AsyncAnthropic:
	global _claude
	if _claude is None:
		_claude = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
	return _claude


def get_voyage_client() -> Any:
	global _voyage
	if _voyage is None:
		try:
			import voyageai

			_voyage = voyageai.AsyncClient(api_key=settings.voyage_api_key.get_secret_value())
		except Exception:
			class _FallbackVoyageClient:
				async def embed(self, texts: list[str], model: str, input_type: str) -> Any:
					class _Result:
						embeddings = [[0.0] * 1024]

					return _Result()

			_voyage = _FallbackVoyageClient()
	return _voyage


async def chat_complete(system: str, messages: list[dict], **kwargs) -> str:
	try:
		response = await get_llm_client().messages.create(
			model=settings.claude_model,
			max_tokens=settings.claude_max_tokens,
			system=system,
			messages=messages,
			**kwargs,
		)
		return response.content[0].text
	except Exception as exc:  # noqa: BLE001
		logger.error("Claude call failed", exc_info=exc)
		raise RuntimeError("The AI service is temporarily unavailable. Please try again.") from None


async def embed(text: str, input_type: str = "query") -> list[float]:
	try:
		result = await get_voyage_client().embed(
			texts=[text],
			model=settings.voyage_model,
			input_type=input_type,
		)
		return result.embeddings[0]
	except Exception as exc:  # noqa: BLE001
		logger.error("Voyage embedding failed", exc_info=exc)
		raise RuntimeError("Could not generate embeddings. Please try again.") from None


instrument_module_functions(
	globals(),
	logger,
	exclude={"instrument_module_functions"},
	include={"chat_complete"},
)
