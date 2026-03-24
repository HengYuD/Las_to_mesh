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
    output_report_json: Path

    include_boxes: list[dict[str, float]]
    exclude_boxes: list[dict[str, float]]

    load_max_points: int | None
    load_stride: int
    voxel_size: float
    outlier_radius: float
    outlier_min_neighbors: int

    z_floor_quantile: float
    z_ceiling_quantile: float
    flatten_band: float

    reconstruction: str
    target_faces: int

    @classmethod
    def from_yaml(cls, path: Path) -> "PipelineConfig":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        roi = data.get("roi", {})
        processing = data.get("processing", {})
        flatten = data.get("flattening", {})
        mesh = data.get("mesh", {})

        return cls(
            input_las=Path(data["input_las"]),
            output_obj=Path(data["output_obj"]),
            output_report_json=Path(data.get("output_report_json", "outputs/qa_report.json")),
            include_boxes=roi.get("include_boxes", []),
            exclude_boxes=roi.get("exclude_boxes", []),
            load_max_points=processing.get("load_max_points"),
            load_stride=int(processing.get("load_stride", 1)),
            voxel_size=float(processing.get("voxel_size", 0.05)),
            outlier_radius=float(processing.get("outlier_radius", 0.15)),
            outlier_min_neighbors=int(processing.get("outlier_min_neighbors", 3)),
            z_floor_quantile=float(flatten.get("z_floor_quantile", 0.02)),
            z_ceiling_quantile=float(flatten.get("z_ceiling_quantile", 0.98)),
            flatten_band=float(flatten.get("flatten_band", 0.08)),
            reconstruction=mesh.get("reconstruction", "convex_hull"),
            target_faces=int(mesh.get("target_faces", 120_000)),
        )


class PipelineRunner:
    def __init__(self, config: PipelineConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.stages = PipelineStages()
        self.logger = logger or logging.getLogger(__name__)

    def run(self) -> dict[str, Any]:
        self.logger.info("[1/8] Loading LAS: %s", self.config.input_las)
        cloud = self.stages.load_las(
            self.config.input_las,
            max_points=self.config.load_max_points,
            stride=self.config.load_stride,
        )

        self.logger.info("[2/8] Cropping ROI")
        cloud = self.stages.crop_roi(cloud, self.config.include_boxes, self.config.exclude_boxes)

        self.logger.info("[3/8] Voxel downsample")
        cloud = self.stages.voxel_downsample(cloud, voxel_size=self.config.voxel_size)

        self.logger.info("[4/8] Radius outlier removal")
        cloud = self.stages.remove_radius_outliers(
            cloud,
            radius=self.config.outlier_radius,
            min_neighbors=self.config.outlier_min_neighbors,
        )

        self.logger.info("[5/8] Flattening floor/ceiling")
        cloud = self.stages.flatten_structural_surfaces(
            cloud,
            z_floor_quantile=self.config.z_floor_quantile,
            z_ceiling_quantile=self.config.z_ceiling_quantile,
            flatten_band=self.config.flatten_band,
        )

        self.logger.info("[6/8] Reconstructing mesh")
        mesh = self.stages.reconstruct_mesh(cloud, reconstruction=self.config.reconstruction)

        self.logger.info("[7/8] Simplifying mesh")
        mesh = self.stages.simplify_mesh(mesh, target_faces=self.config.target_faces)

        self.logger.info("[8/8] Exporting OBJ + report")
        self.stages.export_obj(mesh, self.config.output_obj)

        summary = self.stages.summarize(cloud, mesh)
        self._write_report(summary)
        self.logger.info("Summary: %s", json.dumps(summary, ensure_ascii=False))
        return summary

    def _write_report(self, summary: dict[str, Any]) -> None:
        self.config.output_report_json.parent.mkdir(parents=True, exist_ok=True)
        self.config.output_report_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
