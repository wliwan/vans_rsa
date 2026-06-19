"""OSMnx 路网数据下载器

使用 osmnx 库从 OpenStreetMap 下载路网数据，支持两种模式：
- boundary 模式：利用已有的边界 GeoJSON 文件，提取 polygon 后下载
- name 模式：直接使用行政区名称 + 国家名搜索下载
"""

import json
import os
import ssl


class OSMnxDownloadError(Exception):
    """OSMnx 下载异常"""


class OSMnxDownloader:
    """OSMnx 路网下载器"""

    @staticmethod
    def _import_osmnx():
        try:
            import osmnx as ox
            return ox
        except ImportError:
            raise OSMnxDownloadError("osmnx 未安装，请执行: pip install osmnx")

    @classmethod
    def _setup_env(cls):
        """在线程池内：不分段下载 + SSL 配置"""
        ox = cls._import_osmnx()
        ox.settings.max_query_area_size = 50 * 1000 * 1000 * 1000  # 不分段

        # SSL 关闭时静默警告
        if os.environ.get("PYTHONHTTPSVERIFY") == "0":
            ssl._create_default_https_context = ssl._create_unverified_context
            try:
                import urllib3; urllib3.disable_warnings()
            except ImportError: pass
            try:
                import requests as _r; _r.packages.urllib3.disable_warnings()
            except ImportError: pass
        return ox

    @classmethod
    def download_by_boundary(
        cls,
        boundary_file_path: str,
        output_dir: str,
        output_name: str,
        network_type: str = "drive",
        _proxy_setup=None,
    ) -> dict:
        """模式一：通过边界 GeoJSON 文件下载路网。"""
        if _proxy_setup:
            _proxy_setup()
        ox = cls._setup_env()

        with open(boundary_file_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)
        features = geojson.get("features", [])
        if not features:
            raise OSMnxDownloadError("边界文件为空，无 features")
        geometry = features[0].get("geometry", {})
        coords = geometry.get("coordinates")
        if not coords:
            raise OSMnxDownloadError("边界文件 geometry 无坐标数据")
        geom_type = geometry.get("type", "Polygon")
        if geom_type == "MultiPolygon":
            largest = max(coords, key=lambda p: len(p[0]) if p else 0)
            polygon = largest[0] if largest else coords[0][0]
        elif geom_type == "Polygon":
            polygon = coords[0] if isinstance(coords[0][0], list) else coords
        else:
            raise OSMnxDownloadError(f"不支持的 geometry 类型: {geom_type}")

        from shapely.geometry import Polygon as ShapelyPolygon
        poly = ShapelyPolygon(polygon)
        G = ox.graph_from_polygon(poly, network_type=network_type, simplify=True)

        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{output_name}.gpkg")
        from app.utils.road_network_analyzer import RoadNetworkAnalyzer
        RoadNetworkAnalyzer._save_gpkg(G, file_path)
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
        _proxy_setup=None,
    ) -> dict:
        """模式二：通过地名搜索下载路网。"""
        if _proxy_setup:
            _proxy_setup()
        ox = cls._setup_env()

        G = ox.graph_from_place(place_name, network_type=network_type, simplify=True)
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{output_name}.gpkg")
        from app.utils.road_network_analyzer import RoadNetworkAnalyzer
        RoadNetworkAnalyzer._save_gpkg(G, file_path)
        return {
            "file_path": file_path,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        }
