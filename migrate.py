"""Database migration management."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config
from database.base import init_database


def get_alembic_config():
    """Get Alembic configuration."""
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "migrations"))
    return alembic_cfg


def create_migration(message: str):
    """Create a new migration."""
    alembic_cfg = get_alembic_config()
    command.revision(alembic_cfg, autogenerate=True, message=message)


def run_migrations():
    """Run all pending migrations."""
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")


def rollback_migration(revision: str = "-1"):
    """Rollback to a specific revision."""
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, revision)


def show_migration_history():
    """Show migration history."""
    alembic_cfg = get_alembic_config()
    command.history(alembic_cfg)


def show_current_revision():
    """Show current revision."""
    alembic_cfg = get_alembic_config()
    command.current(alembic_cfg)


def init_db_with_migrations():
    """Initialize database and create initial migration if needed."""
    # Check if database file exists
    db_path = project_root / "storyteller.db"
    is_new_db = not db_path.exists()
    
    if is_new_db:
        print("Creating new database...")
        # Initialize database tables
        init_database()
        
        # Mark database as up to date with migrations
        alembic_cfg = get_alembic_config()
        command.stamp(alembic_cfg, "head")
        print("Database initialized and stamped with latest migration.")
    else:
        print("Database exists, running pending migrations...")
        run_migrations()
        print("Migrations completed.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration management")
    parser.add_argument("command", choices=[
        "init", "create", "migrate", "rollback", "history", "current"
    ], help="Migration command")
    parser.add_argument("--message", "-m", help="Migration message (for create)")
    parser.add_argument("--revision", "-r", help="Revision (for rollback)")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_db_with_migrations()
    elif args.command == "create":
        if not args.message:
            print("Error: --message is required for create command")
            sys.exit(1)
        create_migration(args.message)
    elif args.command == "migrate":
        run_migrations()
    elif args.command == "rollback":
        rollback_migration(args.revision or "-1")
    elif args.command == "history":
        show_migration_history()
    elif args.command == "current":
        show_current_revision()