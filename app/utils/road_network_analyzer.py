"""
路网分析器

基于 networkx + osmnx 对 GraphML 路网数据进行：
- 读取与统计（节点数/边数/总里程/道路类型分布）
- 转换为 GeoJSON（用于前端地图预览）
- 道路等级提取与筛选
- 路网分段（按指定长度切分）
"""
import json
import math
import os
from collections import Counter
from typing import Dict, List, Optional


class RoadNetworkAnalyzer:
    """路网分析器（同步方法，调用方应在线程池中执行）"""

    @staticmethod
    def _load_graph(graphml_path: str):
        """加载 GraphML 文件为 networkx 图"""
        import networkx as nx

        if not os.path.exists(graphml_path):
            raise FileNotFoundError(f"路网文件不存在: {graphml_path}")
        return nx.read_graphml(graphml_path)

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        """计算两点间距离（米），Haversine 公式"""
        R = 6371000  # 地球半径（米）
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ═══════════════════════════════════════════
    # 统计信息
    # ═══════════════════════════════════════════

    @classmethod
    def get_info(cls, graphml_path: str) -> dict:
        """获取路网统计信息"""
        G = cls._load_graph(graphml_path)

        total_length = 0
        highway_counter = Counter()

        for u, v, data in G.edges(data=True):
            # 计算边长度
            u_attrs = G.nodes[u]
            v_attrs = G.nodes[v]
            lat1 = float(u_attrs.get("y", u_attrs.get("lat", 0)))
            lon1 = float(u_attrs.get("x", u_attrs.get("lon", 0)))
            lat2 = float(v_attrs.get("y", v_attrs.get("lat", 0)))
            lon2 = float(v_attrs.get("x", v_attrs.get("lon", 0)))
            length = cls._haversine(lat1, lon1, lat2, lon2)
            total_length += length

            highway = data.get("highway", "unclassified")
            if isinstance(highway, list):
                highway = highway[0]
            highway_counter[highway] += 1

        # 路口数 = 度数 >= 3 的节点
        junctions = sum(1 for n in G.nodes() if G.degree(n) >= 3)

        # 道路类型统计
        type_stats = [
            {"type": hw, "count": cnt, "percent": round(cnt / G.number_of_edges() * 100, 1)}
            for hw, cnt in highway_counter.most_common()
        ]

        # 路网密度（如果有面积信息则为总长/面积，否则返回总长）
        density = None
        bbox = cls._get_bbox(G)
        if bbox:
            width = cls._haversine(bbox[1], bbox[0], bbox[1], bbox[2])
            height = cls._haversine(bbox[1], bbox[0], bbox[3], bbox[0])
            area_km2 = (width * height) / 1_000_000  # m² → km²
            if area_km2 > 0:
                density = round(total_length / 1000 / area_km2, 2)  # km/km²

        return {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "junction_count": junctions,
            "total_length_m": round(total_length, 1),
            "total_length_km": round(total_length / 1000, 2),
            "density_km_per_km2": density,
            "highway_stats": type_stats,
        }

    @staticmethod
    def _get_bbox(G) -> Optional[tuple]:
        """获取路网边界框 (minlon, minlat, maxlon, maxlat)"""
        lats, lons = [], []
        for n, attrs in G.nodes(data=True):
            y = attrs.get("y", attrs.get("lat"))
            x = attrs.get("x", attrs.get("lon"))
            if y is not None and x is not None:
                lats.append(float(y))
                lons.append(float(x))
        if not lats:
            return None
        return (min(lons), min(lats), max(lons), max(lats))

    # ═══════════════════════════════════════════
    # GeoJSON 转换
    # ═══════════════════════════════════════════

    @classmethod
    def to_geojson(cls, graphml_path: str) -> dict:
        """将路网转为 GeoJSON FeatureCollection"""
        G = cls._load_graph(graphml_path)
        features = []

        for u, v, data in G.edges(data=True):
            u_attrs = G.nodes[u]
            v_attrs = G.nodes[v]
            lat1 = float(u_attrs.get("y", u_attrs.get("lat", 0)))
            lon1 = float(u_attrs.get("x", u_attrs.get("lon", 0)))
            lat2 = float(v_attrs.get("y", v_attrs.get("lat", 0)))
            lon2 = float(v_attrs.get("x", v_attrs.get("lon", 0)))

            highway = data.get("highway", "unclassified")
            if isinstance(highway, list):
                highway = highway[0]

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon1, lat1], [lon2, lat2]],
                },
                "properties": {
                    "highway": str(highway),
                    "length": data.get("length", 0),
                    "name": data.get("name", ""),
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    # ═══════════════════════════════════════════
    # 道路等级
    # ═══════════════════════════════════════════

    @classmethod
    def get_highway_types(cls, graphml_path: str) -> list:
        """获取路网中包含的道路等级列表"""
        G = cls._load_graph(graphml_path)
        types = set()
        for u, v, data in G.edges(data=True):
            hw = data.get("highway", "unclassified")
            if isinstance(hw, list):
                hw = hw[0]
            types.add(str(hw))
        return sorted(types)

    # ═══════════════════════════════════════════
    # 等级筛选
    # ═══════════════════════════════════════════

    @classmethod
    def filter_by_highway(
        cls, graphml_path: str, output_path: str, selected_types: List[str]
    ) -> dict:
        """按道路等级筛选路网，保存为新文件"""
        G = cls._load_graph(graphml_path)

        # 找出要保留的边
        edges_to_keep = []
        for u, v, data in G.edges(data=True):
            hw = data.get("highway", "unclassified")
            if isinstance(hw, list):
                hw = hw[0]
            if str(hw) in selected_types:
                edges_to_keep.append((u, v))

        # 创建子图
        G_filtered = G.edge_subgraph(edges_to_keep).copy()

        import networkx as nx
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        nx.write_graphml(G_filtered, output_path)

        return {
            "node_count": G_filtered.number_of_nodes(),
            "edge_count": G_filtered.number_of_edges(),
            "selected_types": selected_types,
            "file_path": output_path,
        }

    # ═══════════════════════════════════════════
    # 路网分段
    # ═══════════════════════════════════════════

    @classmethod
    def segment(
        cls, graphml_path: str, output_path: str, segment_length: float
    ) -> dict:
        """
        按指定长度（米）对路网边进行分段。

        每条边如果长度超过 segment_length，则沿边插值切分，
        生成新的节点和边，保留原边的属性。
        """
        import networkx as nx

        G = cls._load_graph(graphml_path)
        G_new = nx.MultiDiGraph()

        node_counter = 0
        new_edge_count = 0

        for u, v, data in G.edges(data=True):
            u_attrs = G.nodes[u]
            v_attrs = G.nodes[v]
            lat1 = float(u_attrs.get("y", u_attrs.get("lat", 0)))
            lon1 = float(u_attrs.get("x", u_attrs.get("lon", 0)))
            lat2 = float(v_attrs.get("y", v_attrs.get("lat", 0)))
            lon2 = float(v_attrs.get("x", v_attrs.get("lon", 0)))

            edge_len = cls._haversine(lat1, lon1, lat2, lon2)

            if edge_len <= segment_length:
                # 边太短，不切分
                G_new.add_node(
                    str(u), x=lon1, y=lat1,
                    **{k: v for k, v in u_attrs.items() if k not in ("x", "y")}
                )
                G_new.add_node(
                    str(v), x=lon2, y=lat2,
                    **{k: v for k, v in v_attrs.items() if k not in ("x", "y")}
                )
                G_new.add_edge(str(u), str(v), length=edge_len, from_node=str(u), to_node=str(v), **data)
                new_edge_count += 1
                continue

            # 需要切分
            segments = max(1, int(edge_len / segment_length))
            actual_seg_len = edge_len / segments
            node_ids = [str(u)]

            # 插入插值节点
            for i in range(1, segments):
                t = i / segments
                lat = lat1 + (lat2 - lat1) * t
                lon = lon1 + (lon2 - lon1) * t
                node_id = f"seg_{node_counter}"
                node_counter += 1
                G_new.add_node(node_id, x=lon, y=lat)
                node_ids.append(node_id)

            node_ids.append(str(v))

            # 添加 u 和 v
            G_new.add_node(
                str(u), x=lon1, y=lat1,
                **{k: v for k, v in u_attrs.items() if k not in ("x", "y")}
            )
            G_new.add_node(
                str(v), x=lon2, y=lat2,
                **{k: v for k, v in v_attrs.items() if k not in ("x", "y")}
            )

            # 创建分段边
            for i in range(len(node_ids) - 1):
                G_new.add_edge(
                    node_ids[i], node_ids[i + 1],
                    length=actual_seg_len,
                    from_node=node_ids[i],
                    to_node=node_ids[i + 1],
                    **data,
                )
                new_edge_count += 1

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        nx.write_graphml(G_new, output_path)

        return {
            "node_count": G_new.number_of_nodes(),
            "edge_count": G_new.number_of_edges(),
            "segment_length": segment_length,
            "file_path": output_path,
        }
