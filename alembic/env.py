from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Імпортуємо Base із моделей нашого проєкту
from online_store.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Прив'язуємо метадані для генерації міграцій
target_metadata = Base.metadata