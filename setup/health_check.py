#!/usr/bin/env python3
"""Poll Qdrant health endpoints until all nodes are healthy or timeout."""
import argparse
import sys
import time
import urllib.request
import urllib.error
import yaml


def check_node(host: str, port: int, timeout: float = 2.0) -> bool:
    url = f"http://{host}:{port}/readyz"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Check Qdrant node health")
    parser.add_argument("--config", default="config/nodes.yaml")
    parser.add_argument("--timeout", type=int, default=60, help="Max wait seconds")
    parser.add_argument("--host", help="Single host to check (overrides config)")
    parser.add_argument("--port", type=int, default=6333)
    args = parser.parse_args()

    if args.host:
        nodes = [{"host": args.host, "http_port": args.port, "id": 0}]
    else:
        with open(args.config) as f:
            cfg = yaml.safe_load(f)
        nodes = cfg["nodes"]

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        statuses = {
            n["id"]: check_node(n["host"], n.get("http_port", 6333))
            for n in nodes
        }
        all_ok = all(statuses.values())
        for node_id, ok in statuses.items():
            status = "OK" if ok else "UNREACHABLE"
            print(f"  node{node_id}: {status}")
        if all_ok:
            print("All nodes healthy.")
            sys.exit(0)
        print(f"  Retrying... ({int(deadline - time.monotonic())}s left)")
        time.sleep(2)

    print("ERROR: Timeout waiting for nodes.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
