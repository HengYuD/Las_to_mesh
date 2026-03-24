from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .stages import PipelineStages


@dataclass
class PipelineConfig:
    input_las: Path
    output_obj: Path
    roi_bounds: dict[str, float]
    voxel_size: float
    z_floor_quantile: float
    z_ceiling_quantile: float

    @classmethod
    def from_yaml(cls, path: Path) -> "PipelineConfig":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            input_las=Path(data["input_las"]),
            output_obj=Path(data["output_obj"]),
            roi_bounds=data["roi_bounds"],
            voxel_size=float(data.get("voxel_size", 0.05)),
            z_floor_quantile=float(data.get("z_floor_quantile", 0.02)),
            z_ceiling_quantile=float(data.get("z_ceiling_quantile", 0.98)),
        )


class PipelineRunner:
    def __init__(self, config: PipelineConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.stages = PipelineStages()
        self.logger = logger or logging.getLogger(__name__)

    def run(self) -> dict[str, Any]:
        self.logger.info("[1/6] Loading LAS: %s", self.config.input_las)
        cloud = self.stages.load_las(self.config.input_las)

        self.logger.info("[2/6] Cropping ROI")
        cloud = self.stages.crop_roi(cloud, self.config.roi_bounds)

        self.logger.info("[3/6] Filtering outliers + downsample")
        cloud = self.stages.filter_outliers(cloud, voxel_size=self.config.voxel_size)

        self.logger.info("[4/6] Flattening floor/ceiling proxy")
        cloud = self.stages.flatten_structural_surfaces(
            cloud,
            z_floor_quantile=self.config.z_floor_quantile,
            z_ceiling_quantile=self.config.z_ceiling_quantile,
        )

        self.logger.info("[5/6] Reconstructing lightweight mesh")
        mesh = self.stages.reconstruct_mesh(cloud)

        self.logger.info("[6/6] Exporting OBJ: %s", self.config.output_obj)
        self.stages.export_obj(mesh, self.config.output_obj)

        summary = self.stages.summarize(cloud, mesh)
        self.logger.info("Summary: %s", json.dumps(summary, ensure_ascii=False))
        return summary
