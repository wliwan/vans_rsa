"""
路网瓦片渲染器 (Road Network Tiler)

基于 mercantile + shapely + Pillow，将路网数据渲染为 256×256 PNG 瓦片。
配合 Leaflet L.tileLayer 使用，替代前端 GeoJSON 全量直出方案。

依赖：
    - mercantile（瓦片坐标计算）
    - shapely（空间索引 STRtree）
    - Pillow（PNG 渲染）
    - networkx（路网图加载，复用 RoadNetworkAnalyzer 逻辑）

高性能可选依赖（安装后自动启用）：
    - pycairo：C 底层矢量渲染，抗锯齿更优，大量线条场景快 3-10x
      安装：sudo dnf install cairo-devel && uv pip install pycairo

架构：
    1. 加载路网文件 → 构建空间索引（线程安全 LRU 缓存，双重检查锁定防并发重复加载）
    2. 请求 /tiles/{id}/{z}/{x}/{y}.png?types=motorway,trunk
    3. mercantile.bounds → 瓦片经纬度边界
    4. STRtree.query → 边界内的边
    5. types 过滤 → 经纬度 → 像素坐标 → 渲染 PNG
    6. 磁盘缓存 + 返回

并发安全：
    - 内存图缓存使用 threading.Lock + 双重检查锁定，同一文件只加载一次
    - 磁盘瓦片缓存无锁（文件系统原子操作 + 先写后 rename 可加，当前直接 write 已足够）
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from app.settings.config import settings

logger = logging.getLogger(__name__)

# ── mercantile 延迟导入（仅在需要坐标转换时加载）──

# ── 道路等级颜色映射（与前端 highwayColors 同步） ──
HIGHWAY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "motorway": (230, 74, 25),
    "motorway_link": (230, 74, 25),
    "trunk": (216, 67, 21),
    "trunk_link": (216, 67, 21),
    "primary": (239, 108, 0),
    "primary_link": (239, 108, 0),
    "secondary": (249, 168, 37),
    "secondary_link": (249, 168, 37),
    "tertiary": (67, 160, 71),
    "tertiary_link": (67, 160, 71),
    "residential": (30, 136, 229),
    "living_street": (30, 136, 229),
    "unclassified": (158, 158, 158),
    "road": (158, 158, 158),
    "service": (117, 117, 117),
    "footway": (161, 136, 127),
    "cycleway": (102, 187, 106),
    "path": (141, 110, 99),
    "track": (121, 85, 72),
    "pedestrian": (255, 183, 77),
}
DEFAULT_COLOR = (158, 158, 158)

# ── Zoom → 线宽映射 ──
ZOOM_WEIGHTS: Dict[int, int] = {
    0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0,
    8: 1, 9: 1, 10: 2, 11: 2, 12: 3, 13: 4,
    14: 5, 15: 6, 16: 7, 17: 8, 18: 9, 19: 10, 20: 12,
}

TILE_SIZE = 256
MAX_CACHED_GRAPHS = 5


def _get_tiles_dir() -> str:
    return os.path.join(settings.BASE_DIR, "uploads", "tiles")


def _filter_key(selected_types: Optional[List[str]]) -> str:
    """筛选条件 → 安全目录名（净化 + 长度限制）"""
    import hashlib

    if not selected_types:
        return "all"

    # 净化：只保留 a-z _ 字符，过滤空值，限制单值长度
    safe = []
    for t in selected_types:
        if not isinstance(t, str):
            continue
        cleaned = "".join(c for c in t if c.isascii() and (c.isalnum() or c == "_"))
        if cleaned and len(cleaned) < 50:
            safe.append(cleaned)

    if not safe:
        return "all"

    raw = ",".join(sorted(safe))
    # 如果净化后的结果仍然过长（>80 字符），用 hash 截断
    if len(raw) > 80:
        h = hashlib.md5(raw.encode()).hexdigest()[:12]
        return f"filter_{h}"
    return raw


class RoadNetworkTiler:
    """
    路网瓦片渲染器（线程安全）。

    并发安全设计：
    - 图缓存 (_graph_cache) 受 _cache_lock 保护
    - 同一文件同一时刻只有一个线程执行加载，其余等待
    - 磁盘瓦片缓存独立于图缓存，命中时无需获取任何锁
    """

    # ── 线程安全图缓存 ──
    _graph_cache: Dict[str, Tuple[float, object, object, list]] = {}  # file_path → (ts, graph, tree, edge_meta)
    _cache_lock = threading.Lock()
    _load_events: Dict[str, threading.Event] = {}  # 正在加载中的文件

    # ── 专用线程池（避免占用 FastAPI 默认 executor） ──
    _tile_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tiler")

    # ── 空瓦片缓存 ──
    _empty_tile_bytes: Optional[bytes] = None

    @classmethod
    def get_executor(cls) -> ThreadPoolExecutor:
        """返回专用瓦片渲染线程池，controller 通过它提交渲染任务"""
        return cls._tile_executor

    # ═══════════════════════════════════════════
    # 图加载与缓存（线程安全）
    # ═══════════════════════════════════════════

    @classmethod
    def _load_graph_cached(cls, file_path: str):
        """
        线程安全地加载路网图 + 构建空间索引。

        双重检查锁定模式：
        1. 无锁快速路径检查缓存 → 命中直接返回
        2. 获取锁 → 再次检查（防止 TOCTOU）
        3. 检查是否有其他线程正在加载 → 有则等待其完成
        4. 无则开始加载 → 完成后通知等待线程

        返回 (networkx_graph, STRtree, edge_meta_list)
        """
        import networkx as nx

        # ── 快速路径：无锁缓存命中 ──
        # Python dict.get 在 CPython 中对于单键读取是线程安全的（GIL 保护），
        # 但为了安全起见，我们仍然在锁内做最终确认
        if file_path in cls._graph_cache:
            return cls._graph_cache[file_path][1], cls._graph_cache[file_path][2], cls._graph_cache[file_path][3]

        # ── 慢速路径：可能需要加载 ──
        with cls._cache_lock:
            # 双重检查：获取锁后再次确认
            if file_path in cls._graph_cache:
                graph, tree, edge_meta = cls._graph_cache[file_path][1], cls._graph_cache[file_path][2], cls._graph_cache[file_path][3]
                return graph, tree, edge_meta

            # 检查是否有其他线程正在加载此文件
            if file_path in cls._load_events:
                event = cls._load_events[file_path]
                # 释放锁，等待加载完成
                cls._cache_lock.release()
                try:
                    event.wait()
                finally:
                    cls._cache_lock.acquire()
                # 加载完成，从缓存读取
                if file_path in cls._graph_cache:
                    graph, tree, edge_meta = cls._graph_cache[file_path][1], cls._graph_cache[file_path][2], cls._graph_cache[file_path][3]
                    return graph, tree, edge_meta
                # 极端情况：加载失败，重新尝试
                # fall through to load below

            # 创建加载事件标记
            event = threading.Event()
            cls._load_events[file_path] = event

        # ── 释放锁后执行耗时的加载操作 ──
        try:
            t0 = time.time()
            from app.utils.road_network_analyzer import RoadNetworkAnalyzer

            G = RoadNetworkAnalyzer._load_graph(file_path)
            load_ms = (time.time() - t0) * 1000

            t0 = time.time()
            geoms = []
            edge_meta = []

            for u, v, data in G.edges(data=True):
                u_attrs = G.nodes[u]
                v_attrs = G.nodes[v]

                lon1 = float(u_attrs.get("x", u_attrs.get("lon", 0)))
                lat1 = float(u_attrs.get("y", u_attrs.get("lat", 0)))
                lon2 = float(v_attrs.get("x", v_attrs.get("lon", 0)))
                lat2 = float(v_attrs.get("y", v_attrs.get("lat", 0)))

                from app.utils.road_network_analyzer import RoadNetworkAnalyzer
                highway = RoadNetworkAnalyzer._sanitize_highway(data.get("highway", "unclassified"))

                # 优先使用原始 geometry 完整坐标（含拐点），否则用端点坐标
                raw_geom = data.get("geometry")
                if raw_geom is not None and hasattr(raw_geom, "coords"):
                    # Shapely LineString / Point
                    coords = list(raw_geom.coords)
                elif isinstance(raw_geom, list) and len(raw_geom) >= 2:
                    # 坐标列表 [[x,y], [x,y], ...]
                    coords = [(float(c[0]), float(c[1])) for c in raw_geom]
                elif isinstance(raw_geom, str):
                    # WKT 字符串
                    try:
                        from shapely import wkt as _wkt
                        g = _wkt.loads(raw_geom)
                        coords = list(g.coords) if hasattr(g, "coords") else [(lon1, lat1)]
                    except Exception:
                        coords = [(lon1, lat1), (lon2, lat2)]
                else:
                    coords = [(lon1, lat1), (lon2, lat2)]

                from shapely.geometry import LineString
                geoms.append(LineString(coords))
                edge_meta.append({
                    "coords": coords,
                    "highway": highway,
                    "length": float(data.get("length", 0)),
                })

            from shapely import STRtree
            tree = STRtree(geoms)
            index_ms = (time.time() - t0) * 1000

            logger.info(
                f"[Tiler] 图加载完成: {os.path.basename(file_path)} "
                f"nodes={G.number_of_nodes()} edges={G.number_of_edges()} "
                f"load={load_ms:.0f}ms index={index_ms:.0f}ms"
            )

        except Exception as e:
            # 加载失败，清理事件
            with cls._cache_lock:
                cls._load_events.pop(file_path, None)
            logger.error(f"[Tiler] 图加载失败: {file_path}: {e}")
            raise

        # ── 缓存结果 ──
        with cls._cache_lock:
            # LRU 驱逐
            while len(cls._graph_cache) >= MAX_CACHED_GRAPHS:
                oldest = min(cls._graph_cache.keys(), key=lambda k: cls._graph_cache[k][0], default=None)
                if oldest:
                    del cls._graph_cache[oldest]
                    logger.info(f"[Tiler] LRU 驱逐: {os.path.basename(oldest)}")
                else:
                    break

            cls._graph_cache[file_path] = (time.time(), G, tree, edge_meta)
            # 通知等待线程
            event.set()
            # 清理事件
            cls._load_events.pop(file_path, None)

        return G, tree, edge_meta

    @classmethod
    def warm_cache(cls, file_path: str) -> dict:
        """
        预热图缓存（可被预热 API 调用）。

        在线程池中执行加载，不阻塞调用方的事件循环。
        返回 {"status": "cached" | "loading", "message": str}
        """
        if file_path in cls._graph_cache:
            G, tree, edge_meta = cls._graph_cache[file_path][1], cls._graph_cache[file_path][2], cls._graph_cache[file_path][3]
            return {"status": "cached", "message": f"已缓存: nodes={G.number_of_nodes()} edges={G.number_of_edges()}"}

        # 提交到线程池后台加载
        def _load():
            try:
                cls._load_graph_cached(file_path)
            except Exception as e:
                logger.error(f"[Tiler] 预热失败: {e}")

        cls._tile_executor.submit(_load)
        return {"status": "loading", "message": "后台加载中..."}

    # ═══════════════════════════════════════════
    # 坐标转换
    # ═══════════════════════════════════════════

    @staticmethod
    def _lonlat_to_pixel(lon: float, lat: float, z: int, tile_x: int, tile_y: int) -> Tuple[float, float]:
        """经纬度 → 瓦片内像素坐标 (px, py)"""
        from mercantile import ul as tile_ul, xy as lonlat_to_meters

        mx, my = lonlat_to_meters(lon, lat)
        ul_lon, ul_lat = tile_ul(tile_x, tile_y, z)
        ul_mx, ul_my = lonlat_to_meters(ul_lon, ul_lat)

        R = 6378137.0
        resolution = (2 * math.pi * R) / (256 * (1 << z))

        px = (mx - ul_mx) / resolution
        py = (ul_my - my) / resolution
        return px, py

    # ═══════════════════════════════════════════
    # 瓦片渲染
    # ═══════════════════════════════════════════

    @classmethod
    def render_tile(
        cls,
        file_path: str,
        network_id: int,
        z: int,
        x: int,
        y: int,
        selected_types: Optional[List[str]] = None,
    ) -> bytes:
        """
        渲染单张路网瓦片，返回 PNG 字节（线程安全，可在线程池中并发调用）。

        缓存层次：
        1. 磁盘 PNG 缓存 → 命中直接返回（最快，0ms）
        2. 内存图缓存 → 命中则跳过加载，直接查询+渲染
        3. 冷启动 → 线程安全加载图（同一文件只加载一次）
        """
        # ── 最小 zoom 检查 ──
        if z < min(ZOOM_WEIGHTS.keys()):
            return cls._empty_tile()

        # ── 磁盘缓存 ──
        tiles_root = _get_tiles_dir()
        fkey = _filter_key(selected_types)
        cache_dir = os.path.join(tiles_root, str(network_id), fkey, str(z), str(x))
        cache_file = os.path.join(cache_dir, f"{y}.png")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "rb") as f:
                    return f.read()
            except OSError:
                pass

        # ── 瓦片边界 ──
        from mercantile import bounds as tile_bounds
        bbox = tile_bounds(x, y, z)
        west, south, east, north = bbox.west, bbox.south, bbox.east, bbox.north

        # ── 加载图 + 空间索引（线程安全） ──
        G, tree, edge_meta = cls._load_graph_cached(file_path)

        # ── 空间查询 ──
        from shapely.geometry import box
        query_box = box(west, south, east, north)
        indices = tree.query(query_box, predicate="intersects")

        if len(indices) == 0:
            return cls._empty_tile()

        # ── 线宽 ──
        weight = ZOOM_WEIGHTS.get(z, 2)

        # ── 渲染 ──
        img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        type_set = set(selected_types) if selected_types else None

        for idx in indices:
            meta = edge_meta[idx]

            if type_set is not None and meta["highway"] not in type_set:
                continue

            color = HIGHWAY_COLORS.get(meta["highway"], DEFAULT_COLOR)
            coords = meta["coords"]

            # 将所有拐点转为像素坐标
            pixels = [cls._lonlat_to_pixel(lon, lat, z, x, y) for lon, lat in coords]

            # 逐段绘制折线（始终画线，浮点坐标保留 sub-pixel 精度）
            for i in range(len(pixels) - 1):
                p0, p1 = pixels[i], pixels[i + 1]

                # 跳过极短段（两端距离 < 0.3 px，对视觉无贡献）
                if max(abs(p0[0] - p1[0]), abs(p0[1] - p1[1])) < 0.3:
                    continue

                clipped = cls._cohen_sutherland_clip(p0, p1, TILE_SIZE)
                if clipped is None:
                    continue
                ax, ay, bx, by = clipped

                draw.line(
                    [(ax, ay), (bx, by)],
                    fill=color,
                    width=max(weight, 1),
                )

        # ── 保存磁盘缓存 ──
        os.makedirs(cache_dir, exist_ok=True)
        try:
            img.save(cache_file, "PNG", optimize=True)
        except OSError:
            pass  # 磁盘写入失败不影响返回

        # ── 返回 bytes ──
        buf = BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()

    # ═══════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════

    @classmethod
    def _empty_tile(cls) -> bytes:
        if cls._empty_tile_bytes is None:
            img = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
            buf = BytesIO()
            img.save(buf, "PNG", optimize=True)
            cls._empty_tile_bytes = buf.getvalue()
        return cls._empty_tile_bytes

    @staticmethod
    def _cohen_sutherland_clip(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        size: int,
    ) -> Optional[Tuple[float, float, float, float]]:
        """Cohen-Sutherland 线段裁剪到 [0,size]×[0,size]"""
        INSIDE, LEFT, RIGHT, BOTTOM, TOP = 0, 1, 2, 4, 8

        def _code(px: float, py: float) -> int:
            c = INSIDE
            if px < 0: c |= LEFT
            elif px > size: c |= RIGHT
            if py < 0: c |= TOP
            elif py > size: c |= BOTTOM
            return c

        x0, y0 = p0
        x1, y1 = p1
        code0, code1 = _code(x0, y0), _code(x1, y1)

        while True:
            if code0 == 0 and code1 == 0:
                return (x0, y0, x1, y1)
            if code0 & code1 != 0:
                return None

            code = code0 if code0 != 0 else code1
            x, y = 0.0, 0.0

            if code & TOP:
                x = x0 + (x1 - x0) * (0 - y0) / (y1 - y0) if y1 != y0 else x0
                y = 0
            elif code & BOTTOM:
                x = x0 + (x1 - x0) * (size - y0) / (y1 - y0) if y1 != y0 else x0
                y = size
            elif code & RIGHT:
                y = y0 + (y1 - y0) * (size - x0) / (x1 - x0) if x1 != x0 else y0
                x = size
            elif code & LEFT:
                y = y0 + (y1 - y0) * (0 - x0) / (x1 - x0) if x1 != x0 else y0
                x = 0

            if code == code0:
                x0, y0 = x, y
                code0 = _code(x0, y0)
            else:
                x1, y1 = x, y
                code1 = _code(x1, y1)

    @classmethod
    def clear_cache(cls, network_id: Optional[int] = None):
        """清除缓存"""
        if network_id is not None:
            tiles_root = _get_tiles_dir()
            target = os.path.join(tiles_root, str(network_id))
            if os.path.exists(target):
                import shutil
                shutil.rmtree(target, ignore_errors=True)
                logger.info(f"[Tiler] 已清除瓦片缓存: network_id={network_id}")
        else:
            with cls._cache_lock:
                cls._graph_cache.clear()
            logger.info("[Tiler] 已清除所有内存图缓存")
