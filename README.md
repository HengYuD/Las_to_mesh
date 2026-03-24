# LAS → 轻量化 OBJ 室内结构网格管线

> 面向 OmniSLAM R8 等室内激光扫描场景：将大体量 `.las/.laz` 点云转换为适合射线追踪仿真的轻量化 OBJ。

## 能力概览

当前仓库已具备可运行的端到端流程：

1. **大文件 LAS 读取**（分块读取，支持 `stride` 和 `max_points` 限流）。
2. **ROI 裁剪**（支持多 `include_boxes` 与 `exclude_boxes` 组合）。
3. **体素降采样 + 半径离群点过滤**（先降采样再过滤，控制复杂度）。
4. **地面/天花平整（打薄代理）**（按 quantile 找层面并投影）。
5. **网格重建 + 简化**（默认 `convex_hull`，支持目标面数上限）。
6. **结果导出**（OBJ + QA JSON 报告）。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 方式 1：用示例配置运行
PYTHONPATH=src python scripts/run_pipeline.py --config configs/pipeline.example.yaml
```

输出：

- `outputs/*.obj`：网格模型。
- `outputs/*_report.json`：质量统计（点数、面数、watertight、包围盒等）。

## 关键配置说明

见 `configs/pipeline.example.yaml`：

- `roi.include_boxes / exclude_boxes`：可视化框选结果可直接写入这里。
- `processing.load_stride`：大数据调速参数，建议 `1/2/4/8`。
- `processing.voxel_size`：建议 3~8cm 起步。
- `processing.outlier_radius` + `outlier_min_neighbors`：游离点过滤。
- `flattening.*`：地面/天花平整强度。
- `mesh.target_faces`：仿真预算控制核心参数。

## 工程化建议（下一步）

- 在 `PipelineStages.reconstruct_mesh` 中接入平面分割（RANSAC）+ 轮廓三角化，替换当前凸包占位。
- 将 `remove_radius_outliers` 替换为 Open3D KDTree 版本（当前 NumPy 版本为鲁棒基线，复杂度 O(N²)）。
- 增加阶段缓存（`roi.las / filtered.las / planes.json`）以支持断点恢复。

## 目录

- `docs/pipeline_design_zh.md`：完整蓝图与参数建议。
- `src/las_to_mesh/pipeline.py`：配置模型 + 流程编排。
- `src/las_to_mesh/stages.py`：各处理阶段实现。
- `scripts/run_pipeline.py`：CLI 入口。
- `configs/pipeline.example.yaml`：参数模板。
- `tests/test_pipeline_smoke.py`：最小冒烟测试。
