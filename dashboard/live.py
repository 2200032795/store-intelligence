import time
import argparse
import requests
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text

console = Console()


def fetch(api_base, path):
    try:
        r = requests.get(f"{api_base}{path}", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def build_dashboard(api_base, store_id):
    metrics   = fetch(api_base, f"/stores/{store_id}/metrics")
    funnel    = fetch(api_base, f"/stores/{store_id}/funnel")
    heatmap   = fetch(api_base, f"/stores/{store_id}/heatmap")
    anomalies = fetch(api_base, f"/stores/{store_id}/anomalies")
    health    = fetch(api_base, "/health")
    now       = datetime.now().strftime("%H:%M:%S")

    # Metrics table
    m_table = Table(title=f"Store Metrics — {store_id}", border_style="blue")
    m_table.add_column("Metric",  style="cyan",  width=25)
    m_table.add_column("Value",   style="green", width=20)
    if "error" not in metrics:
        m_table.add_row("Unique Visitors",  str(metrics.get("unique_visitors", 0)))
        m_table.add_row("Conversion Rate",  f"{metrics.get('conversion_rate', 0):.1%}")
        m_table.add_row("Queue Depth",      str(metrics.get("queue_depth", 0)))
        m_table.add_row("Abandonment Rate", f"{metrics.get('abandonment_rate', 0):.1%}")
        m_table.add_row("Total POS Txns",   str(metrics.get("total_pos_txns", 0)))
    else:
        m_table.add_row("Status", "[red]API unavailable[/red]")

    # Funnel table
    f_table = Table(title="Conversion Funnel", border_style="magenta")
    f_table.add_column("Stage",    style="white",  width=16)
    f_table.add_column("Count",    style="yellow", width=8)
    f_table.add_column("% Total",  style="green",  width=10)
    f_table.add_column("Drop-off", style="red",    width=10)
    if "funnel" in funnel:
        for s in funnel["funnel"]:
            drop = f"{s.get('drop_off_pct', 0):.1f}%" if "drop_off_pct" in s else "-"
            f_table.add_row(s["stage"], str(s["count"]),
                            f"{s['pct_of_total']}%", drop)

    # Heatmap table
    h_table = Table(title="Zone Heatmap", border_style="yellow")
    h_table.add_column("Zone",      style="cyan",  width=16)
    h_table.add_column("Visits",    style="white", width=8)
    h_table.add_column("Heat",      style="red",   width=14)
    h_table.add_column("Avg Dwell", style="green", width=12)
    if "zones" in heatmap:
        for z in heatmap["zones"][:6]:
            bar = "█" * (z["normalised"] // 10)
            h_table.add_row(z["zone_id"], str(z["visit_count"]),
                            f"{bar:<10} {z['normalised']}", f"{z['avg_dwell_s']}s")

    # Anomalies table
    a_table = Table(title="Anomalies", border_style="red")
    a_table.add_column("Type",     style="white",  width=24)
    a_table.add_column("Severity", style="yellow", width=10)
    a_table.add_column("Detail",   style="cyan",   width=36)
    colors = {"CRITICAL": "red", "WARN": "yellow", "INFO": "green"}
    if "anomalies" in anomalies:
        for a in anomalies["anomalies"]:
            sev   = a.get("severity", "INFO")
            color = colors.get(sev, "white")
            a_table.add_row(a["type"],
                            f"[{color}]{sev}[/{color}]",
                            a.get("detail", "")[:36])

    # Health
    api_status = "OK" if health.get("status") == "ok" else "DEGRADED"
    db_status  = health.get("database", "unknown")
    h_panel    = Panel(
        Text(f"  API: {api_status}  |  DB: {db_status}  |  Updated: {now}  "),
        title="Health", border_style="green"
    )

    return Columns([m_table, f_table]), h_table, a_table, h_panel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store",    default="STORE_BLR_002")
    parser.add_argument("--api",      default="http://localhost:8000")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    console.print(f"\n[bold green]Store Intelligence Dashboard[/bold green]")
    console.print(f"Store: {args.store} | API: {args.api}\n")

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            try:
                from rich.console import Group
                top, heat, anom, health = build_dashboard(args.api, args.store)
                live.update(Group(top, heat, anom, health))
            except Exception as e:
                live.update(Panel(f"[red]Error: {e}[/red]"))
            time.sleep(args.interval)


if __name__ == "__main__":
    main()