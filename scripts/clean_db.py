import asyncio
import os
import sys
from sqlalchemy import text, MetaData
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Confirm

# Add services/core_service/app to sys.path to access internal configs if needed
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIR = os.path.join(ROOT_DIR, "services", "core_service", "app")
sys.path.append(APP_DIR)

# Import DATABASE_URL from core config
try:
    from core.database import DATABASE_URL
except ImportError:
    # Fallback if path manipulation fails or run with weird context
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")

console = Console()


async def clean_database():
    """
    Cleans all rows from all database tables by reflecting the schema directly.
    Excludes migrations table and uses CASCADE TRUNCATE.
    """
    console.print("[bold yellow]⚠️  DATABASE PURGE SCRIPT ⚠️[/bold yellow]")

    if not DATABASE_URL:
        console.print(
            "[bold red]❌ DATABASE_URL not found. Ensure .env is present.[/bold red]"
        )
        sys.exit(1)

    engine = create_async_engine(DATABASE_URL)
    metadata = MetaData()

    try:
        async with engine.begin() as conn:
            # We reflect the database to find ALL actual tables
            def get_tables(connection):
                metadata.reflect(bind=connection)
                return list(metadata.tables.keys())

            # Sort tables so we don't hit obvious FK issues before CASCADE kicks in
            table_names = await conn.run_sync(get_tables)

            # Filter out alembic_version so we don't break the migration history
            tables_to_clean = [t for t in table_names if t != "alembic_version"]

            if not tables_to_clean:
                console.print(
                    "[yellow]Found no tables to clean (excluding migrations rules).[/yellow]"
                )
                return

            console.print(
                f"Found [cyan]{len(tables_to_clean)}[/cyan] tables: [cyan]{', '.join(tables_to_clean)}[/cyan]"
            )

            if not Confirm.ask(
                "[bold red]Are you sure you want to delete all rows from these tables? This cannot be undone.[/bold red]"
            ):
                console.print("[green]Cleanup task aborted.[/green]")
                return

            console.print("\n[bold]🚀 Executing purge...[/bold]")

            # PostgreSQL TRUNCATE ... CASCADE is efficient and handles FK order automatically
            for table_name in tables_to_clean:
                query = text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE;')
                await conn.execute(query)
                console.print(f"  ✅ [green]Truncated {table_name}[/green]")

        console.print(
            "\n[bold green]✨ Database successfully purged. All table identities reset.[/bold green]"
        )
    except Exception as e:
        console.print(f"\n[bold red]❌ Error during purge: {e}[/bold red]")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(clean_database())
