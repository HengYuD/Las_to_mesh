# LAS → 轻量化 OBJ 室内结构网格管线（Blueprint + Starter）

本仓库提供一个面向 **OmniSLAM R8 背包激光扫描** 场景的后处理方案：

- 输入：单层约 `1.8 GB` 的 `.las/.laz` 点云。
- 输出：用于射线追踪仿真的、结构化且轻量化的 `OBJ` 模型。

核心目标：

1. 交互式剔除非目标区域。
2. 清理游离点与噪声。
3. 对墙面/地面/天花进行平整（打薄）与结构化约束。
4. 输出面数可控、体积更小的 OBJ。

## 推荐总体流程

1. **坐标与数据预处理**：LAS 读取、重投影、分块/下采样。
2. **区域裁剪（ROI）**：可视化框选、体素栅格+裁剪盒。
3. **离群点过滤**：统计离群 + 半径离群 + 强度阈值（可选）。
4. **平面识别与打薄**：RANSAC + 区域生长，法向统一，平面投影。
5. **结构先验修正**：
   - 地面/天花近似水平约束。
   - 墙面近似垂直约束。
   - 相邻墙体正交约束（可选，基于 Manhattan World）。
6. **网格重建**：
   - 结构面：按平面轮廓三角化。
   - 非结构件：Poisson/BPA 局部重建。
7. **模型简化与拓扑修复**：QEM decimation、孔洞修补、法线重算。
8. **导出与验证**：OBJ/MTL 导出，统计面数、包围盒、文件大小。

详见 `docs/pipeline_design_zh.md`。

## 快速开始（脚手架）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_pipeline.py --config configs/pipeline.example.yaml
```

> 当前仓库是“可落地的最小骨架”：包含模块化接口、默认配置、日志和每阶段占位实现，便于你逐步替换成生产算法。

## 目录

- `docs/pipeline_design_zh.md`：完整技术方案（中文）。
- `src/las_to_mesh/pipeline.py`：端到端处理管线。
- `src/las_to_mesh/stages.py`：各阶段处理逻辑（当前为基线实现/占位）。
- `scripts/run_pipeline.py`：CLI 入口。
- `configs/pipeline.example.yaml`：可调参数模板。

## 下一步建议

- 接入 `Open3D + laspy + pdal` 的生产级处理。
- 增加 GUI 框选（Open3D 可视化器 / Potree / CloudCompare 插件）。
- 在平面重建后引入 BIM-ish 结构约束（门窗洞口、墙厚参数化）。
- 建立“仿真可用性”验收指标（封闭性、法线一致性、面数阈值、误差阈值）。
