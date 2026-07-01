"""GeoNames 中文地名下载器 + 桥接工具

数据流:
  allCountries.zip  ──→ 提取 ADM1/ADM2 条目 → (geonameid, country_code, name)
  alternateNamesV2   ──→ 过滤 isolanguage=zh   → (geonameid, zh_name)
                           ↓
                    交叉匹配 → (country_code, name) → zh_name
                           ↓
                    与 Region 表桥接 → region.code → zh_name
                           ↓
                    离线映射 JSON: {iso_code: zh_name}

进度状态: cache/geonames_progress.json
"""

import asyncio
import io
import json
import os
import time
import zipfile

import httpx

from app.log import logger

GEONAMES_BASE = "https://download.geonames.org/export/dump"
ALL_COUNTRIES_URL = f"{GEONAMES_BASE}/allCountries.zip"
ALTERNATE_NAMES_URL = f"{GEONAMES_BASE}/alternateNamesV2.zip"
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache"
)
PROGRESS_FILE = os.path.join(CACHE_DIR, "geonames_progress.json")


class GeoNamesDownloadError(Exception):
    """GeoNames 数据下载或解析异常"""


# ── 全局进度状态 ──
_progress: dict = {
    "status": "idle",       # idle | downloading | parsing | bridging | updating | done | error
    "phase": "",
    "progress": 0,           # 0-100
    "message": "",
    "detail": "",            # 错误详情
    "started_at": None,
    "done_at": None,
}

_reset_lock = asyncio.Lock()


def save_progress():
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(_progress, f, ensure_ascii=False, indent=2)


def get_progress() -> dict:
    """读取进度（内存优先，文件兜底）"""
    if _progress["status"] != "idle":
        return dict(_progress)
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return dict(_progress)


def reset_progress():
    """重置进度，允许重试"""
    _progress["status"] = "idle"
    _progress["phase"] = ""
    _progress["progress"] = 0
    _progress["message"] = ""
    _progress["detail"] = ""
    _progress["started_at"] = None
    _progress["done_at"] = None
    save_progress()


def _update_progress(status: str, phase: str, progress: int, message: str, detail: str = ""):
    _progress["status"] = status
    _progress["phase"] = phase
    _progress["progress"] = progress
    _progress["message"] = message
    _progress["detail"] = detail
    if status == "downloading" and _progress["started_at"] is None:
        _progress["started_at"] = time.time()
    if status in ("done", "error"):
        _progress["done_at"] = time.time()
    save_progress()


async def _download_httpx(
    client: httpx.AsyncClient, url: str, filepath: str, label: str
) -> str:
    """异步下载文件，支持代理、断点续传

    失败时不清除 .tmp 文件（供下次续传）。
    下载完成后将 .tmp 重命名为正式文件。
    """
    if os.path.exists(filepath):
        logger.info(f"GeoNames 缓存命中: {os.path.basename(filepath)}")
        return filepath

    tmp = filepath + ".tmp"
    headers = {}
    resume_pos = 0
    if os.path.exists(tmp):
        resume_pos = os.path.getsize(tmp)
        headers["Range"] = f"bytes={resume_pos}-"
        logger.info(f"续传 {label}: 已有 {resume_pos / 1024 / 1024:.1f} MB，从偏移 {resume_pos} 继续")

    logger.info(f"下载 {label}: {url}" + (f" (续传 @ {resume_pos})" if resume_pos else ""))
    try:
        async with client.stream("GET", url, headers=headers, timeout=600) as resp:
            if resume_pos > 0 and resp.status_code not in (200, 206):
                # 服务器不支持断点续传，从头开始
                logger.warning(f"服务器不支持续传 (status={resp.status_code})，从头下载")
                resume_pos = 0
                os.remove(tmp)
                # 重试不带 Range 头
                async with client.stream("GET", url, timeout=600) as resp2:
                    resp2.raise_for_status()
                    resp = resp2
                resp.raise_for_status()
            elif resume_pos == 0:
                resp.raise_for_status()

            content_range = resp.headers.get("content-range", "")
            total = int(resp.headers.get("content-length", 0))
            if resume_pos > 0 and "bytes" in content_range:
                # 解析 Content-Range: bytes 1234-5678/5679
                parts = content_range.split("/")
                total = int(parts[-1]) if len(parts) >= 2 else total

            downloaded = resume_pos
            last_pct = -1
            mode = "ab" if resume_pos > 0 else "wb"
            with open(tmp, mode) as f:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded * 100 / total)
                        if pct != last_pct and pct % 5 == 0:
                            _update_progress(
                                "downloading", label,
                                pct, f"{label} {pct}% ({downloaded / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB)"
                            )
                            last_pct = pct

        os.rename(tmp, filepath)
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        logger.info(f"下载完成: {os.path.basename(filepath)} ({size_mb:.1f} MB)")
        return filepath
    except Exception as e:
        # 保留 .tmp 文件供重试时续传，不清除！
        error_msg = str(e)
        if not error_msg:
            error_msg = repr(e)
        logger.warning(f"下载中断 {label}: {error_msg}（.tmp 文件已保留，下次可从断点续传）")
        raise GeoNamesDownloadError(f"下载中断 {label}: {error_msg}") from e


class GeoNamesChineseDownloader:
    """GeoNames 中文名下载 + 桥接工具"""

    def __init__(self, cache_dir: str | None = None, proxy: str | None = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.proxy = proxy
        os.makedirs(self.cache_dir, exist_ok=True)

    async def _make_client(self) -> httpx.AsyncClient:
        timeout_sec = 600.0
        kwargs = {"timeout": httpx.Timeout(timeout_sec), "follow_redirects": True}

        # 优先使用传入的 proxy，否则从系统配置读取
        proxy = self.proxy
        if not proxy:
            try:
                from app.controllers.system_config import system_config_controller
                proxy_val = await system_config_controller.get_value("download_proxy", "")
                if proxy_val:
                    proxy = proxy_val
            except Exception:
                pass

        if proxy:
            kwargs["proxy"] = proxy
            logger.info(f"使用代理: {proxy}")
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def reset_progress():
        """重置进度状态，供重试前调用"""
        reset_progress()

    async def download_and_parse(self) -> dict:
        """下载并构建 (country_code, name) → zh_name 映射"""
        client = await self._make_client()

        try:
            # ── 第一步: 下载 allCountries.zip ──
            _update_progress("downloading", "allCountries.zip", 0,
                             "下载 allCountries.zip (~400MB)...")
            all_path = await _download_httpx(
                client, ALL_COUNTRIES_URL,
                os.path.join(self.cache_dir, "allCountries.zip"),
                "allCountries.zip"
            )

            # ── 第二步: 解析 allCountries ──
            _update_progress("parsing", "allCountries.zip", 30,
                             "解析 allCountries.zip 中的行政区域...")
            adm_map: dict[int, tuple[str, str, str]] = {}
            count = 0
            with zipfile.ZipFile(all_path, "r") as zf:
                with zf.open("allCountries.txt", "r") as f:
                    reader = io.TextIOWrapper(f, encoding="utf-8")
                    for line in reader:
                        cols = line.strip().split("\t")
                        if len(cols) < 9:
                            continue
                        feature_class = cols[6]
                        feature_code = cols[7]
                        if feature_class != "A" or feature_code not in ("ADM1", "ADM2"):
                            continue
                        try:
                            geonameid = int(cols[0])
                        except ValueError:
                            continue
                        adm_map[geonameid] = (cols[8], cols[1], feature_code)
                        count += 1
            logger.info(f"提取 {count} 条行政区域条目 (ADM1/ADM2)")

            # ── 第三步: 下载 alternateNamesV2.zip ──
            _update_progress("downloading", "alternateNamesV2.zip", 50,
                             "下载 alternateNamesV2.zip (~300MB)...")
            alt_path = await _download_httpx(
                client, ALTERNATE_NAMES_URL,
                os.path.join(self.cache_dir, "alternateNamesV2.zip"),
                "alternateNamesV2.zip"
            )

            # ── 第四步: 解析 alternateNamesV2 ──
            _update_progress("parsing", "alternateNamesV2.zip", 70,
                             "解析 alternateNamesV2.zip 中文名...")
            geo_to_zh: dict[int, str] = {}
            zh_count = 0
            with zipfile.ZipFile(alt_path, "r") as zf:
                with zf.open("alternateNamesV2.txt", "r") as f:
                    reader = io.TextIOWrapper(f, encoding="utf-8")
                    for line in reader:
                        cols = line.strip().split("\t")
                        if len(cols) < 4:
                            continue
                        if cols[2] not in ("zh", "zho", "chi"):
                            continue
                        try:
                            geonameid = int(cols[1])
                        except ValueError:
                            continue
                        is_preferred = cols[4] if len(cols) >= 5 else ""
                        if geonameid in geo_to_zh and is_preferred != "1":
                            continue
                        geo_to_zh[geonameid] = cols[3]
                        zh_count += 1
            logger.info(f"提取 {zh_count} 条中文名")

            # ── 第五步: 交叉匹配 ──
            _update_progress("bridging", "", 85, "交叉匹配中文名...")
            result: dict[tuple[str, str], str] = {}
            matched = 0
            for geonameid, (cc, en_name, _) in adm_map.items():
                zh = geo_to_zh.get(geonameid)
                if zh:
                    result[(cc, en_name)] = zh
                    matched += 1
            logger.info(
                f"桥接完成: {matched}/{count} 条 ({matched * 100 // max(count, 1)}%)"
            )
            return result
        finally:
            await client.aclose()

    def build_mapping(self, geonames_map: dict, regions: list) -> dict[str, str]:
        """构建 region.code → zh_name 映射。

        geonames_map 的 key 是 (country_alpha2, en_name)。
        对于 STATE：parent 是 COUNTRY → parent.code 即 alpha-2。
        对于 CITY：parent 是 STATE → 需回溯到 parent.parent.code（即 COUNTRY alpha-2）。

        精确匹配失败时回退：名称标准化 → country 内模糊匹配 → 跨国家唯一匹配。
        """
        result: dict[str, str] = {}
        matched = 0

        # ── 预建 country_code → {normalized_en_name → zh_name} 索引 ──
        country_index: dict[str, dict[str, str]] = {}
        for (cc, en_name), zh in geonames_map.items():
            norm = self._normalize_name(en_name)
            idx = country_index.setdefault(cc, {})
            if norm not in idx:
                idx[norm] = zh

        for region in regions:
            country_code = self._get_country_code(region)
            if not country_code:
                continue

            # ── 1. 精确匹配 ──
            zh = geonames_map.get((country_code, region.name))
            if zh:
                result[region.code] = zh
                matched += 1
                continue

            # ── 2. 名称标准化后精确查找 ──
            norm_name = self._normalize_name(region.name)
            if norm_name != region.name:
                zh = geonames_map.get((country_code, norm_name))
                if zh:
                    result[region.code] = zh
                    matched += 1
                    continue

            # ── 3. country 内标准化模糊匹配 ──
            idx = country_index.get(country_code)
            if idx and norm_name in idx:
                result[region.code] = idx[norm_name]
                matched += 1
                continue

            # ── 4. 跨国家唯一匹配（名称全球唯一时兜底） ──
            candidates = []
            for cc, idx_cc in country_index.items():
                if norm_name in idx_cc:
                    candidates.append(idx_cc[norm_name])
            if len(candidates) == 1:
                result[region.code] = candidates[0]
                matched += 1

        logger.info(
            f"Region 桥接: {matched}/{len(regions)} 条"
            f" ({matched * 100 // max(len(regions), 1)}%)"
        )
        return result

    @staticmethod
    def _get_country_code(region) -> str | None:
        """获取 region 所属的 COUNTRY 级别 ISO alpha-2 代码。

        STATE: parent 是 COUNTRY，取 parent.code。
        CITY:  parent 是 STATE，取 parent.parent.code（即 COUNTRY）。
        """
        if not hasattr(region, "parent") or not region.parent:
            return None
        if region.region_type and str(region.region_type) == "CITY":
            grandparent = getattr(region.parent, "parent", None)
            return grandparent.code if grandparent else None
        return region.parent.code

    @staticmethod
    def _normalize_name(name: str) -> str:
        """标准化地名：去除变音符号、括号内容、多余空格，统一小写。"""
        import re
        import unicodedata
        # 去除括号及其内容: "Foo (Bar)" → "Foo"
        name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
        # Unicode NFKD 分解，过滤组合字符（é→e, ñ→n, ü→u）
        nfkd = unicodedata.normalize("NFKD", name)
        name = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
        # 合并空白，小写
        name = re.sub(r"\s+", " ", name).strip().lower()
        return name

    async def apply_mapping(self, regions: list, mapping: dict[str, str]) -> int:
        updated = 0
        for region in regions:
            zh = mapping.get(region.code)
            if zh and region.local_name != zh:
                region.local_name = zh
                await region.save(update_fields=["local_name"])
                updated += 1
        return updated

    def save_cache(self, mapping: dict[str, str], path: str | None = None):
        if path is None:
            path = os.path.join(self.cache_dir, "geonames_zh_map.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        logger.info(f"映射已缓存: {path} ({len(mapping)} 条)")

    def load_cache(self, path: str | None = None) -> dict[str, str] | None:
        if path is None:
            path = os.path.join(self.cache_dir, "geonames_zh_map.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def fill_local_names(self, force_download: bool = False) -> dict:
        """一站式流程。失败时写 error 进度但不抛异常"""
        from app.models.admin import Region
        from app.models.enums import RegionType

        state_regions = await Region.filter(region_type=RegionType.STATE).prefetch_related("parent")
        city_regions = await Region.filter(region_type=RegionType.CITY).prefetch_related("parent")
        all_regions = list(state_regions) + list(city_regions)

        if not all_regions:
            _update_progress("done", "", 100, "无数据需要填充")
            return {"downloaded": False, "matched": 0, "updated": 0,
                    "total_state": 0, "total_city": 0, "source": "empty"}

        # 有缓存 → 秒级回填
        if not force_download:
            cached = self.load_cache()
            if cached:
                _update_progress("updating", "", 95, f"从缓存回填 {len(cached)} 条中文名...")
                updated = await self.apply_mapping(all_regions, cached)
                _update_progress("done", "", 100, f"完成: 已更新 {updated} 条")
                return {"downloaded": False, "matched": len(cached), "updated": updated,
                        "total_state": len(state_regions), "total_city": len(city_regions),
                        "source": "cache"}

        # 下载（首次或强制刷新）
        try:
            geonames_map = await self.download_and_parse()
            mapping = self.build_mapping(geonames_map, all_regions)
            self.save_cache(mapping)

            _update_progress("updating", "", 95, f"写入数据库 ({len(mapping)} 条)...")
            updated = await self.apply_mapping(all_regions, mapping)
            _update_progress("done", "", 100, f"完成: 匹配 {len(mapping)} 条，已更新 {updated} 条")
            return {"downloaded": True, "matched": len(mapping), "updated": updated,
                    "total_state": len(state_regions), "total_city": len(city_regions),
                    "source": "download"}
        except Exception as e:
            error_msg = str(e)
            # 截断过长错误信息
            if len(error_msg) > 300:
                error_msg = error_msg[:300] + "..."
            _update_progress("error", "", 0, f"下载失败: {error_msg}", detail=error_msg)
            # 不抛异常，前端通过轮询 progress 感知失败并重试
            return {"downloaded": True, "matched": 0, "updated": 0,
                    "total_state": len(state_regions), "total_city": len(city_regions),
                    "source": "error", "error": error_msg}


async def fill_region_local_names(force_download: bool = False, proxy: str | None = None) -> dict:
    downloader = GeoNamesChineseDownloader(proxy=proxy)
    return await downloader.fill_local_names(force_download=force_download)
