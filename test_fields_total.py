#!/usr/bin/env python
"""快速测试 /fields API 返回的总数"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['TORTOISE_TEST_DB'] = 'sqlite://data/db.sqlite3'

async def main():
    from tortoise import Tortoise
    from app.settings.config import Settings
    
    cfg = Settings()
    await Tortoise.init(config=cfg.TORTOISE_ORM)
    
    from app.controllers.region import RegionController
    rc = RegionController()
    
    # 测试 network_id=58
    result = await rc.get_road_fields(58, 1, 50, "")
    print(f"total={result['total']}, rows={len(result['rows'])}")
    print(f"fields={result['fields']}")
    
    # 第 2 页
    result2 = await rc.get_road_fields(58, 2, 50, "")
    print(f"page2 total={result2['total']}, rows={len(result2['rows'])}")
    
    await Tortoise.close_connections()

asyncio.run(main())
