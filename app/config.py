from __future__ import annotations

import logging
import sys
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.logging_utils import instrument_module_functions


class Settings(BaseSettings):
	anthropic_api_key: SecretStr
	claude_model: str = "claude-sonnet-4-6"
	claude_max_tokens: int = 4096
	voyage_api_key: SecretStr
	voyage_model: str = "voyage-3.5"
	db_host: str = "localhost"
	db_port: int = 5432
	db_name: str
	db_user: str
	db_password: SecretStr
	table_name: str
	chroma_path: str = "./chroma_db"
	column_docs_path: str = "./docs/columns.json"
	similarity_threshold: float = 0.75
	max_result_rows: int = 500
	log_path: str = "./logs/chat.log"

	@property
	def db_url(self) -> str:
		return (
			f"postgresql://{self.db_user}:"
			f"{self.db_password.get_secret_value()}"
			f"@{self.db_host}:{self.db_port}/{self.db_name}"
		)

	model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()


def setup_logging() -> logging.Logger:
	log_path = Path(settings.log_path)
	log_path.parent.mkdir(parents=True, exist_ok=True)

	root_logger = logging.getLogger()
	root_logger.handlers.clear()
	root_logger.setLevel(logging.INFO)

	formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

	file_handler = logging.FileHandler(log_path, encoding="utf-8")
	file_handler.setFormatter(formatter)

	stream_handler = logging.StreamHandler(sys.stdout)
	stream_handler.setFormatter(formatter)

	root_logger.addHandler(file_handler)
	root_logger.addHandler(stream_handler)

	return logging.getLogger("smtdb")


instrument_module_functions(globals(), logging.getLogger("smtdb.config"), exclude={"instrument_module_functions"})
