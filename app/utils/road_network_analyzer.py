"""
路网分析器

基于 networkx 对多格式路网数据进行：
- 读取与统计（节点数/边数/总里程/道路类型分布）
- 转换为 GeoJSON（用于前端地图预览）
- 道路等级提取与筛选
- 路网分段（按指定长度切分）

支持格式：GPKG / GraphML / OSM / SHP / GeoJSON / OpenDRIVE
"""
import json
import math
import os
from collections import Counter
from typing import Dict, List, Optional


class RoadNetworkAnalyzer:
    """路网分析器（同步方法，调用方应在线程池中执行）"""

    # ── OSM highway → 中文名映射 ──
    HIGHWAY_ZH: Dict[str, str] = {
        "motorway": "高速公路",
        "motorway_link": "高速匝道",
        "trunk": "国道/快速路",
        "trunk_link": "国道匝道",
        "primary": "主干道",
        "primary_link": "主干道匝道",
        "secondary": "次干道",
        "secondary_link": "次干道匝道",
        "tertiary": "三级道路",
        "tertiary_link": "三级道路匝道",
        "residential": "居住区道路",
        "living_street": "生活街道",
        "unclassified": "未分类道路",
        "road": "道路",
        "service": "服务道路",
        "track": "乡村/农耕路",
        "path": "小径",
        "footway": "步道",
        "cycleway": "自行车道",
        "pedestrian": "步行街",
        "busway": "公交专用道",
        "bus_guideway": "导轨公交",
        "escape": "避险车道",
        "crossing": "路口",
        "steps": "台阶",
        "corridor": "走廊",
        "raceway": "赛道",
        "bridleway": "马道",
    }

    # ═══════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════

    @staticmethod
    def _sanitize_highway(hw) -> str:
        """
        净化 highway 值——去除非 [a-z_] 的字符，多值取首个。

        OSM 标准 highway 值仅包含小写字母和下划线（如 motorway, trunk_link）。
        处理三种异常：
          1. GPKG 序列化的 Python 列表字面值（如 \"['primary', 'secondary']\" → primary）
          2. OSM 分号多值（如 living_street;residential → living_street）
          3. 空值/None → unclassified
        """
        import re

        if hw is None:
            return "unclassified"
        if isinstance(hw, list):
            hw = hw[0] if hw else "unclassified"
        s = str(hw)
        # GPKG 列表字面值: \"['primary', 'secondary']\" → 提取首个元素
        m = re.match(r"^\s*\[(?:\"|')([a-z_]+)(?:\"|')", s)
        if m:
            return m.group(1)
        # 分号分隔的多值取第一个
        if ";" in s:
            s = s.split(";")[0]
        cleaned = "".join(c for c in s if c.isascii() and (c.islower() and c.isalpha() or c == "_"))
        return cleaned if cleaned else "unclassified"

    @staticmethod
    def _load_graph(file_path: str):
        """多格式路网加载器，统一返回 networkx 图"""
        import networkx as nx

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"路网文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        # ── GPKG（osmnx 保存的 GeoPackage）──
        if ext == ".gpkg":
            return RoadNetworkAnalyzer._load_gpkg(file_path)

        # ── GraphML / XML ──
        if ext in (".graphml", ".xml"):
            return nx.read_graphml(file_path)

        # ── OSM ──
        if ext == ".osm":
            try:
                import osmnx as ox
                return ox.graph_from_xml(file_path, simplify=False)
            except ImportError:
                raise RuntimeError("OSM 格式需要 osmnx: pip install osmnx")

        # ── SHP / GeoJSON → networkx 转换 ──
        if ext in (".shp", ".geojson", ".json"):
            return RoadNetworkAnalyzer._load_geodataframe_as_graph(file_path)

        # ── OpenDRIVE ──
        if ext == ".xodr":
            return RoadNetworkAnalyzer._load_opendrive(file_path)

        raise ValueError(f"不支持的路网格式: {ext}")

    @staticmethod
    def _load_gpkg(file_path: str):
        """从 OSMnx 保存的 GPKG 重建 networkx 图"""
        import geopandas as gpd
        import networkx as nx

        G = nx.MultiDiGraph()

        # 读取节点层，添加节点属性
        try:
            gdf_nodes = gpd.read_file(file_path, layer="nodes")
            for _, row in gdf_nodes.iterrows():
                osmid = row.get("osmid", _)
                y = row.geometry.y if row.geometry else None
                x = row.geometry.x if row.geometry else None
                G.add_node(osmid, y=y, x=x, lat=y, lon=x)
        except Exception:
            pass  # nodes 层可能不存在

        # 读取边层，重建边
        gdf_edges = gpd.read_file(file_path, layer="edges")
        for _, row in gdf_edges.iterrows():
            u = row.get("u")
            v = row.get("v")
            if u is None or v is None:
                continue
            k = row.get("key", 0)
            edge_data = {}
            for col in gdf_edges.columns:
                if col not in ("u", "v", "key", "geometry"):
                    val = row[col]
                    if not (isinstance(val, float) and math.isnan(val)):
                        edge_data[col] = val
            # 传递几何坐标给节点，同时保留原始几何到边属性
            geom = row.geometry
            if geom and not geom.is_empty:
                coords = list(geom.coords)
                if len(coords) >= 1:
                    G.add_node(u, y=coords[0][1], x=coords[0][0], lat=coords[0][1], lon=coords[0][0])
                if len(coords) >= 2:
                    G.add_node(v, y=coords[-1][1], x=coords[-1][0], lat=coords[-1][1], lon=coords[-1][0])
                edge_data["geometry"] = geom
            G.add_edge(u, v, key=k, **edge_data)

        if G.number_of_edges() == 0:
            raise ValueError("GPKG 文件中无有效边数据")
        return G

    @staticmethod
    def _save_gpkg(G, file_path: str, include_nodes: bool = True):
        """将 networkx 图保存为 GPKG 文件（nodes + edges layers）"""
        import geopandas as gpd
        from shapely.geometry import LineString, Point

        # ── 节点层 ──
        if include_nodes:
            nodes_data = []
            for n, attrs in G.nodes(data=True):
                y = attrs.get("y", attrs.get("lat"))
                x = attrs.get("x", attrs.get("lon"))
                if x is None or y is None:
                    continue
                row = {"osmid": n, "geometry": Point(float(x), float(y))}
                for k, v in attrs.items():
                    if k not in ("x", "y", "lat", "lon") and not (
                        isinstance(v, float) and math.isnan(v)
                    ):
                        row[k] = v
                nodes_data.append(row)

            if nodes_data:
                gdf_nodes = gpd.GeoDataFrame(nodes_data, crs="EPSG:4326")
                gdf_nodes.to_file(file_path, layer="nodes", driver="GPKG")

        # ── 边层 ──
        edges_data = []
        for edge in G.edges(data=True, keys=True):
            if len(edge) == 4:
                u, v, k, data = edge
            else:
                u, v, data = edge
                k = 0

            u_attrs = G.nodes.get(u, {})
            v_attrs = G.nodes.get(v, {})
            u_y = u_attrs.get("y", u_attrs.get("lat"))
            u_x = u_attrs.get("x", u_attrs.get("lon"))
            v_y = v_attrs.get("y", v_attrs.get("lat"))
            v_x = v_attrs.get("x", v_attrs.get("lon"))

            if u_x is None or u_y is None or v_x is None or v_y is None:
                continue

            # 优先使用边原始 geometry（含拐点），否则从端点构建直线
            raw_geom = data.pop("geometry", None)
            if raw_geom is not None and hasattr(raw_geom, "coords"):
                geom = raw_geom
            elif isinstance(raw_geom, list):
                geom = LineString(raw_geom)
            elif isinstance(raw_geom, str):
                try:
                    from shapely import wkt
                    geom = wkt.loads(raw_geom)
                except Exception:
                    geom = LineString(
                        [(float(u_x), float(u_y)), (float(v_x), float(v_y))]
                    )
            else:
                geom = LineString(
                    [(float(u_x), float(u_y)), (float(v_x), float(v_y))]
                )

            row = {
                "u": u,
                "v": v,
                "key": k,
                "geometry": geom,
            }
            for key, val in data.items():
                if not (isinstance(val, float) and math.isnan(val)):
                    row[key] = val
            edges_data.append(row)

        if edges_data:
            gdf_edges = gpd.GeoDataFrame(edges_data, crs="EPSG:4326")
            gdf_edges.to_file(file_path, layer="edges", driver="GPKG")

    @staticmethod
    def _load_geodataframe_as_graph(file_path: str):
        """从 SHP / GeoJSON 构建 networkx 图"""
        import geopandas as gpd
        import networkx as nx

        gdf = gpd.read_file(file_path)
        G = nx.MultiDiGraph()

        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            coords = list(geom.coords)
            if len(coords) >= 2:
                u, v = f"n{idx}_0", f"n{idx}_1"
                G.add_node(u, y=coords[0][1], x=coords[0][0], lat=coords[0][1], lon=coords[0][0])
                G.add_node(v, y=coords[-1][1], x=coords[-1][0], lat=coords[-1][1], lon=coords[-1][0])
                props = {k: v for k, v in row.items() if k != "geometry"
                         and not (isinstance(v, float) and math.isnan(v))}
                G.add_edge(u, v, **props)

        if G.number_of_edges() == 0:
            raise ValueError("文件无有效几何数据")
        return G

    @staticmethod
    def _load_opendrive(file_path: str):
        """OpenDRIVE (.xodr) → networkx 图"""
        import networkx as nx
        import xml.etree.ElementTree as ET

        tree = ET.parse(file_path)
        root = tree.getroot()
        ns = {"odr": "http://www.opendrive.org"}
        G = nx.MultiDiGraph()

        for road in root.findall(".//road"):
            road_id = road.attrib.get("id", "")
            plan = road.find(".//planView/geometry")
            if plan is None:
                continue
            x_start = float(plan.attrib.get("x", 0))
            y_start = float(plan.attrib.get("y", 0))
            length = float(road.attrib.get("length", 100))

            u, v = f"odr_s{road_id}", f"odr_e{road_id}"
            G.add_node(u, y=y_start, x=x_start, lat=y_start, lon=x_start)
            G.add_node(v, y=y_start + length * 0.001, x=x_start + length * 0.001,
                       lat=y_start + length * 0.001, lon=x_start + length * 0.001)
            G.add_edge(u, v, highway="road", length=length, road_id=road_id)

        if G.number_of_edges() == 0:
            raise ValueError("OpenDRIVE 文件中无有效道路")
        return G

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

            highway = cls._sanitize_highway(data.get("highway", "unclassified"))
            highway_counter[highway] += 1

        # 路口数 = 度数 >= 3 的节点
        junctions = sum(1 for n in G.nodes() if G.degree(n) >= 3)

        # 道路类型统计（含中文名）
        edge_total = G.number_of_edges()
        type_stats = [
            {
                "type": hw,
                "name_zh": cls.HIGHWAY_ZH.get(hw, hw),
                "count": cnt,
                "percent": round(cnt / edge_total * 100, 1) if edge_total > 0 else 0,
            }
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

        bbox = cls._get_bbox(G)
        return {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "junction_count": junctions,
            "total_length_m": round(total_length, 1),
            "total_length_km": round(total_length / 1000, 2),
            "density_km_per_km2": density,
            "highway_stats": type_stats,
            "bbox": bbox,
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

            highway = cls._sanitize_highway(data.get("highway", "unclassified"))

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
            hw = cls._sanitize_highway(data.get("highway", "unclassified"))
            types.add(hw)
        return sorted(types)

    # ═══════════════════════════════════════════
    # 边界提取
    # ═══════════════════════════════════════════

    @classmethod
    def extract_boundary_nodes(cls, file_path: str) -> list:
        """
        从路网图中提取所有节点的 (lon, lat) 坐标列表。

        返回: [(lon1, lat1), (lon2, lat2), ...]
        """
        G = cls._load_graph(file_path)
        points = []
        for n, attrs in G.nodes(data=True):
            y = attrs.get("y", attrs.get("lat"))
            x = attrs.get("x", attrs.get("lon"))
            if x is not None and y is not None:
                points.append((float(x), float(y)))
        if not points:
            raise ValueError("路网文件中无可提取的节点坐标")
        return points

    @staticmethod
    def compute_convex_hull(points: list) -> list:
        """
        计算点集的凸包（Convex Hull），返回组成凸包边界的点序列 (lon, lat)。

        使用 Graham Scan 算法。凸包是最小的凸多边形包含所有点。
        """
        if len(points) < 3:
            # 少于3个点直接返回
            return points

        pts = [(p[0], p[1]) for p in points]  # (lon, lat)

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        # 找到最左下角的点
        pts = sorted(set(pts))
        if len(pts) <= 1:
            return pts

        lower = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        # 去掉首尾重复点
        hull = lower[:-1] + upper[:-1]
        return hull

    @staticmethod
    def compute_concave_hull(points: list, alpha: float = 2.0) -> list:
        """
        计算点集的凹包（Concave Hull / Alpha Shape）。

        使用 Alpha Shape 算法：
        - alpha 越小，凹包越贴近实际点集形态
        - alpha 越大，凹包越趋近凸包
        - alpha 推荐值 1.5-3.0，默认 2.0

        返回: [(lon1, lat1), (lon2, lat2), ...] 边界多边形点序列
        """
        import math

        if len(points) < 3:
            return points

        pts = [(p[0], p[1]) for p in points]

        # 使用 Delaunay 三角剖分 + Alpha Shape 筛选
        try:
            from scipy.spatial import Delaunay
            import numpy as np
        except ImportError:
            # 如果没有 scipy，回退到凸包
            return RoadNetworkAnalyzer.compute_convex_hull(points)

        coords = np.array(pts)
        tri = Delaunay(coords)

        # 计算每条边的长度
        edge_set = set()
        for simplex in tri.simplices:
            for i in range(3):
                a, b = simplex[i], simplex[(i + 1) % 3]
                if a > b:
                    a, b = b, a
                edge = (a, b)
                if edge not in edge_set:
                    edge_set.add(edge)

        # Alpha shape: 保留边长 < alpha_circumference 的边
        # 对于经纬度坐标，alpha 单位为"度"（~111km/度）
        # 默认 alpha=2.0 约等于 222km 范围内的点可连接
        alpha_sq = alpha * alpha

        # 构建邻接表
        adjacency = {}
        for a, b in edge_set:
            pa, pb = coords[a], coords[b]
            dist_sq = (pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2
            if dist_sq <= alpha_sq:
                adjacency.setdefault(a, []).append(b)
                adjacency.setdefault(b, []).append(a)

        if not adjacency:
            # 没有边符合，回退到凸包
            return RoadNetworkAnalyzer.compute_convex_hull(points)

        # 从最左边的点出发，沿边界行走
        start = int(np.argmin(coords[:, 0]))
        boundary = []
        visited_edges = set()
        current = start

        while True:
            boundary.append((float(coords[current][0]), float(coords[current][1])))
            neighbors = adjacency.get(current, [])

            if not neighbors:
                break

            # 找最逆时针的下一个邻居
            if len(boundary) >= 2:
                prev = boundary[-2]
                cur = boundary[-1]
                prev_angle = math.atan2(cur[1] - prev[1], cur[0] - prev[0])

                best_neighbor = None
                best_angle = -float('inf')
                for nb in neighbors:
                    if (current, nb) in visited_edges:
                        continue
                    nb_pt = (float(coords[nb][0]), float(coords[nb][1]))
                    angle = math.atan2(nb_pt[1] - cur[1], nb_pt[0] - cur[0])
                    # 计算从 prev_angle 到 angle 的逆时针转角
                    diff = (angle - prev_angle) % (2 * math.pi)
                    if diff > best_angle:
                        best_angle = diff
                        best_neighbor = nb

                if best_neighbor is None:
                    break
                next_node = best_neighbor
            else:
                next_node = neighbors[0]

            visited_edges.add((current, next_node))
            current = next_node

            if current == start:
                boundary.append((float(coords[start][0]), float(coords[start][1])))
                break
            if len(boundary) > len(points) * 2:
                # 防止死循环
                break

        # 如果凹包顶点太少，回退到凸包
        if len(boundary) < 3:
            return RoadNetworkAnalyzer.compute_convex_hull(points)

        return boundary

    @classmethod
    def generate_boundary_gpkg(
        cls,
        file_path: str,
        output_path: str,
        method: str = "concave",
        alpha: float = 2.0,
    ) -> dict:
        """
        从路网文件提取边界并生成 GPKG 文件。

        参数:
            file_path: 路网文件路径
            output_path: 输出 GPKG 文件路径
            method: 算法 (convex / concave)
            alpha: 凹包 alpha 参数

        返回: dict with node_count, hull_point_count, method, bbox
        """
        import geopandas as gpd
        from shapely.geometry import Polygon

        # 1. 提取所有节点
        points = cls.extract_boundary_nodes(file_path)

        # 2. 计算边界多边形
        if method == "convex":
            hull_points = cls.compute_convex_hull(points)
        else:
            hull_points = cls.compute_concave_hull(points, alpha)

        # 确保多边形闭合（GeoJSON 规范）
        if hull_points and hull_points[0] != hull_points[-1]:
            hull_points.append(hull_points[0])

        # 3. 构建 Shapely Polygon（注意 GeoJSON 顺序是 lon,lat）
        polygon = Polygon(hull_points)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)  # 修复自相交

        # 4. 保存为 GPKG
        bbox = polygon.bounds  # (minx, miny, maxx, maxy)
        gdf = gpd.GeoDataFrame(
            {
                "name": [os.path.splitext(os.path.basename(file_path))[0]],
                "method": [method],
                "alpha": [alpha if method == "concave" else None],
                "node_count": [len(points)],
                "hull_point_count": [len(hull_points) - 1],  # 不含闭合点
                "geometry": [polygon],
            },
            crs="EPSG:4326",
        )
        gdf.to_file(output_path, layer="boundary", driver="GPKG")

        return {
            "node_count": len(points),
            "hull_point_count": len(hull_points) - 1,
            "method": method,
            "alpha": alpha if method == "concave" else None,
            "bbox": list(bbox),
        }

    # ═══════════════════════════════════════════
    # 等级筛选
    # ═══════════════════════════════════════════

    @classmethod
    def filter_by_highway(
        cls, graphml_path: str, output_path: str, selected_types: List[str]
    ) -> dict:
        """按道路等级筛选路网，保存为 GPKG"""
        G = cls._load_graph(graphml_path)

        # 构建筛选后的新图（直接构造，绕过 edge_subgraph 对 MultiDiGraph 的 key 要求）
        G_filtered = type(G)()
        G_filtered.add_nodes_from(G.nodes(data=True))

        for edge in G.edges(data=True, keys=True):
            # 兼容 MultiDiGraph (u,v,k,data) 和 DiGraph (u,v,data)
            if len(edge) == 4:
                u, v, k, data = edge
            else:
                u, v, data = edge
                k = 0
            hw = cls._sanitize_highway(data.get("highway", "unclassified"))
            if hw in selected_types:
                G_filtered.add_edge(u, v, key=k, **data)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cls._save_gpkg(G_filtered, output_path, include_nodes=False)

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
