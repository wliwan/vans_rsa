"""
OSMnx 路网数据下载器

使用 osmnx 库从 OpenStreetMap 下载路网数据，支持两种模式：

- boundary 模式：利用已有的边界 GeoJSON 文件，提取 polygon 后下载
- name 模式：直接使用行政区名称 + 国家名搜索下载

下载后以 GraphML 格式保存，并统计节点数和边数。
"""
import json
import os
from typing import Optional


class OSMnxDownloadError(Exception):
    """OSMnx 下载异常"""


class OSMnxDownloader:
    """OSMnx 路网下载器"""

    @staticmethod
    def _import_osmnx():
        """懒加载 osmnx（避免启动时就导入）"""
        try:
            import osmnx as ox
            return ox
        except ImportError:
            raise OSMnxDownloadError(
                "osmnx 未安装，请执行: pip install osmnx"
            )

    @classmethod
    def download_by_boundary(
        cls,
        boundary_file_path: str,
        output_dir: str,
        output_name: str,
        network_type: str = "drive",
    ) -> dict:
        """
        模式一：通过边界 GeoJSON 文件下载路网。

        Args:
            boundary_file_path: 边界 GeoJSON 文件路径
            output_dir: 输出目录
            output_name: 输出文件名（不含扩展名）
            network_type: 路网类型 (drive/walk/bike/all)

        Returns:
            {"file_path": ..., "node_count": ..., "edge_count": ...}
        """
        ox = cls._import_osmnx()

        # 读取边界 GeoJSON
        with open(boundary_file_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)

        # 提取 polygon
        features = geojson.get("features", [])
        if not features:
            raise OSMnxDownloadError("边界文件为空，无 features")

        # 取第一个 feature 的 geometry 作为 polygon
        geometry = features[0].get("geometry", {})
        coords = geometry.get("coordinates")

        if not coords:
            raise OSMnxDownloadError("边界文件 geometry 无坐标数据")

        # osmnx 支持 MultiPolygon 和 Polygon
        geom_type = geometry.get("type", "Polygon")
        if geom_type == "MultiPolygon":
            # 取最大的 polygon
            largest = max(coords, key=lambda p: len(p[0]) if p else 0)
            polygon = largest[0] if largest else coords[0][0]
        elif geom_type == "Polygon":
            polygon = coords[0] if isinstance(coords[0][0], list) else coords
        else:
            raise OSMnxDownloadError(f"不支持的 geometry 类型: {geom_type}")

        # 下载路网
        import geopandas
        from shapely.geometry import Polygon as ShapelyPolygon

        poly = ShapelyPolygon(polygon)
        gdf = geopandas.GeoDataFrame(index=[0], geometry=[poly], crs="EPSG:4326")

        G = ox.graph_from_polygon(poly, network_type=network_type, simplify=True)

        # 保存为 GraphML
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{output_name}.graphml")
        ox.save_graphml(G, file_path)

        return {
            "file_path": file_path,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        }

    @classmethod
    def download_by_name(
        cls,
        place_name: str,
        output_dir: str,
        output_name: str,
        network_type: str = "drive",
    ) -> dict:
        """
        模式二：通过地名搜索下载路网。

        Args:
            place_name: 地名（如 "Beijing, China"）
            output_dir: 输出目录
            output_name: 输出文件名（不含扩展名）
            network_type: 路网类型 (drive/walk/bike/all)

        Returns:
            {"file_path": ..., "node_count": ..., "edge_count": ...}
        """
        ox = cls._import_osmnx()

        G = ox.graph_from_place(place_name, network_type=network_type, simplify=True)

        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{output_name}.graphml")
        ox.save_graphml(G, file_path)

        return {
            "file_path": file_path,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        }
