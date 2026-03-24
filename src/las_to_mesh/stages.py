from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import laspy
import numpy as np
import trimesh


@dataclass
class PointCloudData:
    """In-memory point cloud plus optional metadata."""

    points: np.ndarray
    source_point_count: int


@dataclass
class MeshData:
    """Triangle mesh data and summary metadata."""

    vertices: np.ndarray
    faces: np.ndarray
    watertight: bool


class PipelineStages:
    """Production-oriented baseline stages for LAS -> simulation OBJ."""

    def load_las(
        self,
        input_path: Path,
        *,
        max_points: int | None = None,
        stride: int = 1,
    ) -> PointCloudData:
        if stride <= 0:
            raise ValueError("stride must be >= 1")

        with laspy.open(input_path) as reader:
            chunks: list[np.ndarray] = []
            raw_count = 0
            sampled_count = 0

            for chunk in reader.chunk_iterator(2_000_000):
                xyz = np.column_stack((chunk.x, chunk.y, chunk.z)).astype(np.float64)
                raw_count += len(xyz)
                sampled = xyz[::stride]

                if max_points is not None:
                    remaining = max_points - sampled_count
                    if remaining <= 0:
                        break
                    sampled = sampled[:remaining]

                if len(sampled):
                    chunks.append(sampled)
                    sampled_count += len(sampled)

            if chunks:
                points = np.concatenate(chunks, axis=0)
            else:
                points = np.empty((0, 3), dtype=np.float64)

        return PointCloudData(points=points, source_point_count=raw_count)

    def crop_roi(
        self,
        cloud: PointCloudData,
        include_boxes: list[dict[str, float]],
        exclude_boxes: list[dict[str, float]],
    ) -> PointCloudData:
        points = cloud.points
        if len(points) == 0:
            return cloud

        def mask_for_box(bounds: dict[str, float]) -> np.ndarray:
            return (
                (points[:, 0] >= bounds["x_min"])
                & (points[:, 0] <= bounds["x_max"])
                & (points[:, 1] >= bounds["y_min"])
                & (points[:, 1] <= bounds["y_max"])
                & (points[:, 2] >= bounds["z_min"])
                & (points[:, 2] <= bounds["z_max"])
            )

        if include_boxes:
            include_mask = np.zeros(len(points), dtype=bool)
            for box in include_boxes:
                include_mask |= mask_for_box(box)
        else:
            include_mask = np.ones(len(points), dtype=bool)

        exclude_mask = np.zeros(len(points), dtype=bool)
        for box in exclude_boxes:
            exclude_mask |= mask_for_box(box)

        final_mask = include_mask & ~exclude_mask
        return PointCloudData(points=points[final_mask], source_point_count=cloud.source_point_count)

    def voxel_downsample(self, cloud: PointCloudData, voxel_size: float) -> PointCloudData:
        if len(cloud.points) == 0 or voxel_size <= 0:
            return cloud

        grid = np.floor(cloud.points / voxel_size).astype(np.int64)
        _, inv = np.unique(grid, axis=0, return_inverse=True)
        counts = np.bincount(inv)

        centroids = np.zeros((len(counts), 3), dtype=np.float64)
        np.add.at(centroids, inv, cloud.points)
        centroids /= counts[:, None]
        return PointCloudData(points=centroids, source_point_count=cloud.source_point_count)

    def remove_radius_outliers(self, cloud: PointCloudData, radius: float, min_neighbors: int) -> PointCloudData:
        """Slow-but-robust NumPy baseline; replace with Open3D in production.

        Complexity O(N^2). It is acceptable only after voxel downsampling.
        """

        points = cloud.points
        if len(points) == 0 or radius <= 0:
            return cloud

        diff = points[:, None, :] - points[None, :, :]
        dist2 = np.sum(diff * diff, axis=2)
        neighbors = np.sum(dist2 <= radius * radius, axis=1) - 1
        keep = neighbors >= min_neighbors

        return PointCloudData(points=points[keep], source_point_count=cloud.source_point_count)

    def flatten_structural_surfaces(
        self,
        cloud: PointCloudData,
        z_floor_quantile: float,
        z_ceiling_quantile: float,
        flatten_band: float,
    ) -> PointCloudData:
        points = cloud.points
        if len(points) == 0:
            return cloud

        z = points[:, 2]
        floor_z = float(np.quantile(z, z_floor_quantile))
        ceiling_z = float(np.quantile(z, z_ceiling_quantile))

        floor_mask = np.abs(z - floor_z) <= flatten_band
        ceiling_mask = np.abs(z - ceiling_z) <= flatten_band

        flattened = points.copy()
        flattened[floor_mask, 2] = floor_z
        flattened[ceiling_mask, 2] = ceiling_z

        return PointCloudData(points=flattened, source_point_count=cloud.source_point_count)

    def reconstruct_mesh(self, cloud: PointCloudData, reconstruction: str = "convex_hull") -> MeshData:
        if len(cloud.points) < 4:
            return MeshData(
                vertices=cloud.points,
                faces=np.empty((0, 3), dtype=np.int64),
                watertight=False,
            )

        if reconstruction != "convex_hull":
            raise ValueError(f"Unsupported reconstruction mode: {reconstruction}")

        mesh = trimesh.convex.convex_hull(cloud.points)
        return MeshData(
            vertices=np.asarray(mesh.vertices),
            faces=np.asarray(mesh.faces),
            watertight=bool(mesh.is_watertight),
        )

    def simplify_mesh(self, mesh: MeshData, target_faces: int) -> MeshData:
        if len(mesh.faces) == 0 or target_faces <= 0 or len(mesh.faces) <= target_faces:
            return mesh

        tmesh = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces, process=False)
        try:
            simplified = tmesh.simplify_quadric_decimation(target_faces)
            return MeshData(
                vertices=np.asarray(simplified.vertices),
                faces=np.asarray(simplified.faces),
                watertight=bool(simplified.is_watertight),
            )
        except BaseException:
            # Keep pipeline robust if backend libs for simplification are unavailable.
            return mesh

    def export_obj(self, mesh: MeshData, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for v in mesh.vertices:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            for tri in mesh.faces:
                f.write(f"f {tri[0] + 1} {tri[1] + 1} {tri[2] + 1}\n")

    def summarize(self, cloud: PointCloudData, mesh: MeshData) -> dict[str, Any]:
        bbox_min = cloud.points.min(axis=0).tolist() if len(cloud.points) else [0.0, 0.0, 0.0]
        bbox_max = cloud.points.max(axis=0).tolist() if len(cloud.points) else [0.0, 0.0, 0.0]
        return {
            "source_point_count": int(cloud.source_point_count),
            "processed_point_count": int(len(cloud.points)),
            "vertex_count": int(len(mesh.vertices)),
            "face_count": int(len(mesh.faces)),
            "watertight": mesh.watertight,
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
        }
