#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from las_to_mesh.pipeline import PipelineConfig, PipelineRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LAS->OBJ mesh pipeline")
    parser.add_argument("--config", type=Path, required=True, help="Path to pipeline YAML config")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args()

    config = PipelineConfig.from_yaml(args.config)
    runner = PipelineRunner(config)
    summary = runner.run()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
