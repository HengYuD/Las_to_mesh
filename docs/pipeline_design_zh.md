# 室内 LAS 点云到仿真用轻量 OBJ：最终实现蓝图

## 1. 目标定义

输入：单层约 1.8GB 的 LAS 点云。  
输出：用于射线追踪仿真的 OBJ（结构正确、法线稳定、面数可控、文件体积小）。

验收建议：

- 几何：墙/地/顶平面残差与厚度一致性。
- 拓扑：非流形边、反法线、孔洞数量。
- 规模：三角面数、OBJ 文件大小。
- 可用性：保留围护结构、主要隔墙、主要开口。

## 2. 当前仓库可执行流程

```text
LAS(分块读取)
 -> ROI裁剪(include/exclude)
 -> 体素降采样
 -> 半径离群点过滤
 -> 地面/天花平整
 -> 网格重建(convex_hull baseline)
 -> 目标面数简化
 -> OBJ + QA report
```

与代码对应：

- 编排：`src/las_to_mesh/pipeline.py`
- 阶段实现：`src/las_to_mesh/stages.py`
- 参数：`configs/pipeline.example.yaml`

## 3. 关键实现细节

### 3.1 大文件处理

- 使用 `laspy.open(...).chunk_iterator(...)` 分块读取，避免一次性载入导致内存峰值过高。
- 支持 `load_stride` 和 `load_max_points`，用于快速调参/预览模式。

### 3.2 ROI 裁剪策略

- `include_boxes` 多盒并集。
- `exclude_boxes` 再做差集。
- 可直接承接外部可视化标注工具输出。

### 3.3 去噪与打薄

- 先做体素降采样，减少邻域计算成本。
- 半径邻域过滤去除孤立点（当前 NumPy 基线实现，生产可换 Open3D KDTree）。
- 通过 quantile 估计地面/天花高度带并执行平整投影。

### 3.4 网格与简化

- 当前基线：`convex_hull` 便于保证闭合输出与稳定导出。
- 简化：`simplify_quadric_decimation(target_faces)`，若后端不可用则自动回退原网格。

## 4. 生产化增强路线（建议）

1. 平面分割（RANSAC + 区域生长）替代凸包，输出真实墙地顶结构面。
2. 曼哈顿约束（墙体正交/平行）提升结构规整度。
3. 添加阶段缓存和可回放日志，支持批量楼层处理。
4. 构建自动验收脚本：面数上限、封闭性、法线一致性、几何误差。

## 5. 参数基线

- `voxel_size`: 0.03~0.08m
- `outlier_radius`: 0.10~0.25m
- `outlier_min_neighbors`: 2~8
- `flatten_band`: 0.03~0.10m
- `target_faces`: 50k~300k（按仿真性能预算）
