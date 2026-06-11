"""
GADM 行政区边界数据下载器

GADM (Database of Global Administrative Areas) 提供全球各国行政区划的 GeoJSON 数据。
数据按国家和行政级别组织：

- level 0: 国家边界
- level 1: 一级行政区（省/州）
- level 2: 二级行政区（市/区）

下载 URL: https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_{ISO3}_{level}.json
"""
import json
from typing import Optional

import httpx

from app.log import logger

# GADM 4.1 GeoJSON 数据基础 URL
GADM_BASE_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json"


class GADMDownloadError(Exception):
    """GADM 下载异常"""


class GADMDownloader:
    """GADM 边界数据下载器"""

    @staticmethod
    def _region_type_to_level(region_type: str) -> int:
        """将 RegionType 映射为 GADM 行政级别"""
        mapping = {
            "COUNTRY": 0,
            "STATE": 1,
            "CITY": 2,
        }
        return mapping.get(region_type, 0)

    @staticmethod
    def _build_url(iso_alpha3: str, level: int) -> str:
        """构建 GADM 下载 URL"""
        return f"{GADM_BASE_URL}/gadm41_{iso_alpha3}_{level}.json"

    @classmethod
    async def download(
        cls,
        iso_alpha3: str,
        region_type: str,
        timeout: float = 120.0,
    ) -> tuple[dict, str]:
        """
        下载 GADM 边界数据。

        Args:
            iso_alpha3: ISO 3166-1 alpha-3 国家代码（如 CHN、USA）
            region_type: 区域类型（COUNTRY/STATE/CITY），映射为 GADM level

        Returns:
            (geojson_data, source_url) 元组

        Raises:
            GADMDownloadError: 下载失败或数据无效
        """
        level = cls._region_type_to_level(region_type)
        url = cls._build_url(iso_alpha3, level)
        logger.info(f"GADM 下载: url={url}")

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "vue-fastapi-admin/1.0"},
                    follow_redirects=True,
                )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            raise GADMDownloadError(
                f"GADM 下载失败 (HTTP {e.response.status_code}): "
                f"ISO3={iso_alpha3}, level={level}"
            ) from e
        except httpx.RequestError as e:
            raise GADMDownloadError(
                f"GADM 网络请求失败: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise GADMDownloadError(
                f"GADM 返回数据非有效 JSON: {e}"
            ) from e

        if not isinstance(data, dict) or "features" not in data:
            raise GADMDownloadError(
                f"GADM 返回数据格式异常: 缺少 'features' 字段, type={type(data).__name__}"
            )

        logger.info(
            f"GADM 下载成功: ISO3={iso_alpha3}, level={level}, "
            f"features={len(data.get('features', []))}"
        )
        return data, url

    @classmethod
    async def check_available(cls, iso_alpha3: str, level: int) -> bool:
        """检查 GADM 是否提供该国家/级别的数据"""
        url = cls._build_url(iso_alpha3, level)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.head(
                    url,
                    headers={"User-Agent": "vue-fastapi-admin/1.0"},
                    follow_redirects=True,
                )
                return resp.status_code == 200
        except Exception:
            return False
