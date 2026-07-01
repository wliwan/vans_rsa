"""全球国家及行政区 Controller"""
import json
import os
from typing import Optional

from fastapi.responses import StreamingResponse
from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import FilterTemplate, Region, RegionBoundary, RoadNetwork
from app.models.enums import (
    BoundaryStatus, BoundaryType, RegionType,
    RoadNetworkStatus, RoadNetworkType,
)
from app.schemas.regions import RegionCreate, RegionUpdate
from app.settings.config import settings
from app.utils.gadm_downloader import GADMDownloadError, GADMDownloader


class RegionController(CRUDBase[Region, RegionCreate, RegionUpdate]):
    # 类级别缓存：避免每次请求都重新加载大图
    _graph_cache: dict = {}      # {file_path: (mtime, (graph, edge_keys, fields))}

    def __init__(self):
        super().__init__(model=Region)

    async def list_regions(
        self,
        page: int = 1,
        page_size: int = 20,
        name: str = "",
        code: str = "",
        region_type: Optional[str] = None,
        parent_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ):
        q = Q()
        if name:
            q &= Q(name__contains=name) | Q(local_name__contains=name)
        if code:
            q &= Q(code__contains=code)
        if region_type:
            q &= Q(region_type=region_type)
        if parent_id is not None:
            q &= Q(parent_id=parent_id)
        if is_active is not None:
            q &= Q(is_active=is_active)

        total = await Region.filter(q).count()
        objs = await Region.filter(q).offset((page - 1) * page_size).limit(page_size).order_by("name")

        data = []
        for obj in objs:
            parent_name = None
            if obj.parent_id:
                parent = await Region.filter(id=obj.parent_id).first()
                parent_name = parent.name if parent else None
            data.append({
                "id": obj.id, "name": obj.name, "local_name": obj.local_name,
                "code": obj.code, "iso_alpha2": obj.iso_alpha2, "iso_alpha3": obj.iso_alpha3,
                "iso_numeric": obj.iso_numeric, "region_type": obj.region_type,
                "parent_id": obj.parent_id, "parent_name": parent_name,
                "capital": obj.capital, "population": obj.population,
                "area": obj.area, "latitude": obj.latitude, "longitude": obj.longitude,
                "timezone": obj.timezone, "is_active": obj.is_active,
                "created_at": obj.created_at.isoformat() if obj.created_at else None,
            })
        return total, data

    async def create_region(self, obj_in: RegionCreate):
        obj_dict = obj_in.model_dump(exclude={"parent_id"})
        if obj_in.parent_id:
            obj_dict["parent_id"] = obj_in.parent_id
        return await super().create(obj_dict)

    async def update_region(self, obj_in: RegionUpdate):
        obj_dict = obj_in.model_dump(exclude_unset=True, exclude={"id", "parent_id"})
        if obj_in.parent_id is not None:
            obj_dict["parent_id"] = obj_in.parent_id
        return await super().update(id=obj_in.id, obj_in=obj_dict)

    async def get_tree(self) -> list:
        """获取完整树结构：国家 → 行政区 → 城市"""
        countries = await Region.filter(region_type=RegionType.COUNTRY, is_active=True).order_by("name")
        result = []
        for c in countries:
            node = {
                "id": c.id, "label": c.name, "local_name": c.local_name,
                "code": c.code, "region_type": c.region_type,
                "is_active": c.is_active,
            }
            children = await self._build_children(c.id)
            if children:
                node["children"] = children
            result.append(node)
        return result

    async def _build_children(self, parent_id: int) -> list:
        children = await Region.filter(parent_id=parent_id, is_active=True).order_by("name")
        result = []
        for child in children:
            node = {
                "id": child.id, "label": child.name, "local_name": child.local_name,
                "code": child.code, "region_type": child.region_type,
                "is_active": child.is_active,
            }
            grand = await self._build_children(child.id)
            if grand:
                node["children"] = grand
            result.append(node)
        return result

    async def get_children(self, parent_id: int) -> list:
        """获取某节点的直接子节点列表"""
        children = await Region.filter(parent_id=parent_id, is_active=True).order_by("name")
        return [
            {
                "id": c.id, "name": c.name, "local_name": c.local_name,
                "code": c.code, "region_type": c.region_type,
                "parent_id": c.parent_id, "capital": c.capital,
                "is_active": c.is_active,
                "has_children": await Region.filter(parent_id=c.id, is_active=True).exists(),
            }
            for c in children
        ]

    async def import_countries(self) -> dict:
        """从 pycountry 批量导入 ISO 3166 国家 + 行政区 (STATE) + 二级行政区 (CITY) 数据"""
        try:
            import pycountry
        except ImportError:
            raise ValueError("pycountry 未安装: pip install pycountry")

        # 加载国家中文名对照表
        import json
        import os
        zh_map_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "utils", "country_zh_map.json"
        )
        try:
            with open(zh_map_path, "r", encoding="utf-8") as f:
                zh_map: dict[str, str] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"无法加载国家中文名对照表: {e}，local_name 将为 None")
            zh_map = {}

        created_country = 0
        updated_country = 0
        created_state = 0
        created_city = 0
        skipped_state = 0
        skipped_city = 0

        # ── Step 1: 导入国家 ──
        country_map: dict[str, int] = {}  # alpha2 → region_id
        for country in pycountry.countries:
            name = getattr(country, "name", "")
            alpha2 = getattr(country, "alpha_2", "")
            alpha3 = getattr(country, "alpha_3", "")
            numeric = getattr(country, "numeric", "")
            if not name or not alpha2:
                continue

            existing = await Region.filter(code=alpha2, region_type=RegionType.COUNTRY).first()
            data = {
                "name": name, "code": alpha2,
                "iso_alpha2": alpha2, "iso_alpha3": alpha3, "iso_numeric": numeric,
                "region_type": RegionType.COUNTRY,
                "local_name": zh_map.get(alpha2),
            }
            if existing:
                await existing.update_from_dict(data).save()
                country_map[alpha2] = existing.id
                updated_country += 1
            else:
                obj = await Region.create(**data)
                country_map[alpha2] = obj.id
                created_country += 1

        # ── Step 2: 分类 subdivisions ──
        state_subs = []   # 无 parent_code → STATE 一级行政区
        city_subs = []    # 有 parent_code → CITY 二级行政区
        for sub in pycountry.subdivisions:
            code = getattr(sub, "code", "")
            if not code:
                continue
            if getattr(sub, "parent_code", None):
                city_subs.append(sub)
            else:
                state_subs.append(sub)

        # ── Step 3: 导入一级行政区 (STATE) ──
        state_map: dict[str, int] = {}  # subdivision.code → region_id
        for sub in state_subs:
            code = getattr(sub, "code", "")
            name = getattr(sub, "name", "")
            country_code = getattr(sub, "country_code", "")
            if not name or not code or country_code not in country_map:
                skipped_state += 1
                continue

            existing = await Region.filter(
                code=code, region_type=RegionType.STATE, parent_id=country_map[country_code]
            ).first()

            data = {
                "name": name, "code": code,
                "region_type": RegionType.STATE,
                "parent_id": country_map[country_code],
            }
            if existing:
                await existing.update_from_dict(data).save()
                state_map[code] = existing.id
            else:
                obj = await Region.create(**data)
                state_map[code] = obj.id
                created_state += 1

        # ── Step 4: 导入二级行政区 (CITY) ──
        for sub in city_subs:
            code = getattr(sub, "code", "")
            name = getattr(sub, "name", "")
            parent_code = getattr(sub, "parent_code", "")
            if not name or not code or not parent_code:
                skipped_city += 1
                continue

            parent_id = state_map.get(parent_code)
            if parent_id is None:
                # 直接查数据库兜底
                parent_obj = await Region.filter(
                    code=parent_code, region_type=RegionType.STATE
                ).first()
                if parent_obj:
                    parent_id = parent_obj.id
                    state_map[parent_code] = parent_id

            if parent_id is None:
                skipped_city += 1
                continue

            existing = await Region.filter(
                code=code, region_type=RegionType.CITY, parent_id=parent_id
            ).first()

            data = {
                "name": name, "code": code,
                "region_type": RegionType.CITY,
                "parent_id": parent_id,
            }
            if existing:
                await existing.update_from_dict(data).save()
            else:
                await Region.create(**data)
                created_city += 1

        logger.info(
            f"导入完成: country=+{created_country}/~{updated_country}, "
            f"state={created_state}, city={created_city}, "
            f"skip_state={skipped_state}, skip_city={skipped_city}"
        )

        # ── Step 5: 自动回填 STATE/CITY 中文名（优先使用离线缓存）──
        geonames_fill = {}
        try:
            from app.utils.geonames_downloader import GeoNamesChineseDownloader

            downloader = GeoNamesChineseDownloader()
            cached = downloader.load_cache()
            if cached:
                geonames_fill = await downloader.fill_local_names(force_download=False)
                logger.info(f"GeoNames 回填完成: {geonames_fill}")
            else:
                logger.info(
                    "GeoNames 离线缓存缺失，跳过 STATE/CITY 中文名填充。"
                    "如需填充，请运行: python -m app.utils.geonames_downloader"
                )
        except Exception as e:
            logger.warning(f"GeoNames 回填失败: {e}")

        return {
            "created_country": created_country,
            "updated_country": updated_country,
            "created_state": created_state,
            "created_city": created_city,
            "skipped_state": skipped_state,
            "skipped_city": skipped_city,
            "geonames": geonames_fill,
        }

    async def clear_all(self) -> int:
        """清空全部数据"""
        count = await Region.all().count()
        await Region.all().delete()
        logger.info(f"全部清空: deleted={count}")
        return count

    async def export_data(self, country_id: int, level: str) -> list:
        """导出某个国家的数据到指定级别"""
        country = await Region.filter(id=country_id, region_type=RegionType.COUNTRY).first()
        if not country:
            raise ValueError("国家不存在")

        def _serialize(obj):
            return {
                "id": obj.id, "name": obj.name, "local_name": obj.local_name,
                "code": obj.code, "iso_alpha2": obj.iso_alpha2, "iso_alpha3": obj.iso_alpha3,
                "iso_numeric": obj.iso_numeric, "region_type": obj.region_type,
                "parent_id": obj.parent_id, "capital": obj.capital,
                "population": obj.population, "area": obj.area,
                "latitude": obj.latitude, "longitude": obj.longitude,
                "timezone": obj.timezone,
            }

        result = []
        children = await Region.filter(parent_id=country_id, is_active=True).order_by("name")

        for child in children:
            item = _serialize(child)
            if level in ("ALL", "CITY"):
                cities = await Region.filter(parent_id=child.id, is_active=True).order_by("name")
                if cities:
                    item["children"] = [_serialize(c) for c in cities]
            result.append(item)

        if level == "ALL":
            return [_serialize(country)] + result
        return result

    async def batch_update(self, updates: list) -> dict:
        """批量更新"""
        updated = 0
        for item in updates:
            rid = item.get("id")
            if not rid:
                continue
            obj = await Region.filter(id=rid).first()
            if obj:
                await obj.update_from_dict(item).save()
                updated += 1
        logger.info(f"批量更新: updated={updated}")
        return {"updated": updated}

    async def fill_geonames(self, force_download: bool = False,
                            proxy: str | None = None) -> dict:
        """填充 STATE/CITY 的中文名（来自 GeoNames）

        首次调用会下载约 700MB 数据（3-10 分钟），后续使用离线缓存秒级完成。
        proxy: 可选代理地址，如 http://127.0.0.1:7890
        """
        try:
            from app.utils.geonames_downloader import fill_region_local_names

            result = await fill_region_local_names(
                force_download=force_download, proxy=proxy
            )
            logger.info(f"GeoNames 填充结果: {result}")
            return result
        except Exception as e:
            logger.error(f"GeoNames 填充失败: {e}")
            raise

    @staticmethod
    def get_geonames_progress() -> dict:
        """查询 GeoNames 下载进度"""
        try:
            from app.utils.geonames_downloader import get_progress
            return get_progress()
        except ImportError:
            return {"status": "idle", "progress": 0, "message": ""}

    # ── Boundary 边界文件管理 ──

    async def _get_country_iso3(self, region) -> str:
        """向上追溯找到区域所属国家的 iso_alpha3"""
        current = region
        while current:
            if current.region_type == RegionType.COUNTRY and current.iso_alpha3:
                return current.iso_alpha3
            if current.parent_id:
                current = await Region.filter(id=current.parent_id).first()
            else:
                break
        raise ValueError(f"区域「{region.name}」无法找到所属国家的 ISO Alpha-3 代码")

    async def get_boundary_status(self, region_id: int) -> dict:
        """检查区域的边界文件下载状态及列表"""
        boundaries = await RegionBoundary.filter(
            region_id=region_id, is_active=True
        ).order_by("-created_at")

        items = []
        has_success = False
        for b in boundaries:
            items.append({
                "id": b.id,
                "file_name": b.file_name,
                "file_type": b.file_type,
                "file_size": b.file_size,
                "srid": b.srid,
                "download_status": b.download_status,
                "error_message": b.error_message,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            })
            if b.download_status == BoundaryStatus.SUCCESS:
                has_success = True

        return {
            "region_id": region_id,
            "has_boundary": has_success,
            "count": len(items),
            "files": items,
        }

    async def download_boundary(self, region_id: int, file_type: str = "GEOJSON") -> dict:
        """从 GADM 下载行政区的边界 GeoJSON 数据"""
        import time

        region = await Region.filter(id=region_id).first()
        if not region:
            raise ValueError("区域不存在")

        # 找到所属国家的 ISO Alpha-3
        iso_alpha3 = await self._get_country_iso3(region)

        # 创建下载中记录
        boundary = await RegionBoundary.create(
            region_id=region_id,
            file_name=f"{region.name}_{region.region_type}.geojson",
            file_type=BoundaryType.GEOJSON,
            file_path="",
            download_status=BoundaryStatus.DOWNLOADING,
        )

        try:
            # 调用 GADM 下载器（大国家/省级数据可能较慢，超时设为 5 分钟）
            geojson_data, source_url = await GADMDownloader.download(
                iso_alpha3=iso_alpha3,
                region_type=region.region_type,
                timeout=300.0,
            )

            # 保存到文件
            upload_dir = os.path.join(settings.BASE_DIR, "uploads", "boundaries")
            os.makedirs(upload_dir, exist_ok=True)

            file_name = f"{iso_alpha3}_{region.region_type}_{int(time.time())}.geojson"
            file_path = os.path.join(upload_dir, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(geojson_data, f, ensure_ascii=False)

            file_size = os.path.getsize(file_path)

            # 更新记录为成功
            boundary.file_path = file_path
            boundary.file_size = file_size
            boundary.srid = "EPSG:4326"
            boundary.download_status = BoundaryStatus.SUCCESS
            await boundary.save()

            feature_count = len(geojson_data.get("features", []))
            logger.info(f"GADM 边界下载成功: {iso_alpha3} level={region.region_type} features={feature_count}")

            return {
                "id": boundary.id,
                "file_name": boundary.file_name,
                "file_type": boundary.file_type,
                "file_size": file_size,
                "download_status": "SUCCESS",
            }

        except GADMDownloadError as e:
            logger.error(f"GADM 下载边界失败 region_id={region_id}: {e}")
            boundary.download_status = BoundaryStatus.FAILED
            boundary.error_message = str(e)[:500]
            await boundary.save()
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"下载边界文件失败 region_id={region_id}: {e}")
            boundary.download_status = BoundaryStatus.FAILED
            boundary.error_message = str(e)[:500]
            await boundary.save()
            raise ValueError(f"下载失败: {e}")

    async def upload_boundary(self, region_id: int, file_content: bytes, file_name: str) -> dict:
        """上传边界文件"""
        import os
        import time

        region = await Region.filter(id=region_id).first()
        if not region:
            raise ValueError("区域不存在")

        ext = os.path.splitext(file_name)[1].lower()
        if ext == ".geojson" or ext == ".json":
            file_type = BoundaryType.GEOJSON
        elif ext == ".kml":
            file_type = BoundaryType.KML
        elif ext == ".shp":
            file_type = BoundaryType.SHP
        else:
            file_type = BoundaryType.GEOJSON

        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "boundaries")
        os.makedirs(upload_dir, exist_ok=True)

        saved_name = f"{region_id}_{int(time.time())}{ext}"
        file_path = os.path.join(upload_dir, saved_name)

        with open(file_path, "wb") as f:
            f.write(file_content)

        file_size = os.path.getsize(file_path)

        boundary = await RegionBoundary.create(
            region_id=region_id,
            file_name=file_name,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size,
            srid="EPSG:4326",
            download_status=BoundaryStatus.SUCCESS,
        )

        return {
            "id": boundary.id,
            "file_name": boundary.file_name,
            "file_type": boundary.file_type,
            "file_size": file_size,
            "download_status": "SUCCESS",
        }

    async def delete_boundary(self, boundary_id: int):
        """删除单个边界文件"""
        boundary = await RegionBoundary.filter(id=boundary_id).first()
        if not boundary:
            raise ValueError("边界文件不存在")
        # 删除物理文件
        if boundary.file_path and os.path.exists(boundary.file_path):
            os.remove(boundary.file_path)
        await boundary.delete()

    async def clear_boundaries(self, region_id: int) -> int:
        """清除指定区域的所有边界文件"""
        boundaries = await RegionBoundary.filter(region_id=region_id)
        count = 0
        for b in boundaries:
            if b.file_path and os.path.exists(b.file_path):
                os.remove(b.file_path)
            await b.delete()
            count += 1
        return count

    async def export_boundary(self, boundary_id: int) -> tuple:
        """导出边界文件，返回 (file_path, file_name, media_type)"""
        boundary = await RegionBoundary.filter(id=boundary_id).first()
        if not boundary:
            raise ValueError("边界文件不存在")
        if not boundary.file_path or not os.path.exists(boundary.file_path):
            raise ValueError("边界文件未找到")

        if boundary.file_type == BoundaryType.GEOJSON:
            media_type = "application/geo+json"
        elif boundary.file_type == BoundaryType.KML:
            media_type = "application/vnd.google-earth.kml+xml"
        else:
            media_type = "application/octet-stream"

        return boundary.file_path, boundary.file_name, media_type


    # ── RoadNetwork 路网文件管理 ──

    async def get_road_network_status(self, region_id: int) -> dict:
        """检查区域的路网文件下载状态及列表"""
        networks = await RoadNetwork.filter(
            region_id=region_id, is_active=True
        ).order_by("-created_at")

        items = []
        has_success = False
        for n in networks:
            items.append({
                "id": n.id,
                "file_name": n.file_name,
                "file_type": n.file_type,
                "file_size": n.file_size,
                "node_count": n.node_count,
                "edge_count": n.edge_count,
                "srid": n.srid,
                "download_mode": n.download_mode,
                "download_status": n.download_status,
                "error_message": n.error_message,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            })
            if n.download_status == RoadNetworkStatus.SUCCESS:
                has_success = True

        return {
            "region_id": region_id,
            "has_network": has_success,
            "count": len(items),
            "files": items,
        }

    async def download_road_network(
        self, region_id: int, mode: str = "boundary", file_type: str = "GPKG"
    ) -> dict:
        """从 OSM 下载路网数据（在线程池中执行同步 osmnx，避免阻塞事件循环）"""
        import asyncio
        import functools
        import time

        from app.utils.osmnx_downloader import OSMnxDownloadError, OSMnxDownloader

        region = await Region.filter(id=region_id).first()
        if not region:
            raise ValueError("区域不存在")

        # 创建下载中记录
        network = await RoadNetwork.create(
            region_id=region_id,
            file_name=f"{region.name}.gpkg",
            file_type=RoadNetworkType.GPKG,
            file_path="",
            download_mode=mode,
            download_status=RoadNetworkStatus.DOWNLOADING,
        )

        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "road_networks")
        output_name = f"{region_id}_{int(time.time())}"

        # 从系统配置读取代理和 SSL 设置
        import os as _os
        proxy_url = None
        ssl_verify = True
        try:
            from app.controllers.system_config import system_config_controller
            proxy_url = await system_config_controller.get_value("download_proxy", "")
            ssl_val = await system_config_controller.get_value("download_ssl_verify", "true")
            ssl_verify = str(ssl_val).lower() != "false"
        except Exception:
            pass

        def _set_proxy():
            """在线程池内临时设置代理和 SSL 验证参数"""
            if proxy_url:
                _os.environ["HTTPS_PROXY"] = proxy_url
                _os.environ["HTTP_PROXY"] = proxy_url
                # 只排除本地回环，Overpass 走代理
                _os.environ["NO_PROXY"] = "localhost,127.0.0.1"
                logger.info(f"OSMnx 使用代理: {proxy_url}")
            else:
                _os.environ.pop("HTTPS_PROXY", None)
                _os.environ.pop("HTTP_PROXY", None)
                _os.environ.pop("NO_PROXY", None)
            # SSL 验证配置：强制 requests 禁用验证（patch ssl 模块对已初始化连接无效）
            if not ssl_verify:
                import ssl as _ssl
                _ssl._create_default_https_context = _ssl._create_unverified_context
                _os.environ["PYTHONHTTPSVERIFY"] = "0"
                _os.environ["CURL_CA_BUNDLE"] = ""
                _os.environ["REQUESTS_CA_BUNDLE"] = ""
                # 全局禁用 requests 的 SSL 验证（在线程池内 osmnx 调用前生效）
                import requests as _req
                _req.packages.urllib3.disable_warnings()
                # Monkey-patch Session.send 强制 verify=False
                if not hasattr(_req.Session, '_patched_verify'):
                    _orig_send = _req.Session.send
                    def _patched_send(self, request, **kwargs):
                        kwargs['verify'] = False
                        return _orig_send(self, request, **kwargs)
                    _req.Session.send = _patched_send
                    _req.Session._patched_verify = True
                logger.warning("SSL 证书验证已关闭（download_ssl_verify=false）")
            else:
                _os.environ.pop("PYTHONHTTPSVERIFY", None)
                _os.environ.pop("CURL_CA_BUNDLE", None)
                _os.environ.pop("REQUESTS_CA_BUNDLE", None)

        try:
            if mode == "boundary":
                # 模式一：通过边界文件下载
                boundary = await RegionBoundary.filter(
                    region_id=region_id, download_status=BoundaryStatus.SUCCESS
                ).first()
                if not boundary or not boundary.file_path:
                    raise ValueError("该区域暂无已下载的边界文件，请先下载边界或使用 name 模式")

                # 在线程池中执行同步 osmnx 操作，避免阻塞事件循环
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    functools.partial(
                        OSMnxDownloader.download_by_boundary,
                        boundary_file_path=boundary.file_path,
                        output_dir=upload_dir,
                        output_name=output_name,
                        _proxy_setup=_set_proxy,
                    ),
                )
            else:
                # 模式二：通过地名搜索下载
                iso_alpha3 = await self._get_country_iso3(region)
                country = await Region.filter(
                    iso_alpha3=iso_alpha3, region_type=RegionType.COUNTRY
                ).first()
                place_name = f"{region.name}, {country.name if country else ''}"

                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    functools.partial(
                        OSMnxDownloader.download_by_name,
                        place_name=place_name,
                        output_dir=upload_dir,
                        output_name=output_name,
                        _proxy_setup=_set_proxy,
                    ),
                )

            file_path = result["file_path"]
            file_size = os.path.getsize(file_path)

            network.file_path = file_path
            network.file_size = file_size
            network.node_count = result["node_count"]
            network.edge_count = result["edge_count"]
            network.srid = "EPSG:4326"
            network.download_status = RoadNetworkStatus.SUCCESS
            await network.save()

            logger.info(
                f"路网下载成功: region={region.name} mode={mode} "
                f"nodes={result['node_count']} edges={result['edge_count']}"
            )

            return {
                "id": network.id,
                "file_name": network.file_name,
                "file_type": network.file_type,
                "file_size": file_size,
                "node_count": result["node_count"],
                "edge_count": result["edge_count"],
                "download_mode": mode,
                "download_status": "SUCCESS",
            }

        except OSMnxDownloadError as e:
            logger.error(f"OSMnx 下载路网失败 region_id={region_id}: {e}")
            network.download_status = RoadNetworkStatus.FAILED
            network.error_message = str(e)[:500]
            await network.save()
            raise ValueError(str(e))
        except Exception as e:
            logger.error(f"下载路网失败 region_id={region_id}: {e}")
            network.download_status = RoadNetworkStatus.FAILED
            network.error_message = str(e)[:500]
            await network.save()
            raise ValueError(f"下载失败: {e}")

    async def upload_road_network(self, region_id: int, file_content: bytes, file_name: str) -> dict:
        """上传路网文件"""
        import time

        region = await Region.filter(id=region_id).first()
        if not region:
            raise ValueError("区域不存在")

        ext = os.path.splitext(file_name)[1].lower()
        if ext in (".graphml", ".xml"):
            file_type = RoadNetworkType.GRAPHML
        elif ext == ".osm":
            file_type = RoadNetworkType.OSM
        elif ext == ".gpkg":
            file_type = RoadNetworkType.GPKG
        else:
            file_type = RoadNetworkType.GRAPHML

        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "road_networks")
        os.makedirs(upload_dir, exist_ok=True)

        saved_name = f"{region_id}_{int(time.time())}{ext}"
        file_path = os.path.join(upload_dir, saved_name)

        with open(file_path, "wb") as f:
            f.write(file_content)

        file_size = os.path.getsize(file_path)

        network = await RoadNetwork.create(
            region_id=region_id,
            file_name=file_name,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size,
            download_mode="upload",
            download_status=RoadNetworkStatus.SUCCESS,
        )

        return {
            "id": network.id,
            "file_name": network.file_name,
            "file_type": network.file_type,
            "file_size": file_size,
            "download_status": "SUCCESS",
        }

    async def delete_road_network(self, network_id: int):
        """删除单个路网文件"""
        network = await RoadNetwork.filter(id=network_id).first()
        if not network:
            raise ValueError("路网文件不存在")
        if network.file_path and os.path.exists(network.file_path):
            os.remove(network.file_path)
        await network.delete()

    async def clear_road_networks(self, region_id: int) -> int:
        """清除指定区域的所有路网文件"""
        networks = await RoadNetwork.filter(region_id=region_id)
        count = 0
        for n in networks:
            if n.file_path and os.path.exists(n.file_path):
                os.remove(n.file_path)
            await n.delete()
            count += 1
        return count

    async def export_road_network(self, network_id: int) -> tuple:
        """导出路网文件"""
        network = await RoadNetwork.filter(id=network_id).first()
        if not network:
            raise ValueError("路网文件不存在")
        if not network.file_path or not os.path.exists(network.file_path):
            raise ValueError("路网文件未找到")

        ext = os.path.splitext(network.file_path)[1].lower()
        if ext == ".graphml":
            media_type = "application/xml"
        elif ext == ".osm":
            media_type = "application/xml"
        else:
            media_type = "application/octet-stream"

        return network.file_path, network.file_name, media_type


    # ── 路网工作台 ──

    @staticmethod
    def _enrich_highway_types(highway_types: list) -> list:
        """将 highway 字符串列表转为 [{type, name_zh}] 对象列表"""
        from app.utils.road_network_analyzer import RoadNetworkAnalyzer
        zh_map = RoadNetworkAnalyzer.HIGHWAY_ZH
        if highway_types and isinstance(highway_types[0], str):
            return [{"type": t, "name_zh": zh_map.get(t, t)} for t in highway_types]
        # 已经是对象列表，补上缺失的 name_zh
        for item in highway_types:
            if isinstance(item, dict) and "name_zh" not in item:
                item["name_zh"] = zh_map.get(item.get("type", ""), item.get("type", ""))
        return highway_types

    @staticmethod
    def _compute_viewport(bbox) -> dict:
        """根据 bbox (minlon, minlat, maxlon, maxlat) 计算几何中心和建议缩放级别"""
        import math

        if not bbox or len(bbox) != 4:
            return {"center": None, "zoom": None}

        west, south, east, north = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        center_lat = (south + north) / 2
        center_lon = (west + east) / 2

        # 取经纬度跨度中较大者（高纬度地区经度跨度可能远大于纬度）
        lon_span = max(east - west, 0.001)
        lat_span = max(north - south, 0.001)
        span = max(lon_span, lat_span)
        # 从低 zoom 向上找：系数 0.7 让 bbox 占约 70% 视口，留白适中
        for z in range(2, 19):
            tile_span = 360.0 / (1 << z)
            if span * 0.7 > tile_span:
                return {"center": {"lat": round(center_lat, 4), "lon": round(center_lon, 4)}, "zoom": z}
        return {"center": {"lat": round(center_lat, 4), "lon": round(center_lon, 4)}, "zoom": 18}

    async def extract_boundary_from_road_network(
        self, network_id: int, region_id: int, method: str = "concave", alpha: float = 2.0
    ) -> dict:
        """从路网文件中提取行政边界节点，生成 GPKG 边界文件并关联到区域

        参数:
            network_id: 路网文件ID
            region_id: 目标区域ID（边界文件关联的区域）
            method: 算法 (convex / concave)
            alpha: 凹包 alpha 参数（仅 concave 有效）

        返回: dict with boundary_id, file_name, gpkg_path, stats
        """
        import asyncio
        import functools
        import time

        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        # 1. 验证路网文件
        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")
        if not os.path.exists(network.file_path):
            raise ValueError(f"路网文件已丢失: {network.file_path}")

        # 2. 验证区域存在
        region = await Region.filter(id=region_id).first()
        if not region:
            raise ValueError("目标区域不存在")

        # 3. 创建边界文件记录（处理中状态）
        source_stem = os.path.splitext(network.file_name)[0]
        method_tag = "hull" if method == "convex" else f"alpha{alpha}"
        file_name = f"{source_stem}_boundary_{method_tag}.gpkg"

        boundary = await RegionBoundary.create(
            region_id=region_id,
            file_name=file_name,
            file_type=BoundaryType.GPKG,
            file_path="",
            download_status=BoundaryStatus.DOWNLOADING,
        )

        try:
            # 4. 在线程池中执行同步的边界提取（耗时操作）
            upload_dir = os.path.join(settings.BASE_DIR, "uploads", "boundaries")
            os.makedirs(upload_dir, exist_ok=True)

            saved_name = f"extract_{region_id}_{int(time.time())}_{method_tag}.gpkg"
            output_path = os.path.join(upload_dir, saved_name)

            loop = asyncio.get_running_loop()
            stats = await loop.run_in_executor(
                None,
                functools.partial(
                    RoadNetworkAnalyzer.generate_boundary_gpkg,
                    file_path=network.file_path,
                    output_path=output_path,
                    method=method,
                    alpha=alpha,
                ),
            )

            # 5. 更新记录为成功
            file_size = os.path.getsize(output_path)
            boundary.file_path = output_path
            boundary.file_name = file_name
            boundary.file_size = file_size
            boundary.srid = "EPSG:4326"
            boundary.download_status = BoundaryStatus.SUCCESS
            await boundary.save()

            logger.info(
                f"路网边界提取成功: network_id={network_id}, region_id={region_id}, "
                f"method={method}, alpha={alpha}, "
                f"nodes={stats['node_count']}, hull_points={stats['hull_point_count']}, "
                f"file_size={file_size}"
            )

            return {
                "boundary_id": boundary.id,
                "file_name": boundary.file_name,
                "file_type": boundary.file_type,
                "file_size": file_size,
                "download_status": "SUCCESS",
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"路网边界提取失败 network_id={network_id}: {e}")
            boundary.download_status = BoundaryStatus.FAILED
            boundary.error_message = str(e)[:500]
            await boundary.save()
            raise ValueError(f"边界提取失败: {e}")

    async def analyze_road_network(self, network_id: int) -> dict:
        """获取路网信息（统计 + GeoJSON），优先读取 stats_json 缓存。后台预热图缓存"""
        import asyncio
        import functools
        import json

        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        # ── 后台预热图缓存（不阻塞当前响应）──
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, functools.partial(self._get_cached_graph, network.file_path))

        # ── 缓存命中：直接返回统计信息，跳过文件加载 ──
        if network.stats_json:
            try:
                cached = json.loads(network.stats_json)
                # 用 bbox 构造最小 geojson 供前端 fitBounds
                bbox = cached.get("bbox")
                minimal_geojson = None
                if bbox and len(bbox) == 4:
                    w, s, e, n = bbox
                    minimal_geojson = {
                        "type": "FeatureCollection",
                        "features": [{
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                            },
                            "properties": {},
                        }],
                    }
                viewport = self._compute_viewport(bbox)
                result = {
                    "network_id": network_id,
                    "info": cached.get("info", {}),
                    "geojson": minimal_geojson,
                    "highway_types": self._enrich_highway_types(cached.get("highway_types", [])),
                    "center": viewport["center"],
                    "zoom": viewport["zoom"],
                }
                # 文件信息始终从记录读取（实时）
                result["info"]["file_size"] = network.file_size
                result["info"]["file_name"] = network.file_name
                result["info"]["srid"] = network.srid
                # 兼容旧缓存：补上 name_zh
                from app.utils.road_network_analyzer import RoadNetworkAnalyzer
                for s in result["info"].get("highway_stats", []):
                    if "name_zh" not in s:
                        s["name_zh"] = RoadNetworkAnalyzer.HIGHWAY_ZH.get(s.get("type", ""), s.get("type", ""))
                return result
            except (json.JSONDecodeError, KeyError):
                pass  # 缓存损坏，回退到重新计算

        # ── 缓存未命中：完整加载并写入 ──
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(
            None, functools.partial(RoadNetworkAnalyzer.get_info, network.file_path)
        )
        geojson = await loop.run_in_executor(
            None, functools.partial(RoadNetworkAnalyzer.to_geojson, network.file_path)
        )
        highways = await loop.run_in_executor(
            None, functools.partial(RoadNetworkAnalyzer.get_highway_types, network.file_path)
        )

        # 保存缓存（不阻塞响应）
        try:
            bbox = info.get("bbox")
            cache_data = {
                "info": {k: v for k, v in info.items() if k != "bbox"},  # bbox 存外层
                "highway_types": highways,
                "bbox": bbox,
            }
            network.stats_json = json.dumps(cache_data, ensure_ascii=False)
            await network.save(update_fields=["stats_json"])
        except Exception:
            pass  # 保存失败不影响返回

        # 文件信息附加到 info
        info["file_size"] = network.file_size
        info["file_name"] = network.file_name
        info["srid"] = network.srid

        viewport = self._compute_viewport(info.get("bbox"))
        return {
            "network_id": network_id,
            "info": info,
            "geojson": geojson,
            "highway_types": self._enrich_highway_types(highways),
            "center": viewport["center"],
            "zoom": viewport["zoom"],
        }

    async def filter_road_network(
        self, network_id: int, selected_types: list, save_to_region: bool = False
    ) -> dict:
        """按道路等级筛选路网"""
        import asyncio
        import functools
        import time

        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "road_networks")
        # 源文件名去后缀 + 类型编码（每个 highway 取前两字母）
        source_stem = os.path.splitext(network.file_name)[0]
        type_code = "".join(t[:2] for t in selected_types)
        output_name = f"{source_stem}_{type_code}.gpkg"
        output_path = os.path.join(upload_dir, output_name)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            functools.partial(
                RoadNetworkAnalyzer.filter_by_highway,
                network.file_path, output_path, selected_types,
            ),
        )

        # 如果需要保存到区域下
        if save_to_region:
            file_size = os.path.getsize(output_path)
            await RoadNetwork.create(
                region_id=network.region_id,
                file_name=output_name,
                file_type=RoadNetworkType.GPKG,
                file_path=output_path,
                file_size=file_size,
                node_count=result["node_count"],
                edge_count=result["edge_count"],
                download_mode="filter",
                download_status=RoadNetworkStatus.SUCCESS,
            )

        return result

    async def segment_road_network(
        self, network_id: int, segment_length: float, save_to_region: bool = False
    ) -> dict:
        """按指定长度分段路网"""
        import asyncio
        import functools
        import time

        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "road_networks")
        output_name = f"segmented_{network_id}_{int(time.time())}.graphml"
        output_path = os.path.join(upload_dir, output_name)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            functools.partial(
                RoadNetworkAnalyzer.segment,
                network.file_path, output_path, segment_length,
            ),
        )

        if save_to_region:
            file_size = os.path.getsize(output_path)
            await RoadNetwork.create(
                region_id=network.region_id,
                file_name=output_name,
                file_type=RoadNetworkType.GRAPHML,
                file_path=output_path,
                file_size=file_size,
                node_count=result["node_count"],
                edge_count=result["edge_count"],
                download_mode="segment",
                download_status=RoadNetworkStatus.SUCCESS,
            )

        return result

    async def get_tile(
        self, network_id: int, z: int, x: int, y: int,
        selected_types: list = None,
    ) -> bytes:
        """获取路网瓦片 PNG 字节（使用专用线程池，不阻塞默认 executor）"""
        import asyncio
        import functools

        from app.utils.road_network_tiler import RoadNetworkTiler

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            return RoadNetworkTiler._empty_tile()

        # 使用专用瓦片线程池，避免阻塞 FastAPI 默认 executor
        loop = asyncio.get_running_loop()
        png_bytes = await loop.run_in_executor(
            RoadNetworkTiler.get_executor(),
            functools.partial(
                RoadNetworkTiler.render_tile,
                network.file_path, network_id, z, x, y, selected_types,
            ),
        )
        return png_bytes

    async def warm_tile_cache(self, network_id: int) -> dict:
        """预热路网图缓存（后台加载，不阻塞）"""
        from app.utils.road_network_tiler import RoadNetworkTiler

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            return {"status": "error", "message": "路网文件不存在"}
        return RoadNetworkTiler.warm_cache(network.file_path)

    @staticmethod
    def _get_cached_fields(file_path: str, search: str, page: int, page_size: int) -> dict:
        """分页读取字段数据：从缓存图 + edge_keys 索引中按需构建当前页"""
        G, edge_keys, fields = RegionController._get_cached_graph(file_path)
        _SKIP_KEYS = {"geometry", "geom", "wkt", "wkb"}

        # 搜索过滤
        if search:
            s = search.lower()
            matched = []
            for u, v, k in edge_keys:
                data = G[u][v][k]
                if any(s in str(data.get(key, "")).lower() for key in data if key not in _SKIP_KEYS):
                    matched.append((u, v, k))
            total = len(matched)
            page_keys = matched[(page - 1) * page_size : page * page_size]
        else:
            total = len(edge_keys)
            page_keys = edge_keys[(page - 1) * page_size : page * page_size]

        # 只构建当前页的 rows
        rows = []
        for u, v, k in page_keys:
            row = {"u": u, "v": v, "k": k}
            for key, val in G[u][v][k].items():
                if key not in _SKIP_KEYS:
                    row[key] = RegionController._safe_json_val(val)
            rows.append(row)

        return {"fields": fields, "rows": rows, "total": total}

    async def get_road_fields(self, network_id: int, page: int, page_size: int, search: str) -> dict:
        """获取路网边字段参数（后端分页），返回 {fields, rows, total}"""
        import asyncio
        import functools

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(
                self._get_cached_fields,
                network.file_path, search, page, page_size,
            ),
        )

    @staticmethod
    def _get_cached_graph(file_path: str):
        """获取缓存 (图对象, edge_keys索引, 字段名列表)。文件 mtime 变化自动失效。
        首次加载后 pickle 序列化到磁盘，后续直接反序列化（比 GPKG 解析快 5-10x）。"""
        import pickle

        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else 0

        # ── 内存缓存命中 ──
        cached = RegionController._graph_cache.get(file_path)
        if cached and cached[0] == mtime:
            return cached[1]

        # ── Pickle 缓存命中 ──
        pickle_path = file_path + ".pickle"
        try:
            if os.path.exists(pickle_path) and os.path.getmtime(pickle_path) >= mtime:
                with open(pickle_path, "rb") as f:
                    G, edge_keys, fields = pickle.load(f)
                RegionController._graph_cache[file_path] = (mtime, (G, edge_keys, fields))
                return (G, edge_keys, fields)
        except Exception:
            pass  # pickle 损坏，回退到 GPKG 加载

        # ── 冷启动：加载 GPKG + 构建索引 ──
        G = RoadNetworkAnalyzer._load_graph(file_path)
        _SKIP_KEYS = {"geometry", "geom", "wkt", "wkb"}
        edge_keys = []
        all_fields = set()
        for u, v, k in G.edges(keys=True):
            edge_keys.append((u, v, k))
            all_fields.update(key for key in G[u][v][k] if key not in _SKIP_KEYS)
        fields = sorted(all_fields)
        RegionController._graph_cache[file_path] = (mtime, (G, edge_keys, fields))

        # ── 保存 pickle 缓存 ──
        try:
            with open(pickle_path, "wb") as f:
                pickle.dump((G, edge_keys, fields), f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass  # 保存失败不影响功能

        # 限制内存缓存大小（只保留最近 5 个）
        if len(RegionController._graph_cache) > 5:
            oldest = min(RegionController._graph_cache.keys(), key=lambda k: RegionController._graph_cache[k][0])
            del RegionController._graph_cache[oldest]
        return (G, edge_keys, fields)

    async def export_road_fields_json(self, network_id: int) -> dict:
        """导出路网全量边数据为 JSON"""
        import asyncio
        import functools

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(self._export_fields_sync, network.file_path),
        )

    @staticmethod
    def _safe_json_val(val):
        """将值转为 JSON 可序列化类型"""
        if val is None:
            return None
        if isinstance(val, (bool, int, float, str)):
            return val
        # Shapely 几何对象
        if hasattr(val, "coords"):
            return str(val)
        # bytes
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        # 其他不可序列化对象 → 字符串
        try:
            json.dumps(val)
            return val
        except (TypeError, ValueError):
            return str(val)

    @staticmethod
    def _export_fields_sync(file_path: str) -> dict:
        """同步读取全部边数据为 JSON（排除地理空间字段，导入时从源文件匹配恢复）"""
        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        G = RoadNetworkAnalyzer._load_graph(file_path)
        _SKIP_KEYS = {"geometry", "geom", "wkt", "wkb"}
        fields_set = set()
        edges = []

        for edge in G.edges(data=True, keys=True):
            if len(edge) == 4:
                u, v, k, data = edge
            else:
                u, v, data = edge
                k = 0
            row = {"u": u, "v": v, "k": k}
            for key, val in data.items():
                if key in _SKIP_KEYS:
                    continue
                row[key] = RegionController._safe_json_val(val)
                fields_set.add(key)
            edges.append(row)

        return {
            "fields": sorted(fields_set),
            "edges": edges,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        }

    async def import_road_fields_json(self, network_id: int, edges: list) -> dict:
        """根据 JSON 边数据重建路网，保存为新文件"""
        import asyncio
        import functools
        import time

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "road_networks")
        source_stem = os.path.splitext(network.file_name)[0]
        output_name = f"{source_stem}_imported_{int(time.time())}.gpkg"
        output_path = os.path.join(upload_dir, output_name)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            functools.partial(
                self._import_fields_sync,
                network.file_path, output_path, edges,
            ),
        )

        file_size = os.path.getsize(output_path)
        await RoadNetwork.create(
            region_id=network.region_id,
            file_name=output_name,
            file_type=RoadNetworkType.GPKG,
            file_path=output_path,
            file_size=file_size,
            node_count=result["node_count"],
            edge_count=result["edge_count"],
            download_mode="imported",
            download_status=RoadNetworkStatus.SUCCESS,
        )

        return {
            "applied": result["applied"],
            "node_count": result["node_count"],
            "edge_count": result["edge_count"],
            "file_path": output_path,
        }

    @staticmethod
    def _import_fields_sync(src_path: str, dst_path: str, edges: list) -> dict:
        """用 JSON 边数据重建网络：从源文件按 (u,v,k) 匹配恢复 geometry"""
        import networkx as nx

        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        src = RoadNetworkAnalyzer._load_graph(src_path)
        G = type(src)()
        applied = 0
        geom_restored = 0

        # 先复制源文件的节点（保留坐标）
        for n, attrs in src.nodes(data=True):
            G.add_node(n, **attrs)

        # 用 JSON 中的属性字段 + 源文件的 geometry 重建边
        for row in edges:
            u = row.get("u")
            v = row.get("v")
            k = row.get("k", 0)
            if u is None or v is None:
                continue
            # 补充缺失的节点（以防 JSON 中有新节点）
            for node in (u, v):
                if not G.has_node(node):
                    G.add_node(node)
            # 从 JSON 取属性字段
            edge_data = {}
            for key, val in row.items():
                if key in ("u", "v", "k"):
                    continue
                edge_data[key] = val
            # 从源文件匹配恢复 geometry
            if src.has_edge(u, v, k):
                src_edge = src[u][v][k]
                for geo_key in ("geometry", "geom"):
                    src_geom = src_edge.get(geo_key)
                    if src_geom is not None:
                        edge_data[geo_key] = src_geom
                        geom_restored += 1
                        break
            G.add_edge(u, v, key=k, **edge_data)
            applied += 1

        RoadNetworkAnalyzer._save_gpkg(G, dst_path)
        return {
            "applied": applied,
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        }

    async def batch_update_road_field(self, network_id: int, field: str, mode: str, value: str) -> dict:
        """批量操作字段值"""
        import asyncio
        import functools

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        if mode not in ("set", "sanitize"):
            raise ValueError(f"不支持的模式: {mode}")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(
                self._batch_update_field_sync,
                network.file_path, field, mode, value,
            ),
        )

    @staticmethod
    def _batch_update_field_sync(file_path: str, field: str, mode: str, value: str) -> dict:
        """同步批量更新 + 写回文件"""
        import re
        import networkx as nx
        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        G = RoadNetworkAnalyzer._load_graph(file_path)
        affected = 0

        # 兼容 MultiDiGraph (u,v,k,data) 和 DiGraph (u,v,data)
        for edge in G.edges(data=True, keys=True):
            if len(edge) == 4:
                u, v, k, data = edge
            else:
                u, v, data = edge
            if field not in data:
                continue
            old = data[field]

            if mode == "set":
                data[field] = value
                affected += 1
            elif mode == "sanitize":
                # 数组/列表字符串取首值
                s = str(old)
                m = re.match(r"^\s*\[(?:\"|')([a-zA-Z0-9_]+)(?:\"|')", s)
                if m:
                    data[field] = m.group(1)
                    affected += 1
                elif ";" in s:
                    data[field] = s.split(";")[0].strip()
                    affected += 1

        if affected > 0:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".gpkg":
                RoadNetworkAnalyzer._save_gpkg(G, file_path)
            else:
                nx.write_graphml(G, file_path)

        return {"affected": affected, "field": field, "mode": mode}

    async def clear_tile_cache(self, network_id: int) -> dict:
        """清除指定路网的瓦片渲染缓存（磁盘 + 内存）"""
        from app.utils.road_network_tiler import RoadNetworkTiler

        RoadNetworkTiler.clear_cache(network_id=network_id)
        return {"status": "cleared", "network_id": network_id}

    async def get_road_network_list(self, region_id: int) -> list:
        """获取区域下所有已成功下载的路网文件列表"""
        networks = await RoadNetwork.filter(
            region_id=region_id,
            download_status=RoadNetworkStatus.SUCCESS,
            is_active=True,
        ).order_by("-created_at")
        return [
            {
                "id": n.id,
                "file_name": n.file_name,
                "file_type": n.file_type,
                "node_count": n.node_count,
                "edge_count": n.edge_count,
                "download_mode": n.download_mode,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in networks
        ]


    # ── 筛选模板管理 ──

    async def list_filter_templates(self) -> list:
        """获取所有筛选模板"""
        templates = await FilterTemplate.all().order_by("-is_preset", "name")
        return [
            {
                "id": t.id,
                "name": t.name,
                "selected_types": t.selected_types,
                "is_preset": t.is_preset,
            }
            for t in templates
        ]

    async def create_filter_template(self, name: str, selected_types: list) -> dict:
        """创建筛选模板"""
        if await FilterTemplate.filter(name=name).exists():
            raise ValueError(f"模板「{name}」已存在")
        obj = await FilterTemplate.create(name=name, selected_types=selected_types)
        return {"id": obj.id, "name": obj.name, "selected_types": obj.selected_types}

    async def delete_filter_template(self, template_id: int) -> None:
        """删除筛选模板"""
        obj = await FilterTemplate.filter(id=template_id).first()
        if not obj:
            raise ValueError("模板不存在")
        if obj.is_preset:
            raise ValueError("系统预设模板不可删除")
        await obj.delete()

    # ── AI 代理处理路网字段 ──

    async def process_fields_with_ai(
        self,
        network_id: int,
        ai_proxy_id: int,
        prompt: str,
        sample: dict,
        fields_list: list,
        skill_id: Optional[int] = None,
    ) -> dict:
        """
        使用 AI 代理处理路网边字段数据。

        流程：
        1. 获取 AIProxy 配置和 Skill 内容
        2. 用样本 + 字段列表 + prompt 发给 AI 生成处理脚本
        3. 加载源 GPKG 全量边数据（无 geometry）
        4. 执行脚本处理全量边数据
        5. 按 (u,v,k) 从源文件匹配恢复 geometry
        6. 保存为新的 GPKG 文件（同一行政区）
        7. 返回新文件信息
        """
        import asyncio
        import functools
        import time

        from openai import OpenAI

        from app.models.admin import AIProxy, Skill
        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        # ── 获取路网文件 ──
        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

        # ── 获取 AI 代理 ──
        ai_proxy = await AIProxy.filter(id=ai_proxy_id).first()
        if not ai_proxy:
            raise ValueError("AI 代理不存在")

        # ── 获取 Skill 内容 ──
        skill_prompt = ""
        if skill_id:
            skill = await Skill.filter(id=skill_id).first()
            if skill:
                skill_prompt = skill.content

        # ── 构建 system prompt ──
        system_prompt = (
            "要求：\n"
            "1. 所有需要的模块（json, re, copy）已预置，直接使用，禁止 import\n"
            "2. 不要修改 u/v/k 字段（除筛选删除外）\n"
            "3. 返回值中的每条 dict 必须保持 u/v/k 字段\n"
            "4. 只输出 Python 代码，不要输出解释文字\n"
        )
        if skill_prompt:
            system_prompt += f"\n## 处理框架（Skill）\n{skill_prompt}"

        # ── 构建 user prompt（仅含字段列表 + 样本） ──
        sample_display = {"u": sample.get("u"), "v": sample.get("v"), "k": sample.get("k", 0)}
        for k in fields_list[:20]:
            if k in sample:
                sample_display[k] = sample[k]

        user_prompt = (
            f"## 字段列表\n{json.dumps(fields_list, ensure_ascii=False)}\n\n"
            f"## 数据样本（1 条边）\n"
            f"```json\n{json.dumps(sample_display, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## 用户需求\n{prompt}\n\n"
            "请生成 process(edges) 函数来处理这些数据。"
        )

        # ── 调用 AI 生成脚本 ──
        client = OpenAI(base_url=ai_proxy.url, api_key=ai_proxy.token)
        model = ai_proxy.model or "gpt-3.5-turbo"

        def _sync_call():
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content

        code = await asyncio.to_thread(_sync_call)
        code = self._clean_ai_code(code)

        logger.info(f"AI 处理路网字段，network_id={network_id}")

        # ── 加载源文件全量边数据（无 geometry） ──
        loop = asyncio.get_running_loop()

        def _load_all_edges():
            G = RoadNetworkAnalyzer._load_graph(network.file_path)
            _SKIP = {"geometry", "geom", "wkt", "wkb"}
            all_edges = []
            for edge in G.edges(data=True, keys=True):
                if len(edge) == 4:
                    u, v, k, data = edge
                else:
                    u, v, data = edge
                    k = 0
                row = {"u": u, "v": v, "k": k}
                for key, val in data.items():
                    if key not in _SKIP:
                        row[key] = RegionController._safe_json_val(val)
                all_edges.append(row)
            return all_edges, G

        all_edges, src_graph = await loop.run_in_executor(None, _load_all_edges)

        # ── 执行 AI 脚本处理全量数据 ──
        def _exec():
            return self._exec_fields_script(code, all_edges)

        result_edges, exec_message = await loop.run_in_executor(None, _exec)

        if not isinstance(result_edges, list):
            return {"message": f"脚本返回非列表: {type(result_edges).__name__}", "network_id": None}

        # ── 兜底清理：确保 name/osmid 数组被正确取首值 ──
        def _sanitize():
            return self._sanitize_arrays(result_edges)

        sanitized_count = await loop.run_in_executor(None, _sanitize)
        if sanitized_count:
            exec_message += f"，兜底清理数组 {sanitized_count} 条"

        # ── 按 (u,v,k) 从源文件匹配恢复 geometry ──
        def _rebuild_with_geometry():
            G_new = type(src_graph)()
            # 复制节点
            for n, attrs in src_graph.nodes(data=True):
                G_new.add_node(n, **attrs)
            geom_restored = 0
            for row in result_edges:
                u = row.get("u")
                v = row.get("v")
                k = row.get("k", 0)
                if u is None or v is None:
                    continue
                if not G_new.has_node(u):
                    G_new.add_node(u)
                if not G_new.has_node(v):
                    G_new.add_node(v)
                edge_data = {}
                for key, val in row.items():
                    if key in ("u", "v", "k"):
                        continue
                    edge_data[key] = val
                if src_graph.has_edge(u, v, k):
                    src_edge = src_graph[u][v][k]
                    for geo_key in ("geometry", "geom"):
                        src_geom = src_edge.get(geo_key)
                        if src_geom is not None:
                            edge_data[geo_key] = src_geom
                            geom_restored += 1
                            break
                G_new.add_edge(u, v, key=k, **edge_data)
            return G_new, geom_restored

        G_new, geom_restored = await loop.run_in_executor(None, _rebuild_with_geometry)

        # ── 保存为新 GPKG 文件 ──
        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "road_networks")
        src_stem = os.path.splitext(network.file_name)[0]
        output_name = f"{src_stem}_ai_{int(time.time())}.gpkg"
        output_path = os.path.join(upload_dir, output_name)

        def _save():
            RoadNetworkAnalyzer._save_gpkg(G_new, output_path)

        await loop.run_in_executor(None, _save)
        file_size = os.path.getsize(output_path)

        # ── 创建数据库记录（同一行政区） ──
        new_network = await RoadNetwork.create(
            region_id=network.region_id,
            file_name=output_name,
            file_type=RoadNetworkType.GPKG,
            file_path=output_path,
            file_size=file_size,
            node_count=G_new.number_of_nodes(),
            edge_count=G_new.number_of_edges(),
            download_mode="ai_processed",
            download_status=RoadNetworkStatus.SUCCESS,
        )

        message = (
            f"{exec_message}，geometry 恢复 {geom_restored}/{len(result_edges)} 条"
        )

        logger.info(
            f"AI 处理完成: network_id={network_id} → new_id={new_network.id}, "
            f"edges={len(all_edges)} → {len(result_edges)}, geom_restored={geom_restored}"
        )

        return {
            "network_id": new_network.id,
            "file_name": new_network.file_name,
            "node_count": G_new.number_of_nodes(),
            "edge_count": G_new.number_of_edges(),
            "message": message,
        }

    @staticmethod
    def _clean_ai_code(text: str) -> str:
        """清理 AI 返回的代码：去 ``` 包裹、去首尾空白"""
        text = text.strip()
        for prefix in ("```python", "```"):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    @staticmethod
    def _sanitize_arrays(edges: list) -> int:
        """兜底清理 name/osmid 字段中的数组值，取第一个元素。返回修复条数"""
        import re
        count = 0
        for e in edges:
            for field in ("name", "osmid"):
                val = e.get(field)
                if val is None:
                    continue
                s = str(val)
                # 匹配 ['xxx', ...] 或 ["xxx", ...]
                m = re.match(r"^\s*\[\s*['\"]([^'\"]+)['\"]", s)
                if m:
                    e[field] = m.group(1)
                    count += 1
                    continue
                # 匹配 [123, ...]
                m2 = re.match(r'^\s*\[\s*(-?\d+)', s)
                if m2:
                    e[field] = int(m2.group(1))
                    count += 1
        return count

    @staticmethod
    def _exec_fields_script(code: str, edges: list):
        """在受限环境中执行 AI 脚本处理边数据"""
        try:
            compiled = compile(code, "<ai_fields>", "exec")
        except SyntaxError as e:
            return edges, f"脚本语法错误: {e}"

        restricted_globals = {
            "__builtins__": {
                "__import__": __import__,
                "print": print,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "sorted": sorted,
                "list": list,
                "dict": dict,
                "set": set,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "type": type,
                "isinstance": isinstance,
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "any": any,
                "all": all,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
            },
            "json": json,
            "re": __import__("re"),
            "copy": __import__("copy"),
            "deepcopy": __import__("copy").deepcopy,
        }
        local_vars = {}

        try:
            exec(compiled, restricted_globals, local_vars)
        except Exception as e:
            return edges, f"脚本执行错误: {e}"

        process_func = local_vars.get("process")
        if not process_func:
            return edges, "脚本未定义 process(edges) 函数"

        try:
            result = process_func(edges)
        except Exception as e:
            import traceback

            logger.error(f"process() 调用错误: {traceback.format_exc()}")
            return edges, f"处理函数执行错误: {e}"

        if not isinstance(result, list):
            return edges, f"期望返回 list，实际返回 {type(result).__name__}"

        return result, f"处理完成，{len(edges)} → {len(result)} 条边"


region_controller = RegionController()
