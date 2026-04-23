#!/usr/bin/env python3
"""Unified fault injection CLI for kill and network partition faults.

Single-node mode (--local): runs shell scripts directly on this machine.
Cluster mode: SSHes to the target node to run the scripts remotely.
"""
import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path
import yaml

FAULT_DIR = Path(__file__).parent


def _is_local(host: str) -> bool:
    try:
        target_ip = socket.gethostbyname(host)
    except socket.gaierror:
        return False
    if target_ip in ("127.0.0.1", "::1"):
        return True
    local_ips = {addr[4][0] for addr in socket.getaddrinfo(socket.gethostname(), None)}
    return target_ip in local_ips


def _ssh_run(host: str, user: str, cmd: str) -> None:
    full_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        f"{user}@{host}",
        cmd,
    ]
    subprocess.run(full_cmd, check=True)


def _local_run(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)


class FaultAgent:
    """Encapsulates fault injection for a single experiment run."""

    def __init__(self, cfg: dict, local: bool = False):
        self._cfg = cfg
        self._nodes = self._load_nodes()
        self._local = local or _is_local(self._target_node()["host"])

    def _load_nodes(self) -> list[dict]:
        nodes_path = self._cfg.get("nodes_config", "config/nodes.yaml")
        with open(nodes_path) as f:
            return yaml.safe_load(f)["nodes"]

    def _target_node(self) -> dict:
        target_id = self._cfg["failure_target_node"]
        for n in self._nodes:
            if n["id"] == target_id:
                return n
        raise ValueError(f"Node id {target_id} not found in nodes config")

    def _peer_ips(self, exclude_id: int) -> list[str]:
        return [n["host"] for n in self._nodes if n["id"] != exclude_id]

    def inject(self) -> None:
        mode = self._cfg["failure_mode"]
        if mode == "kill":
            self._kill()
        elif mode == "partition":
            self._partition()
        else:
            raise ValueError(f"Unknown failure_mode: {mode}")

    def heal(self) -> None:
        target = self._target_node()
        script = str(FAULT_DIR / "heal_node.sh")
        if self._local:
            _local_run(f"bash {script}")
        else:
            remote_script = self._upload_and_get_path(target["host"], target["ssh_user"], script)
            _ssh_run(target["host"], target["ssh_user"], f"bash {remote_script}")

    def _kill(self) -> None:
        target = self._target_node()
        script = str(FAULT_DIR / "kill_node.sh")
        if self._local:
            _local_run(f"bash {script}")
        else:
            remote_script = self._upload_and_get_path(target["host"], target["ssh_user"], script)
            _ssh_run(target["host"], target["ssh_user"], f"bash {remote_script}")

    def _partition(self) -> None:
        target = self._target_node()
        peer_ips = self._peer_ips(exclude_id=target["id"])
        script = str(FAULT_DIR / "partition_node.sh")
        peer_args = " ".join(peer_ips)
        if self._local:
            _local_run(f"bash {script} {peer_args}")
        else:
            remote_script = self._upload_and_get_path(target["host"], target["ssh_user"], script)
            _ssh_run(
                target["host"],
                target["ssh_user"],
                f"bash {remote_script} {peer_args}",
            )

    def _upload_and_get_path(self, host: str, user: str, local_script: str) -> str:
        """SCP the script to the remote node and return its remote path."""
        remote_path = f"/tmp/{Path(local_script).name}"
        scp_cmd = [
            "scp",
            "-o", "StrictHostKeyChecking=no",
            local_script,
            f"{user}@{host}:{remote_path}",
        ]
        subprocess.run(scp_cmd, check=True)
        return remote_path


def main():
    parser = argparse.ArgumentParser(description="Inject or heal faults in Qdrant nodes")
    parser.add_argument("--config", help="Experiment YAML config")
    parser.add_argument("--action", choices=["kill", "partition", "heal"], required=True)
    parser.add_argument("--target-node", type=int, default=0)
    parser.add_argument("--local", action="store_true", help="Run locally (single-node mode)")
    parser.add_argument("--nodes-config", default="config/nodes.yaml")
    args = parser.parse_args()

    if args.config:
        with open(args.config) as f:
            cfg = yaml.safe_load(f)
    else:
        cfg = {
            "failure_mode": args.action if args.action != "heal" else "kill",
            "failure_target_node": args.target_node,
            "nodes_config": args.nodes_config,
        }

    agent = FaultAgent(cfg, local=args.local)
    if args.action == "heal":
        agent.heal()
    else:
        agent.inject()


if __name__ == "__main__":
    main()
