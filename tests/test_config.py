"""Validate experiment YAML configs have required fields."""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

REQUIRED_FIELDS = [
    "experiment_id",
    "replication_factor",
    "failure_mode",
    "failure_target_node",
    "fault_injection_delay_s",
    "fault_duration_s",
    "query_rate_qps",
    "top_k",
    "recall_interval_s",
    "ground_truth_file",
    "output_dir",
]

CONFIG_DIR = Path(__file__).parent.parent / "config"
EXPERIMENT_CONFIGS = list(CONFIG_DIR.glob("experiment_*.yaml"))


@pytest.mark.parametrize("config_path", EXPERIMENT_CONFIGS)
def test_experiment_config_has_required_fields(config_path):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    missing = [field for field in REQUIRED_FIELDS if field not in cfg]
    assert not missing, f"{config_path.name} missing: {missing}"


@pytest.mark.parametrize("config_path", EXPERIMENT_CONFIGS)
def test_failure_mode_valid(config_path):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    assert cfg["failure_mode"] in ("kill", "partition"), \
        f"Invalid failure_mode in {config_path.name}: {cfg['failure_mode']}"


@pytest.mark.parametrize("config_path", EXPERIMENT_CONFIGS)
def test_replication_factor_valid(config_path):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    assert cfg["replication_factor"] in (1, 2, 3), \
        f"Unexpected RF in {config_path.name}: {cfg['replication_factor']}"
