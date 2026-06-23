"""系统配置 Controller"""
import json
from typing import Any, Optional

import httpx

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import SystemConfig

# 默认配置
DEFAULT_CONFIGS = {
    "download_proxy": {"value": "", "description": "HTTP 代理地址，如 http://127.0.0.1:7890"},
    "download_chunk_count": {"value": "4", "description": "分块下载线程数 (1-8)"},
    "download_chunk_size_mb": {"value": "50", "description": "每块下载大小 MB (10-500)"},
    "download_max_retries": {"value": "3", "description": "下载失败最大重试次数 (0-10)"},
    "download_timeout_seconds": {"value": "600", "description": "下载超时秒数 (60-3600)"},
    "download_ssl_verify": {"value": "true", "description": "SSL 证书验证 (true/false)。代理环境下出现 SSL 错误时可关闭"},
    "road_highway_colors": {
        "value": json.dumps({
            "motorway": [230, 74, 25], "motorway_link": [230, 74, 25],
            "trunk": [216, 67, 21], "trunk_link": [216, 67, 21],
            "primary": [239, 108, 0], "primary_link": [239, 108, 0],
            "secondary": [249, 168, 37], "secondary_link": [249, 168, 37],
            "tertiary": [67, 160, 71], "tertiary_link": [67, 160, 71],
            "residential": [30, 136, 229], "living_street": [30, 136, 229],
            "unclassified": [158, 158, 158], "road": [158, 158, 158],
            "service": [117, 117, 117], "footway": [161, 136, 127],
            "cycleway": [102, 187, 106], "path": [141, 110, 99],
            "track": [121, 85, 72], "pedestrian": [255, 183, 77],
        }, ensure_ascii=False),
        "description": "路网瓦片道路颜色映射 {highway: [R,G,B]}",
    },
    "road_highway_weights": {
        "value": json.dumps({
            "motorway": 1.3, "motorway_link": 1.0,
            "trunk": 1.2, "trunk_link": 1.0,
            "primary": 1.1, "primary_link": 0.9,
            "secondary": 1.0, "secondary_link": 0.8,
            "tertiary": 0.9, "tertiary_link": 0.7,
            "residential": 0.55, "living_street": 0.45,
            "unclassified": 0.7, "road": 0.7,
            "service": 0.5, "footway": 0.35,
            "cycleway": 0.4, "path": 0.35,
            "track": 0.4, "pedestrian": 0.5,
        }, ensure_ascii=False),
        "description": "路网瓦片线宽系数 {highway: float}，相对于 zoom 基础线宽的倍率",
    },
}


class SystemConfigController:
    """系统配置控制器（不使用 CRUDBase，直接操作键值对）"""

    async def init_defaults(self):
        """初始化默认配置（幂等，不覆盖已有配置）"""
        for key, item in DEFAULT_CONFIGS.items():
            existing = await SystemConfig.filter(key=key).first()
            if not existing:
                await SystemConfig.create(
                    key=key, value=item["value"], description=item["description"]
                )
                logger.info(f"初始化默认配置: {key}={item['value']}")

    async def get_all(self) -> dict[str, Any]:
        """获取所有下载相关配置"""
        configs = {}
        for cfg in await SystemConfig.all():
            # 尝试解析 JSON 值
            raw = cfg.value
            try:
                val = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                val = raw
            configs[cfg.key] = {
                "value": val,
                "description": cfg.description,
                "raw": raw,
            }
        return configs

    async def get_value(self, key: str, default=None) -> Any:
        """获取单个配置值（解析 JSON），供下载器调用"""
        cfg = await SystemConfig.filter(key=key).first()
        if not cfg:
            return default
        try:
            return json.loads(cfg.value)
        except (json.JSONDecodeError, TypeError):
            return cfg.value

    async def set_value(self, key: str, value: str) -> dict:
        """设置配置值"""
        cfg = await SystemConfig.filter(key=key).first()
        if not cfg:
            cfg = await SystemConfig.create(key=key, value=value, description="")
        else:
            cfg.value = value
            await cfg.save(update_fields=["value", "updated_at"])
        logger.info(f"配置更新: {key}={value}")
        return {"key": key, "value": value}

    async def set_all(self, updates: dict[str, str]) -> dict:
        """批量更新配置"""
        updated = 0
        for key, value in updates.items():
            await self.set_value(key, str(value) if not isinstance(value, str) else value)
            updated += 1
        return {"updated": updated}

    async def test_proxy(self, proxy_url: str) -> dict:
        """测试代理连通性"""
        test_url = "https://www.google.com"
        try:
            client_kwargs = {"timeout": httpx.Timeout(15.0), "follow_redirects": True}
            if proxy_url:
                client_kwargs["proxy"] = proxy_url
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(test_url)
                elapsed_ms = int(resp.elapsed.total_seconds() * 1000)
                return {
                    "success": True,
                    "status_code": resp.status_code,
                    "elapsed_ms": elapsed_ms,
                    "message": f"连通成功 ({elapsed_ms}ms)",
                }
        except httpx.ProxyError as e:
            return {"success": False, "error": f"代理连接失败: {e}"}
        except httpx.ConnectTimeout:
            return {"success": False, "error": "连接超时，请检查代理地址和网络"}
        except Exception as e:
            return {"success": False, "error": str(e)}


system_config_controller = SystemConfigController()
