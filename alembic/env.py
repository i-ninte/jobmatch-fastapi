import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv
from alembic import context

# Adding project root to sys.path to make imports work
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import Base from your project
from jobmatch_fastapi.database import Base  

# Load environment variables from .env
load_dotenv()

# Alembic Config object, which provides access to .ini file in use.
config = context.config

# Set sqlalchemy URL from environment variables
database_url = os.getenv('SQLALCHEMY_DATABASE_URL')

# Debug: print the URL to check if it's loaded correctly
print(f"SQLALCHEMY_DATABASE_URL: {database_url}")

# Make sure the URL is being set properly
if not database_url:
    raise ValueError("SQLALCHEMY_DATABASE_URL not set in the environment variables")

config.set_main_option('sqlalchemy.url', database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
