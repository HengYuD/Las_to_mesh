from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class PointCloudData:
    """Simple in-memory point cloud structure."""

    points: np.ndarray
    colors: np.ndarray | None = None


@dataclass
class MeshData:
    """Simple triangle mesh structure."""

    vertices: np.ndarray
    faces: np.ndarray


class PipelineStages:
    """Stage implementations for the LAS -> OBJ process.

    Note: methods are intentionally minimal and can be replaced with
    production implementations (Open3D/PDAL/etc.).
    """

    def load_las(self, input_path: Path) -> PointCloudData:
        import laspy

        las = laspy.read(input_path)
        points = np.column_stack((las.x, las.y, las.z)).astype(np.float64)
        return PointCloudData(points=points)

    def crop_roi(self, cloud: PointCloudData, bounds: dict[str, float]) -> PointCloudData:
        x_min, x_max = bounds["x_min"], bounds["x_max"]
        y_min, y_max = bounds["y_min"], bounds["y_max"]
        z_min, z_max = bounds["z_min"], bounds["z_max"]

        mask = (
            (cloud.points[:, 0] >= x_min)
            & (cloud.points[:, 0] <= x_max)
            & (cloud.points[:, 1] >= y_min)
            & (cloud.points[:, 1] <= y_max)
            & (cloud.points[:, 2] >= z_min)
            & (cloud.points[:, 2] <= z_max)
        )
        return PointCloudData(points=cloud.points[mask], colors=cloud.colors)

    def filter_outliers(self, cloud: PointCloudData, voxel_size: float) -> PointCloudData:
        """Baseline: voxel centroid downsample as a robust pre-filter."""

        if len(cloud.points) == 0:
            return cloud

        idx = np.floor(cloud.points / voxel_size).astype(np.int64)
        _, inv = np.unique(idx, axis=0, return_inverse=True)
        bins = np.bincount(inv)

        centroids = np.zeros((bins.size, 3), dtype=np.float64)
        np.add.at(centroids, inv, cloud.points)
        centroids /= bins[:, None]

        return PointCloudData(points=centroids)

    def flatten_structural_surfaces(
        self,
        cloud: PointCloudData,
        z_floor_quantile: float,
        z_ceiling_quantile: float,
    ) -> PointCloudData:
        """Simple flattening proxy: clamp floor/ceiling quantiles to planes."""

        if len(cloud.points) == 0:
            return cloud

        pts = cloud.points.copy()
        z_vals = pts[:, 2]
        z_floor = float(np.quantile(z_vals, z_floor_quantile))
        z_ceiling = float(np.quantile(z_vals, z_ceiling_quantile))

        floor_mask = np.isclose(z_vals, z_floor, atol=0.08)
        ceil_mask = np.isclose(z_vals, z_ceiling, atol=0.08)
        pts[floor_mask, 2] = z_floor
        pts[ceil_mask, 2] = z_ceiling

        return PointCloudData(points=pts)

    def reconstruct_mesh(self, cloud: PointCloudData) -> MeshData:
        """Produce a very lightweight hull mesh as placeholder output."""

        import trimesh

        if len(cloud.points) < 4:
            return MeshData(vertices=cloud.points, faces=np.empty((0, 3), dtype=np.int64))

        hull = trimesh.convex.convex_hull(cloud.points)
        return MeshData(vertices=np.asarray(hull.vertices), faces=np.asarray(hull.faces))

    def export_obj(self, mesh: MeshData, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for v in mesh.vertices:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for tri in mesh.faces:
                f.write(f"f {tri[0] + 1} {tri[1] + 1} {tri[2] + 1}\n")

    def summarize(self, cloud: PointCloudData, mesh: MeshData) -> dict[str, Any]:
        return {
            "point_count": int(len(cloud.points)),
            "vertex_count": int(len(mesh.vertices)),
            "face_count": int(len(mesh.faces)),
        }
