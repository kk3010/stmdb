from __future__ import annotations

import json

import pytest


def test_load_column_docs_valid(tmp_path):
	from app.tools.chroma import load_column_docs

	p = tmp_path / "cols.json"
	p.write_text(json.dumps({"columns": [{"column_name": "a", "human_label": "A", "data_type": "VARCHAR", "description": "d"}]}), encoding="utf-8")
	out = load_column_docs(str(p))
	assert out[0]["column_name"] == "a"


def test_load_column_docs_missing_human_label_raises(tmp_path):
	from app.tools.chroma import load_column_docs

	p = tmp_path / "cols.json"
	p.write_text(json.dumps({"columns": [{"column_name": "a", "data_type": "VARCHAR", "description": "d"}]}), encoding="utf-8")
	with pytest.raises(ValueError):
		load_column_docs(str(p))


def test_load_column_docs_missing_description_raises(tmp_path):
	from app.tools.chroma import load_column_docs

	p = tmp_path / "cols.json"
	p.write_text(json.dumps({"columns": [{"column_name": "a", "human_label": "A", "data_type": "VARCHAR"}]}), encoding="utf-8")
	with pytest.raises(ValueError):
		load_column_docs(str(p))


def test_load_column_docs_file_not_found():
	from app.tools.chroma import load_column_docs

	with pytest.raises(FileNotFoundError):
		load_column_docs("missing.json")


def test_build_document_text_contains_label_and_description(sample_columns):
	from app.tools.chroma import build_document_text

	text = build_document_text(sample_columns[0])
	assert "Cost Center Code" in text
	assert "SAP-style" in text


def test_build_document_text_includes_allowed_values(sample_columns):
	from app.tools.chroma import build_document_text

	text = build_document_text(sample_columns[1])
	assert "Allowed values" in text
	assert "ACTIVE" in text


def test_build_document_text_omits_section_when_empty(sample_columns):
	from app.tools.chroma import build_document_text

	text = build_document_text(sample_columns[0])
	assert "Allowed values" not in text


@pytest.mark.asyncio
async def test_ingest_skips_when_collection_exists(mocker, sample_columns):
	from app.tools import chroma

	col = mocker.MagicMock()
	col.count.return_value = 5
	client = mocker.MagicMock()
	client.get_or_create_collection.return_value = col
	mocker.patch("app.tools.chroma.get_chroma_client", return_value=client)
	await chroma.ingest_columns(sample_columns, force=False)
	col.add.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_force_deletes_and_readds(mocker, sample_columns):
	from app.tools import chroma

	col = mocker.MagicMock()
	col.count.return_value = 0
	client = mocker.MagicMock()
	client.get_or_create_collection.return_value = col
	mocker.patch("app.tools.chroma.get_chroma_client", return_value=client)
	mocker.patch("app.tools.chroma.embed", mocker.AsyncMock(return_value=[0.1] * 1024))
	await chroma.ingest_columns(sample_columns, force=True)
	client.delete_collection.assert_called_once()
	col.add.assert_called_once()


@pytest.mark.asyncio
async def test_search_returns_correct_shape(mocker, mock_chroma_collection):
	from app.tools import chroma

	client = mocker.MagicMock()
	client.get_collection.return_value = mock_chroma_collection
	mocker.patch("app.tools.chroma.get_chroma_client", return_value=client)
	mocker.patch("app.tools.chroma.embed", mocker.AsyncMock(return_value=[0.1] * 1024))
	out = await chroma.search_columns("status")
	assert len(out) == 5
	assert "column_name" in out[0]
	assert "human_label" in out[0]
	assert 0.0 <= out[0]["similarity_score"] <= 1.0


@pytest.mark.asyncio
async def test_search_raises_helpful_error_when_no_collection(mocker):
	from app.tools import chroma

	client = mocker.MagicMock()
	client.get_collection.side_effect = Exception("missing")
	mocker.patch("app.tools.chroma.get_chroma_client", return_value=client)
	with pytest.raises(RuntimeError) as exc_info:
		await chroma.search_columns("status")
	assert "make ingest" in str(exc_info.value).lower()


def test_similarity_score_conversion():
	from app.tools.chroma import _distance_to_score

	assert _distance_to_score(0.0) == 1.0
	assert _distance_to_score(0.5) == 0.5
	assert _distance_to_score(1.5) == 0.0


@pytest.mark.asyncio
async def test_allowed_values_deserialised_as_list(mocker, mock_chroma_collection):
	from app.tools import chroma

	client = mocker.MagicMock()
	client.get_collection.return_value = mock_chroma_collection
	mocker.patch("app.tools.chroma.get_chroma_client", return_value=client)
	mocker.patch("app.tools.chroma.embed", mocker.AsyncMock(return_value=[0.1] * 1024))
	out = await chroma.search_columns("status")
	status = next(x for x in out if x["column_name"] == "status")
	assert isinstance(status["allowed_values"], list)
	assert "ACTIVE" in status["allowed_values"]
