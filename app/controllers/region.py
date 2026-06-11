"""全球国家及行政区 Controller"""
import json
import os
from typing import Optional

from fastapi.responses import StreamingResponse
from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import Region, RegionBoundary, RoadNetwork
from app.models.enums import (
    BoundaryStatus, BoundaryType, RegionType,
    RoadNetworkStatus, RoadNetworkType,
)
from app.schemas.regions import RegionCreate, RegionUpdate
from app.settings.config import settings
from app.utils.gadm_downloader import GADMDownloadError, GADMDownloader


class RegionController(CRUDBase[Region, RegionCreate, RegionUpdate]):
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
            q &= Q(name__contains=name)
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
                "id": c.id, "label": c.name, "code": c.code,
                "region_type": c.region_type, "is_active": c.is_active,
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
                "id": child.id, "label": child.name, "code": child.code,
                "region_type": child.region_type, "is_active": child.is_active,
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
                "id": c.id, "name": c.name, "code": c.code,
                "region_type": c.region_type, "parent_id": c.parent_id,
                "capital": c.capital, "is_active": c.is_active,
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
        return {
            "created_country": created_country,
            "updated_country": updated_country,
            "created_state": created_state,
            "created_city": created_city,
            "skipped_state": skipped_state,
            "skipped_city": skipped_city,
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
            # 调用 GADM 下载器
            geojson_data, source_url = await GADMDownloader.download(
                iso_alpha3=iso_alpha3,
                region_type=region.region_type,
                timeout=120.0,
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
        self, region_id: int, mode: str = "boundary", file_type: str = "GRAPHML"
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
            file_name=f"{region.name}.graphml",
            file_type=RoadNetworkType.GRAPHML,
            file_path="",
            download_mode=mode,
            download_status=RoadNetworkStatus.DOWNLOADING,
        )

        upload_dir = os.path.join(settings.BASE_DIR, "uploads", "road_networks")
        output_name = f"{region_id}_{int(time.time())}"

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

    async def analyze_road_network(self, network_id: int) -> dict:
        """获取路网信息（统计 + GeoJSON）"""
        import asyncio
        import functools

        from app.utils.road_network_analyzer import RoadNetworkAnalyzer

        network = await RoadNetwork.filter(id=network_id).first()
        if not network or not network.file_path:
            raise ValueError("路网文件不存在")

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

        return {
            "network_id": network_id,
            "info": info,
            "geojson": geojson,
            "highway_types": highways,
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
        output_name = f"filtered_{network_id}_{int(time.time())}.graphml"
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
                file_type=RoadNetworkType.GRAPHML,
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


region_controller = RegionController()
