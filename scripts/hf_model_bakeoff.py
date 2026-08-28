#!/usr/bin/env python3
"""Run the fixed DSH three-regime gate for HF Router/Baseten candidates.

This script intentionally stores only gate metadata: never model prompts,
responses, credentials, account data, or the decision ledger's free-text reason.
Run it from the repository root with ``HF_TOKEN`` set.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


CANDIDATES = (
    "moonshotai/Kimi-K3:baseten",
    "deepseek-ai/DeepSeek-V4-Pro-0813:baseten",
    "deepseek-ai/DeepSeek-V4-Flash-0731:baseten",
    "zai-org/GLM-5.3-Flash:baseten",
)
SCENARIOS = ("calm", "elevated", "stressed")
INSTRUCTION = "Select one admissible candidate and explain its trade-off."


def evaluate(repo_root: Path, model_id: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="alpaca-hf-bakeoff-") as temporary:
        root = Path(temporary)
        ledger = root / "decisions.jsonl"
        env = os.environ.copy()
        env.update(
            {
                "DSH_HOME": str(root / "dsh"),
                "DSH_PERMISSION_MODE": "read-only",
                "DSH_TELEMETRY_MODE": "DISABLED",
                "HF_MODEL_ID": model_id,
            }
        )
        cases: list[dict[str, object]] = []
        for scenario in SCENARIOS:
            completed = subprocess.run(
                [
                    str(repo_root / "deploy" / "startup.sh"),
                    "--scenario",
                    scenario,
                    "--ledger",
                    str(ledger),
                    INSTRUCTION,
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=240,
                check=False,
            )
            # Do not retain raw stdout/stderr: it may contain model output.
            cases.append({"scenario": scenario, "exit_code": completed.returncode})

        rows = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
        approved = [row for row in rows if row.get("gate", {}).get("status") == "approved_for_dry_run"]
        return {
            "model_id": model_id,
            "cases": cases,
            "approved_for_dry_run": len(approved),
            "eligible": len(cases) == len(SCENARIOS)
            and all(case["exit_code"] == 0 for case in cases)
            and len(approved) == len(SCENARIOS),
        }


def main() -> None:
    if not os.environ.get("HF_TOKEN"):
        raise SystemExit("HF_TOKEN must be supplied securely by the runner")
    repo_root = Path(__file__).resolve().parents[1]
    results = {
        "protocol": "fixed-three-regime-dsh-gate-v1",
        "provider": "baseten",
        "recorded_at": datetime.now(UTC).isoformat(),
        "candidates": [evaluate(repo_root, model_id) for model_id in CANDIDATES],
    }
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
