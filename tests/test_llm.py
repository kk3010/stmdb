from __future__ import annotations

import pytest


def test_get_llm_client_returns_async_anthropic(settings_override):
	from app.tools import llm

	llm._claude = None
	assert llm.get_llm_client() is not None


def test_get_llm_client_is_singleton(settings_override):
	from app.tools import llm

	llm._claude = None
	assert llm.get_llm_client() is llm.get_llm_client()


def test_get_voyage_client_is_singleton(settings_override):
	from app.tools import llm

	llm._voyage = None
	assert llm.get_voyage_client() is llm.get_voyage_client()


@pytest.mark.asyncio
async def test_chat_complete_returns_string(mocker):
	from app.tools import llm

	mock_client = mocker.MagicMock()
	mock_client.messages.create = mocker.AsyncMock(
		return_value=mocker.MagicMock(content=[mocker.MagicMock(text="ok")])
	)
	mocker.patch("app.tools.llm.get_llm_client", return_value=mock_client)
	out = await llm.chat_complete("s", [{"role": "user", "content": "x"}])
	assert out == "ok"


@pytest.mark.asyncio
async def test_chat_complete_passes_system_as_separate_param(mocker):
	from app.tools import llm

	mock_client = mocker.MagicMock()
	create = mocker.AsyncMock(return_value=mocker.MagicMock(content=[mocker.MagicMock(text="ok")]))
	mock_client.messages.create = create
	mocker.patch("app.tools.llm.get_llm_client", return_value=mock_client)
	await llm.chat_complete("system text", [{"role": "user", "content": "x"}])
	kwargs = create.call_args.kwargs
	assert "system" in kwargs
	assert not any(m.get("role") == "system" for m in kwargs["messages"])


@pytest.mark.asyncio
async def test_chat_complete_uses_correct_model(mocker):
	from app.tools import llm
	from app.config import settings

	mock_client = mocker.MagicMock()
	create = mocker.AsyncMock(return_value=mocker.MagicMock(content=[mocker.MagicMock(text="ok")]))
	mock_client.messages.create = create
	mocker.patch("app.tools.llm.get_llm_client", return_value=mock_client)
	await llm.chat_complete("s", [{"role": "user", "content": "x"}])
	assert create.call_args.kwargs["model"] == settings.claude_model


@pytest.mark.asyncio
async def test_chat_complete_raises_friendly_error_on_failure(mocker):
	from app.tools import llm

	mock_client = mocker.MagicMock()
	mock_client.messages.create = mocker.AsyncMock(side_effect=Exception("anthropic boom"))
	mocker.patch("app.tools.llm.get_llm_client", return_value=mock_client)
	with pytest.raises(RuntimeError) as exc_info:
		await llm.chat_complete("s", [])
	assert "anthropic" not in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_embed_returns_1024_floats(mocker):
	from app.tools import llm

	mock_client = mocker.MagicMock()
	mock_client.embed = mocker.AsyncMock(return_value=mocker.MagicMock(embeddings=[[0.1] * 1024]))
	mocker.patch("app.tools.llm.get_voyage_client", return_value=mock_client)
	out = await llm.embed("x")
	assert len(out) == 1024


@pytest.mark.asyncio
async def test_embed_passes_correct_input_type_document(mocker):
	from app.tools import llm

	mock_client = mocker.MagicMock()
	embed_call = mocker.AsyncMock(return_value=mocker.MagicMock(embeddings=[[0.1] * 1024]))
	mock_client.embed = embed_call
	mocker.patch("app.tools.llm.get_voyage_client", return_value=mock_client)
	await llm.embed("x", input_type="document")
	assert embed_call.call_args.kwargs["input_type"] == "document"


@pytest.mark.asyncio
async def test_embed_raises_friendly_error_on_failure(mocker):
	from app.tools import llm

	mock_client = mocker.MagicMock()
	mock_client.embed = mocker.AsyncMock(side_effect=Exception("voyage boom"))
	mocker.patch("app.tools.llm.get_voyage_client", return_value=mock_client)
	with pytest.raises(RuntimeError) as exc_info:
		await llm.embed("x")
	assert "voyage" not in str(exc_info.value).lower()
