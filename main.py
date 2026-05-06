"""
Entry point.
Run once:   python main.py --mode once
Scheduled:  python main.py --mode schedule   (runs daily at 08:00)
"""
import argparse
import schedule
import time
import asyncio
from agent.graph import build_graph


async def run_agent():
    graph = build_graph()
    initial_state = {
        "contracts_dir": "data/contracts",
        "db_path": "data/contracts.db",
        "alerts": [],
        "memos": [],
        "errors": [],
    }
    result = await graph.ainvoke(initial_state)
    print(f"[Agent] Done. Alerts sent: {len(result['alerts'])}, Memos drafted: {len(result['memos'])}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["once", "schedule"], default="once")
    args = parser.parse_args()

    if args.mode == "once":
        asyncio.run(run_agent())
    else:
        schedule.every().day.at("08:00").do(lambda: asyncio.run(run_agent()))
        print("[Scheduler] Agent scheduled daily at 08:00. Ctrl-C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    main()
