from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import chromadb

from app.config import settings
from app.logging_utils import instrument_module_functions
from app.tools.llm import embed

logger = logging.getLogger("smtdb.chroma")

COLLECTION_NAME = "cost_center_columns"
_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
	global _client
	if _client is None:
		_client = chromadb.PersistentClient(path=settings.chroma_path)
	return _client


def load_column_docs(path: str | None = None) -> list[dict]:
	docs_path = Path(path or settings.column_docs_path)
	if not docs_path.exists():
		raise FileNotFoundError(str(docs_path))

	data = json.loads(docs_path.read_text(encoding="utf-8"))
	columns = data.get("columns", [])
	required_fields = ["column_name", "human_label", "data_type", "description"]
	for entry in columns:
		for field in required_fields:
			if field not in entry:
				raise ValueError(f"Column entry missing '{field}': {entry}")
	return columns


def build_document_text(column: dict) -> str:
	text = f"{column['human_label']}: {column['description']}"
	examples = column.get("example_values") or []
	allowed_values = column.get("allowed_values") or []
	if examples:
		text += f" Examples: {', '.join(str(x) for x in examples)}."
	if allowed_values:
		text += f" Allowed values: {', '.join(str(x) for x in allowed_values)}."
	return text


def _distance_to_score(distance: float) -> float:
	return max(0.0, min(1.0, 1.0 - float(distance)))


async def ingest_columns(columns: list[dict], force: bool = False) -> None:
	client = get_chroma_client()
	if force:
		try:
			client.delete_collection(COLLECTION_NAME)
		except Exception:  # noqa: BLE001
			pass

	collection = client.get_or_create_collection(
		COLLECTION_NAME,
		metadata={"hnsw:space": "cosine"},
	)

	if collection.count() > 0 and not force:
		logger.info("Collection already populated; skipping ingestion")
		return

	ids: list[str] = []
	documents: list[str] = []
	embeddings: list[list[float]] = []
	metadatas: list[dict] = []

	for column in columns:
		doc_text = build_document_text(column)
		emb = await embed(doc_text, input_type="document")
		ids.append(column["column_name"])
		documents.append(doc_text)
		embeddings.append(emb)
		metadatas.append(
			{
				"column_name": column["column_name"],
				"human_label": column["human_label"],
				"data_type": column.get("data_type", ""),
				"nullable": str(column.get("nullable")),
				"allowed_values": json.dumps(column.get("allowed_values")),
				"description": column.get("description", ""),
			}
		)

	collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)


async def search_columns(query: str, n_results: int = 5) -> list[dict]:
	client = get_chroma_client()
	try:
		collection = client.get_collection(COLLECTION_NAME)
	except Exception as exc:  # noqa: BLE001
		raise RuntimeError("Column documentation not found. Run 'make ingest' first.") from exc

	query_embedding = await embed(query, input_type="query")
	result = collection.query(query_embeddings=[query_embedding], n_results=n_results)

	ids = result.get("ids", [[]])[0]
	docs = result.get("documents", [[]])[0]
	distances = result.get("distances", [[]])[0]
	metadatas = result.get("metadatas", [[]])[0]

	output: list[dict] = []
	for i, col_id in enumerate(ids):
		metadata = metadatas[i] if i < len(metadatas) else {}
		allowed_raw = metadata.get("allowed_values", "null")
		try:
			allowed_values = json.loads(allowed_raw) if isinstance(allowed_raw, str) else allowed_raw
		except json.JSONDecodeError:
			allowed_values = []
		if allowed_values is None:
			allowed_values = []

		output.append(
			{
				"column_name": metadata.get("column_name", col_id),
				"human_label": metadata.get("human_label", metadata.get("column_name", col_id)),
				"data_type": metadata.get("data_type"),
				"allowed_values": allowed_values,
				"description": metadata.get("description") or (docs[i] if i < len(docs) else ""),
				"similarity_score": _distance_to_score(distances[i] if i < len(distances) else 1.0),
			}
		)
	return output


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("command", choices=["ingest", "status"])
	parser.add_argument("--force", action="store_true")
	args = parser.parse_args()

	if args.command == "status":
		client = get_chroma_client()
		try:
			col = client.get_collection(COLLECTION_NAME)
			print(col.count())
		except Exception:  # noqa: BLE001
			print(0)
		return

	import asyncio

	columns = load_column_docs()
	asyncio.run(ingest_columns(columns, force=args.force))
	print("ingested")


if __name__ == "__main__":
	main()


instrument_module_functions(
	globals(),
	logger,
	exclude={"instrument_module_functions"},
	include={"ingest_columns", "search_columns"},
)
