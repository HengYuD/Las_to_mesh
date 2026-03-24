from __future__ import annotations

import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
laspy = pytest.importorskip("laspy")

from las_to_mesh.pipeline import PipelineConfig, PipelineRunner


def _write_synthetic_las(path: Path) -> None:
    header = laspy.LasHeader(point_format=3, version="1.2")
    las = laspy.LasData(header)

    floor = np.array([[x, y, 0.0] for x in range(6) for y in range(6)], dtype=float)
    ceiling = np.array([[x, y, 3.0] for x in range(6) for y in range(6)], dtype=float)
    wall = np.array([[0.0, y, z] for y in range(6) for z in np.linspace(0, 3, 6)], dtype=float)
    noise = np.array([[30.0, 30.0, 30.0]])

    pts = np.vstack([floor, ceiling, wall, noise])
    las.x = pts[:, 0]
    las.y = pts[:, 1]
    las.z = pts[:, 2]
    las.write(path)


def test_pipeline_end_to_end(tmp_path: Path) -> None:
    input_las = tmp_path / "input.las"
    output_obj = tmp_path / "out.obj"
    output_report = tmp_path / "report.json"

    _write_synthetic_las(input_las)

    config = PipelineConfig(
        input_las=input_las,
        output_obj=output_obj,
        output_report_json=output_report,
        include_boxes=[
            {
                "x_min": -1,
                "x_max": 10,
                "y_min": -1,
                "y_max": 10,
                "z_min": -1,
                "z_max": 10,
            }
        ],
        exclude_boxes=[],
        load_max_points=None,
        load_stride=1,
        voxel_size=0.2,
        outlier_radius=0.6,
        outlier_min_neighbors=1,
        z_floor_quantile=0.02,
        z_ceiling_quantile=0.98,
        flatten_band=0.05,
        reconstruction="convex_hull",
        target_faces=1000,
    )

    summary = PipelineRunner(config).run()

    assert output_obj.exists()
    assert output_report.exists()
    assert summary["face_count"] > 0

    report = json.loads(output_report.read_text(encoding="utf-8"))
    assert report["processed_point_count"] > 0
    assert report["source_point_count"] > 0
