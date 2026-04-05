import httpx
import asyncio
import os
import sys
from rich.console import Console
from rich.table import Table

# Add parent directory to path to import common libs if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

CORE_SERVICE_URL = "http://127.0.0.1:8001"
EXECUTION_SERVICE_URL = "http://127.0.0.1:8002"

console = Console()

def print_positions_table(title, positions, source="MT5"):
    table = Table(title=title, show_header=True, header_style="bold blue")
    
    if source == "MT5":
        table.add_column("Ticket", justify="right")
        table.add_column("Symbol")
        table.add_column("Type")
        table.add_column("Volume", justify="right")
        table.add_column("Price", justify="right")
        
        for p in positions:
            side = "BUY" if p.get("type") == 0 else "SELL" if p.get("type") == 1 else "TRADE"
            table.add_row(
                str(p.get("ticket", "UNK")),
                p.get("symbol", "UNK"),
                side,
                str(p.get("volume", 0)),
                f"{p.get('price_open', 0):.5f}"
            )
    else: # DATABASE
        table.add_column("ID (Ticket)", justify="right")
        table.add_column("Symbol")
        table.add_column("Side")
        table.add_column("Qty", justify="right")
        table.add_column("Avg Price", justify="right")
        table.add_column("Status")
        
        for p in positions:
            side = "BUY" if p.get("type") == 0 else "SELL" if p.get("type") == 1 else "TRADE"
            status = "🟢 ACTIVE" if p.get("active_status") else "🔴 INACTIVE"
            table.add_row(
                str(p.get("id", "UNK")),
                p.get("symbol", "UNK"),
                side,
                str(p.get("quantity", 0)),
                f"{p.get('average_price', 0):.5f}",
                status
            )
            
    console.print(table)

async def sync_records():
    console.print("[bold cyan]🚀 Starting MT5-DB Record Synchronization...[/bold cyan]")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Fetch current DB state FIRST
            console.print("🔍 Fetching current Database state...")
            db_resp = await client.get(f"{CORE_SERVICE_URL}/positions/1")
            if db_resp.status_code == 200:
                print_positions_table("📊 Database Current State", db_resp.json(), source="DB")
            
            # 2. Force a refresh from MT5
            console.print("\n📡 Requesting fresh report from MT5...")
            await client.post(f"{EXECUTION_SERVICE_URL}/refresh_mt5")
            
            # Wait a bit for MT5 to respond (poll/report cycle)
            console.print("⏳ Waiting for MT5 to send report (7s)...")
            await asyncio.sleep(7)
            
            # 3. Get the latest report from Execution Service
            console.print("📥 Fetching latest report from Execution Service...")
            report_resp = await client.get(f"{EXECUTION_SERVICE_URL}/mt5/report/latest")
            if report_resp.status_code != 200:
                console.print("[bold red]❌ Failed to fetch latest report.[/bold red]")
                return
            
            mt5_positions = report_resp.json().get("positions", [])
            print_positions_table("📉 MT5 Current Terminals State", mt5_positions, source="MT5")
            
            # 4. Trigger a manual sync via Core Service
            console.print("\n⚙️ Synchronizing Core Service Database...")
            sync_resp = await client.post(
                f"{CORE_SERVICE_URL}/positions/sync",
                params={"account_id": 1},
                json=mt5_positions
            )
            
            if sync_resp.status_code == 200:
                console.print("[bold green]✨ Database successfully synchronized with MT5 state.[/bold green]")
                
                # Show final state
                final_resp = await client.get(f"{CORE_SERVICE_URL}/positions/1")
                if final_resp.status_code == 200:
                    print_positions_table("✅ Final Synchronized DB State", final_resp.json(), source="DB")
            else:
                console.print(f"[bold red]❌ Core Service Sync failed: {sync_resp.text}[/bold red]")
                
        except Exception as e:
            console.print(f"[bold red]💥 Error during synchronization: {e}[/bold red]")

if __name__ == "__main__":
    asyncio.run(sync_records())
