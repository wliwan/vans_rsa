"""路网素材 Controller"""
import hashlib
import os
import secrets
import uuid
from typing import List, Optional

from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import Region, RoadMaterial, Skill, AIProxy
from app.schemas.road_material import RoadMaterialCreate, RoadMaterialUpdate
from app.settings.config import settings


class RoadMaterialController(CRUDBase[RoadMaterial, RoadMaterialCreate, RoadMaterialUpdate]):
    UPLOAD_DIR = "uploads/materials"

    def __init__(self):
        super().__init__(model=RoadMaterial)

    # ── 短链接令牌生成 ──
    @staticmethod
    def _gen_short_token() -> str:
        """生成唯一短链接令牌（16字节 = 32十六进制字符）"""
        return secrets.token_hex(16)

    @staticmethod
    def short_url(token: str) -> str:
        """从令牌构造完整短链接"""
        return f"/api/s/{token}"

    # ── 图片属性自动提取 ──
    @staticmethod
    def extract_image_properties(filepath: str) -> dict:
        """提取图片基本属性（大小、分辨率、色彩模式、位深度、DPI、格式、EXIF）"""
        props = {}
        try:
            from PIL import Image, ExifTags
            img = Image.open(filepath)
            props["width"], props["height"] = img.size
            props["color_mode"] = img.mode
            # 位深度
            if img.mode == "1":
                props["bit_depth"] = 1
            elif img.mode == "L":
                props["bit_depth"] = 8
            elif img.mode == "P":
                props["bit_depth"] = 8
            elif img.mode in ("RGB", "LAB", "HSV", "YCbCr"):
                props["bit_depth"] = 24
            elif img.mode in ("RGBA", "CMYK"):
                props["bit_depth"] = 32
            elif img.mode == "I;16":
                props["bit_depth"] = 16
            elif img.mode == "F":
                props["bit_depth"] = 32
            # 格式
            fmt = img.format
            props["format_type"] = fmt.upper() if fmt else os.path.splitext(filepath)[1][1:].upper()
            # DPI
            dpi = img.info.get("dpi")
            if dpi:
                props["dpi"] = float(dpi[0]) if isinstance(dpi, (tuple, list)) else float(dpi)
            # EXIF
            exif_raw = img.getexif()
            if exif_raw:
                exif = {}
                for tag_id, value in exif_raw.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8", errors="replace")
                        except Exception:
                            value = value.hex()
                    exif[tag_name] = str(value)
                props["exif_data"] = exif
            img.close()
        except ImportError:
            logger.warning("Pillow 未安装，无法提取图片属性")
            props["format_type"] = os.path.splitext(filepath)[1][1:].upper()
        except Exception as e:
            logger.warning(f"提取图片属性失败: {e}")
            props["format_type"] = os.path.splitext(filepath)[1][1:].upper()
        return props

    @staticmethod
    def _write_png_metadata(filepath: str, description: str):
        """将 JSON 元数据写入 PNG 的 tEXt 块（作者/相机/GPS 坐标等）。

        仅当 description 是有效的 JSON 且包含已知元数据键时才写入，
        不会对其他格式或普通文本 description 做任何处理。
        """
        import json
        try:
            meta = json.loads(description)
        except (json.JSONDecodeError, TypeError):
            return  # 不是 JSON，跳过

        if not isinstance(meta, dict):
            return

        # 仅处理 PNG
        ext = os.path.splitext(filepath)[1].lower()
        if ext != ".png":
            return

        try:
            from PIL import Image, PngInfo
            img = Image.open(filepath)
            pnginfo = PngInfo()

            # 相机 / 作者
            if "camera" in meta:
                pnginfo.add_text("Camera", str(meta["camera"]))
            if "author" in meta:
                pnginfo.add_text("Author", str(meta["author"]))

            # GPS 坐标
            center = meta.get("center")
            if isinstance(center, dict):
                lat = center.get("lat")
                lon = center.get("lon")
                if lat is not None and lon is not None:
                    pnginfo.add_text("GPSLatitude", str(lat))
                    pnginfo.add_text("GPSLongitude", str(lon))
                    pnginfo.add_text("GPSLatitudeRef", "N" if float(lat) >= 0 else "S")
                    pnginfo.add_text("GPSLongitudeRef", "E" if float(lon) >= 0 else "W")

            # 软件标识
            pnginfo.add_text("Software", "VansRSA Road Network Workbench")

            img.save(filepath, pnginfo=pnginfo)
            logger.info(f"PNG 元数据已写入: {filepath}")
        except Exception as e:
            logger.warning(f"写入 PNG 元数据失败: {e}")

    # ── 上传素材 ──

    async def upload_material(
        self, region_id: int, file_data: bytes, original_filename: str,
        name: str = "", description: str = "", source: str = "upload",
    ) -> RoadMaterial:
        """上传图片素材，自动提取属性"""
        # 确保目录存在
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)

        # 生成唯一文件名
        ext = os.path.splitext(original_filename)[1] or ".png"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(self.UPLOAD_DIR, unique_name)

        # 写入文件
        with open(filepath, "wb") as f:
            f.write(file_data)

        file_size = os.path.getsize(filepath)

        # 写入 PNG 元数据（tEXt 块：作者/相机/GPS）
        self._write_png_metadata(filepath, description)

        # 提取属性
        props = self.extract_image_properties(filepath)

        # 生成短链接令牌
        short_token = self._gen_short_token()

        # 如果没有提供名称，使用原始文件名
        display_name = name or os.path.splitext(original_filename)[0]

        obj = await self.model.create(
            name=display_name,
            description=description,
            region_id=region_id,
            file_name=original_filename,
            file_path=filepath,
            file_size=file_size,
            width=props.get("width"),
            height=props.get("height"),
            color_mode=props.get("color_mode"),
            bit_depth=props.get("bit_depth"),
            dpi=props.get("dpi"),
            format_type=props.get("format_type"),
            exif_data=props.get("exif_data"),
            source=source,
            short_url_token=short_token,
        )
        return obj

    # ── 列表查询 ──
    async def list_materials(
        self, page: int = 1, page_size: int = 20,
        region_id: Optional[int] = None,
        name: str = "",
        source: str = "",
    ):
        q = Q()
        if region_id:
            q &= Q(region_id=region_id)
        if name:
            q &= Q(name__contains=name)
        if source:
            q &= Q(source=source)

        total = await self.model.filter(q).count()
        objs = await (
            self.model.filter(q)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-updated_at")
            .prefetch_related("region")
        )

        data = []
        for obj in objs:
            data.append(self._to_output(obj))
        return total, data

    # ── 获取详情 ──
    async def get_material(self, material_id: int) -> Optional[dict]:
        obj = await self.model.filter(id=material_id).prefetch_related("region").first()
        if not obj:
            return None
        return self._to_output(obj)

    # ── 删除素材 ──
    async def delete_material(self, material_id: int) -> bool:
        obj = await self.model.filter(id=material_id).first()
        if not obj:
            return False
        # 删除物理文件
        try:
            if os.path.exists(obj.file_path):
                os.remove(obj.file_path)
        except Exception as e:
            logger.warning(f"删除文件失败: {e}")
        await obj.delete()
        return True

    # ── 通过短链接令牌获取素材 ──
    async def get_by_short_token(self, token: str) -> Optional[RoadMaterial]:
        return await self.model.filter(short_url_token=token).first()

    # ── 保存处理后的图片 ──
    async def save_processed(
        self, original: RoadMaterial, processed_data: bytes,
        suffix: str = "_processed", source: str = "cv_processed",
        ext: str = ".png",
    ) -> RoadMaterial:
        """保存处理后的图片作为新素材"""
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(self.UPLOAD_DIR, unique_name)

        with open(filepath, "wb") as f:
            f.write(processed_data)

        file_size = os.path.getsize(filepath)
        props = self.extract_image_properties(filepath)
        short_token = self._gen_short_token()

        obj = await self.model.create(
            name=f"{original.name}{suffix}",
            description=original.description,
            region_id=original.region_id,
            file_name=f"{os.path.splitext(original.file_name)[0]}{suffix}{ext}",
            file_path=filepath,
            file_size=file_size,
            width=props.get("width"),
            height=props.get("height"),
            color_mode=props.get("color_mode"),
            bit_depth=props.get("bit_depth"),
            dpi=props.get("dpi"),
            format_type=props.get("format_type"),
            exif_data=props.get("exif_data"),
            source=source,
            short_url_token=short_token,
        )
        return obj

    # ── 输出转换 ──
    def _to_output(self, obj: RoadMaterial) -> dict:
        return {
            "id": obj.id,
            "name": obj.name,
            "description": obj.description,
            "region_id": obj.region_id,
            "file_name": obj.file_name,
            "file_path": obj.file_path,
            "file_size": obj.file_size,
            "width": obj.width,
            "height": obj.height,
            "color_mode": obj.color_mode,
            "bit_depth": obj.bit_depth,
            "dpi": obj.dpi,
            "format_type": obj.format_type,
            "exif_data": obj.exif_data,
            "source": obj.source,
            "short_url_token": obj.short_url_token,
            "short_url": self.short_url(obj.short_url_token),
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }


road_material_controller = RoadMaterialController()