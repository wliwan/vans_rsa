"""静态文件 Controller"""
import asyncio
import os
import secrets
import uuid
from typing import List, Optional, Tuple

from tortoise.expressions import Q
from tortoise.transactions import atomic

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import (
    AIProxy, Document, RoadMaterial, Skill, StaticFile, Workspace,
)
from app.schemas.static_file import StaticFileCreate, StaticFileUpdate
from app.settings.config import settings

UPLOAD_DIR = os.path.join(settings.BASE_DIR, "uploads", "static_files")


class StaticFileController(CRUDBase[StaticFile, StaticFileCreate, StaticFileUpdate]):
    def __init__(self):
        super().__init__(model=StaticFile)

    # ── 短链接令牌 ──
    @staticmethod
    def _gen_short_token() -> str:
        return secrets.token_hex(16)

    @staticmethod
    def short_url(token: str) -> str:
        return f"/api/sf/{token}"

    # ── 图片属性提取（复用 RoadMaterial 的 Pillow 提取逻辑） ──
    @staticmethod
    def _extract_image_properties(filepath: str) -> dict:
        """自动提取图片基本属性"""
        props = {}
        try:
            from PIL import Image, ExifTags
            img = Image.open(filepath)
            props["is_image"] = True
            props["width"], props["height"] = img.size
            props["color_mode"] = img.mode
            # 位深度
            mode_bits = {"1": 1, "L": 8, "P": 8, "RGB": 24, "LAB": 24, "HSV": 24, "YCbCr": 24, "RGBA": 32, "CMYK": 32, "I;16": 16, "F": 32}
            props["bit_depth"] = mode_bits.get(img.mode)
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
    def _is_image_ext(ext: str) -> bool:
        """判断扩展名是不是图片"""
        return ext.lower() in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".svg"}

    # ── 上传 ──
    async def upload(
        self, workspace_id: int, file_data: bytes, original_filename: str,
        name: str = "", description: str = "",
        source: str = "upload", source_type: str = "original",
        parent_id: Optional[int] = None,
    ) -> StaticFile:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(original_filename)[1] or ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, unique_name)
        with open(filepath, "wb") as f:
            f.write(file_data)
        file_size = os.path.getsize(filepath)
        display_name = name or os.path.splitext(original_filename)[0]
        short_token = self._gen_short_token()

        # 图片属性
        is_img = self._is_image_ext(ext)
        props = {}
        if is_img:
            props = self._extract_image_properties(filepath)

        obj = await self.model.create(
            workspace_id=workspace_id,
            name=display_name,
            description=description,
            file_name=original_filename,
            file_path=filepath,
            file_size=file_size,
            source_type=source_type,
            is_image=is_img,
            width=props.get("width"),
            height=props.get("height"),
            color_mode=props.get("color_mode"),
            bit_depth=props.get("bit_depth"),
            dpi=props.get("dpi"),
            format_type=props.get("format_type"),
            exif_data=props.get("exif_data"),
            source=source,
            parent_file_id=parent_id,
            short_url_token=short_token,
        )
        return obj

    # ── 列表 ──
    async def list_files(
        self, workspace_id: int, source_type: str,
        page: int = 1, page_size: int = 50,
    ) -> Tuple[int, list]:
        q = Q(workspace_id=workspace_id, source_type=source_type)
        total = await self.model.filter(q).count()
        objs = await (
            self.model.filter(q)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-updated_at")
        )
        data = [self._to_output(obj) for obj in objs]
        return total, data

    # ── 获取所有图片文件（用于CV/AI处理候选） ──
    async def list_image_files(self, workspace_id: int, source_type: str = "original") -> list:
        objs = await self.model.filter(
            workspace_id=workspace_id, source_type=source_type, is_image=True
        ).order_by("-updated_at")
        return [self._to_output(obj) for obj in objs]

    # ── 获取详情 ──
    async def get_file(self, file_id: int) -> Optional[dict]:
        obj = await self.model.filter(id=file_id).first()
        if not obj:
            return None
        return self._to_output(obj)

    # ── 更新元数据 ──
    async def update_file(self, file_id: int, **kwargs) -> bool:
        obj = await self.model.filter(id=file_id).first()
        if not obj:
            return False
        update_fields = {k: v for k, v in kwargs.items() if k in ("name", "description") and v is not None}
        if update_fields:
            await obj.update_from_dict(update_fields).save()
        return True

    # ── 删除 ──
    async def delete_file(self, file_id: int) -> bool:
        obj = await self.model.filter(id=file_id).first()
        if not obj:
            return False
        try:
            if os.path.exists(obj.file_path):
                os.remove(obj.file_path)
        except Exception as e:
            logger.warning(f"删除文件失败: {e}")
        await obj.delete()
        return True

    async def batch_delete(self, file_ids: List[int]) -> int:
        deleted = 0
        for fid in file_ids:
            if await self.delete_file(fid):
                deleted += 1
        return deleted

    # ── 文档图片提取 ──
    async def extract_images_from_document(
        self, file_data: bytes, original_filename: str,
    ) -> List[dict]:
        """从文档文件中提取所有图片，返回图片元数据列表（不写入数据库）"""
        from app.utils.document_image_extractor import extract_images_from_document
        return extract_images_from_document(file_data, original_filename)

    # ── 导入提取的图片到静态文件区 ──
    async def import_extracted_images(
        self, workspace_id: int, temp_paths: List[str],
        file_names: Optional[List[str]] = None,
        source_type: str = "original",
        source_doc_name: str = "",
    ) -> Tuple[List[dict], List[dict]]:
        """将已提取的临时图片导入到静态文件表"""
        import shutil
        results, errors = [], []
        if not file_names:
            file_names = [""] * len(temp_paths)
        while len(file_names) < len(temp_paths):
            file_names.append("")

        for idx, temp_path in enumerate(temp_paths):
            try:
                if not temp_path or not os.path.exists(temp_path):
                    errors.append({"index": idx, "error": "临时文件不存在"})
                    continue
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                ext = os.path.splitext(temp_path)[1] or ".png"
                unique_name = f"{uuid.uuid4().hex}{ext}"
                dest_path = os.path.join(UPLOAD_DIR, unique_name)
                shutil.copy2(temp_path, dest_path)
                file_size = os.path.getsize(dest_path)
                props = self._extract_image_properties(dest_path)
                short_token = self._gen_short_token()
                display_name = file_names[idx] if idx < len(file_names) and file_names[idx] else os.path.basename(temp_path)
                description = f"从文档提取: {source_doc_name}" if source_doc_name else "从文档提取"
                obj = await self.model.create(
                    workspace_id=workspace_id,
                    name=display_name,
                    description=description,
                    file_name=display_name,
                    file_path=dest_path,
                    file_size=file_size,
                    source_type=source_type,
                    is_image=True,
                    width=props.get("width"),
                    height=props.get("height"),
                    color_mode=props.get("color_mode"),
                    bit_depth=props.get("bit_depth"),
                    dpi=props.get("dpi"),
                    format_type=props.get("format_type"),
                    source="document_extract",
                    short_url_token=short_token,
                )
                results.append(self._to_output(obj))
            except Exception as e:
                logger.exception(f"导入提取图片失败 [idx={idx}]: {e}")
                errors.append({"index": idx, "error": str(e)})
        return results, errors

    # ── 通过短链接令牌获取 ──
    async def get_by_short_token(self, token: str) -> Optional[StaticFile]:
        return await self.model.filter(short_url_token=token).first()

    # ── OpenCV 处理 ──
    async def cv_process(
        self, file_ids: List[int], operation: str, params: dict,
        workspace_id: int,
    ) -> Tuple[list, list]:
        from app.utils.image_processor import ImageProcessor
        results, errors = [], []
        for fid in file_ids:
            try:
                obj = await self.model.filter(id=fid).first()
                if not obj:
                    errors.append({"file_id": fid, "error": "文件不存在"})
                    continue
                if not obj.is_image:
                    errors.append({"file_id": fid, "error": "仅支持图片文件"})
                    continue
                if not os.path.exists(obj.file_path):
                    errors.append({"file_id": fid, "error": "文件不存在于磁盘"})
                    continue

                proc = ImageProcessor()
                suffix = f"_{operation}"
                op = operation
                if op == "resize":
                    processed = proc.resize(obj.file_path, width=params.get("width", 800), height=params.get("height", 0))
                elif op == "rotate":
                    processed = proc.rotate(obj.file_path, angle=params.get("angle", 90), scale=params.get("scale", 1.0))
                elif op == "crop":
                    processed = proc.crop(obj.file_path, x=params.get("x", 0), y=params.get("y", 0), width=params.get("width", 200), height=params.get("height", 200))
                elif op == "flip":
                    processed = proc.flip(obj.file_path, direction=params.get("direction", 1))
                elif op == "border":
                    processed = proc.add_border(obj.file_path, top=params.get("top", 10), bottom=params.get("bottom", 10), left=params.get("left", 10), right=params.get("right", 10), color=params.get("color", "#000000"))
                elif op == "brightness":
                    processed = proc.brightness(obj.file_path, value=params.get("value", 1.0))
                elif op == "contrast":
                    processed = proc.contrast(obj.file_path, value=params.get("value", 1.0))
                elif op == "color_space":
                    processed = proc.color_space(obj.file_path, target=params.get("target", "GRAY"))
                elif op == "blur":
                    processed = proc.blur(obj.file_path, kernel_size=params.get("kernel_size", 5), blur_type=params.get("type", "gaussian"))
                elif op == "morphology":
                    processed = proc.morphology(obj.file_path, operation=params.get("operation", "erode"), kernel_size=params.get("kernel_size", 3), iterations=params.get("iterations", 1))
                elif op == "smooth":
                    processed = proc.smooth(obj.file_path, method=params.get("method", "bilateral"), h=params.get("h", 10), template_window=params.get("template_window", 7), search_window=params.get("search_window", 21))
                elif op == "histogram_eq":
                    processed = proc.histogram_eq(obj.file_path, method=params.get("method", "global"), clip_limit=params.get("clip_limit", 2.0), tile_size=params.get("tile_size", 8))
                elif op == "remove_bg":
                    processed = proc.remove_bg(obj.file_path, method=params.get("method", "grabcut"), margin=params.get("margin", 10))
                else:
                    errors.append({"file_id": fid, "error": f"不支持的操作: {op}"})
                    continue

                new_obj = await self._save_processed(obj, processed, workspace_id, suffix, "cv_processed", ".png")
                results.append(self._to_output(new_obj))
            except Exception as e:
                logger.exception(f"OpenCV处理文件 {fid} 失败")
                errors.append({"file_id": fid, "error": str(e)})
        return results, errors

    # ── AI 处理 ──
    async def ai_process(
        self, file_ids: List[int], ai_proxy_id: int,
        prompt: str, workspace_id: int,
    ) -> Tuple[list, list]:
        from app.utils.volcengine_visual import volcengine_visual
        proxy = await AIProxy.filter(id=ai_proxy_id).first()
        if not proxy or not proxy.token or not proxy.model:
            raise ValueError("AI代理配置不完整")
        try:
            ak, sk, req_key = volcengine_visual.parse_ai_proxy_credentials(proxy.token, proxy.model)
        except ValueError as e:
            raise ValueError(f"AI代理凭证解析失败: {e}")

        results, errors = [], []
        for fid in file_ids:
            try:
                obj = await self.model.filter(id=fid).first()
                if not obj:
                    errors.append({"file_id": fid, "error": "文件不存在"})
                    continue
                if not obj.is_image:
                    errors.append({"file_id": fid, "error": "仅支持图片文件"})
                    continue
                with open(obj.file_path, "rb") as f:
                    image_data = f.read()
                processed_data = await volcengine_visual.process_image(
                    image_data=image_data, access_key=ak, secret_key=sk,
                    req_key=req_key, prompt=prompt,
                )
                new_obj = await self._save_processed(obj, processed_data, workspace_id, "_ai", "ai_generated", ".png")
                results.append(self._to_output(new_obj))
            except Exception as e:
                logger.exception(f"AI处理文件 {fid} 失败")
                errors.append({"file_id": fid, "error": str(e)})
        return results, errors

    # ── 保存处理后图片 ──
    async def _save_processed(
        self, original: StaticFile, processed_data: bytes,
        workspace_id: int, suffix: str, source: str = "cv_processed",
        ext: str = ".png",
    ) -> StaticFile:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_DIR, unique_name)
        with open(filepath, "wb") as f:
            f.write(processed_data)
        file_size = os.path.getsize(filepath)
        props = self._extract_image_properties(filepath)
        short_token = self._gen_short_token()
        obj = await self.model.create(
            workspace_id=workspace_id,
            name=f"{original.name}{suffix}",
            description=original.description,
            file_name=f"{os.path.splitext(original.file_name)[0]}{suffix}{ext}",
            file_path=filepath,
            file_size=file_size,
            source_type="ai_analysis",
            is_image=True,
            width=props.get("width"),
            height=props.get("height"),
            color_mode=props.get("color_mode"),
            bit_depth=props.get("bit_depth"),
            dpi=props.get("dpi"),
            format_type=props.get("format_type"),
            exif_data=props.get("exif_data"),
            source=source,
            parent_file_id=original.id,
            short_url_token=short_token,
        )
        return obj

    # ── OCR 文本提取 ──
    async def ocr_extract(
        self, file_ids: List[int], workspace_id: int,
    ) -> Tuple[List[dict], List[dict]]:
        """对图片进行 OCR 文本提取，结果保存到文档数据"""
        documents_created = []
        errors = []
        for fid in file_ids:
            try:
                obj = await self.model.filter(id=fid).first()
                if not obj:
                    errors.append({"file_id": fid, "error": "文件不存在"})
                    continue
                if not obj.is_image:
                    errors.append({"file_id": fid, "error": "仅支持图片文件"})
                    continue

                # OCR 提取文本
                text_content = await self._do_ocr(obj.file_path)

                if not text_content.strip():
                    errors.append({"file_id": fid, "error": "未识别到文本内容"})
                    continue

                # 保存为文档（原始文档层级）
                doc_dir = os.path.join(settings.BASE_DIR, "uploads", "documents")
                os.makedirs(doc_dir, exist_ok=True)
                doc_name = f"{obj.name}_OCR.txt"
                doc_file = f"{uuid.uuid4().hex}.txt"
                doc_path = os.path.join(doc_dir, doc_file)
                with open(doc_path, "w", encoding="utf-8") as f:
                    f.write(text_content)

                doc = await Document.create(
                    workspace_id=workspace_id,
                    name=doc_name,
                    file_path=doc_path,
                    file_size=os.path.getsize(doc_path),
                    char_count=len(text_content),
                    source_type="original",
                    import_source="ocr",
                    source_table=obj.name,
                )
                documents_created.append({
                    "id": doc.id, "name": doc.name,
                    "char_count": doc.char_count, "file_path": doc.file_path,
                })
            except Exception as e:
                logger.exception(f"OCR提取文件 {fid} 失败")
                errors.append({"file_id": fid, "error": str(e)})
        return documents_created, errors

    @staticmethod
    async def _do_ocr(filepath: str) -> str:
        """执行 OCR，优先用 PaddleOCR，回退到 pytesseract"""
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            result = ocr.ocr(filepath, cls=True)
            lines = []
            if result and result[0]:
                for line_info in result[0]:
                    text = line_info[1][0] if len(line_info) > 1 else ""
                    if text:
                        lines.append(text)
            return "\n".join(lines)
        except ImportError:
            pass
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(filepath)
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            return text
        except ImportError:
            raise ImportError("请安装 OCR 引擎: pip install paddleocr 或 pip install pytesseract")

    # ── 从路网素材导入 ──
    async def import_from_road_material(
        self, workspace_id: int, material_ids: List[int],
    ) -> Tuple[List[dict], List[dict]]:
        results, errors = [], []
        for mid in material_ids:
            try:
                mat = await RoadMaterial.filter(id=mid).first()
                if not mat:
                    errors.append({"material_id": mid, "error": "素材不存在"})
                    continue

                # 检查文件是否还存在
                src_path = mat.file_path
                if not os.path.exists(src_path):
                    errors.append({"material_id": mid, "error": "素材文件已丢失"})
                    continue

                # 复制文件到静态文件目录
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                ext = os.path.splitext(mat.file_name)[1] or ".png"
                unique_name = f"{uuid.uuid4().hex}{ext}"
                dest_path = os.path.join(UPLOAD_DIR, unique_name)
                import shutil
                shutil.copy2(src_path, dest_path)

                file_size = os.path.getsize(dest_path)
                short_token = self._gen_short_token()

                obj = await self.model.create(
                    workspace_id=workspace_id,
                    name=mat.name,
                    description=mat.description,
                    file_name=mat.file_name,
                    file_path=dest_path,
                    file_size=file_size,
                    source_type="original",
                    is_image=True,
                    width=mat.width,
                    height=mat.height,
                    color_mode=mat.color_mode,
                    bit_depth=mat.bit_depth,
                    dpi=mat.dpi,
                    format_type=mat.format_type,
                    exif_data=mat.exif_data,
                    source="road_material",
                    short_url_token=short_token,
                )
                results.append(self._to_output(obj))
            except Exception as e:
                logger.exception(f"导入路网素材 {mid} 失败")
                errors.append({"material_id": mid, "error": str(e)})
        return results, errors

    # ── 获取有路网素材的区域列表（级联导航用） ──
    @staticmethod
    async def list_material_regions() -> list:
        """列出有路网素材的区域树，含完整层级路径"""
        from app.models.admin import Region, RoadMaterial

        materials = await RoadMaterial.all().select_related("region")
        region_map: dict = {}
        for m in materials:
            r = m.region
            if r.id not in region_map:
                region_map[r.id] = {
                    "id": r.id,
                    "name": r.name,
                    "local_name": r.local_name,
                    "code": r.code,
                    "region_type": str(r.region_type) if hasattr(r.region_type, 'value') else str(r.region_type),
                    "parent_id": r.parent_id,
                    "material_count": 0,
                }
            region_map[r.id]["material_count"] += 1

        # 补全父级区域
        all_parents = set()
        for r in region_map.values():
            if r["parent_id"]:
                all_parents.add(r["parent_id"])
        if all_parents:
            parents = await Region.filter(id__in=list(all_parents)).all()
            for p in parents:
                if p.id not in region_map:
                    region_map[p.id] = {
                        "id": p.id,
                        "name": p.name,
                        "local_name": p.local_name,
                        "code": p.code,
                        "region_type": str(p.region_type) if hasattr(p.region_type, 'value') else str(p.region_type),
                        "parent_id": p.parent_id,
                        "material_count": 0,
                    }

        sorted_regions = sorted(region_map.values(), key=lambda r: (r["region_type"], r["name"]))
        for r in sorted_regions:
            path_parts = []
            cursor = r
            while cursor:
                path_parts.insert(0, cursor["name"])
                pid = cursor["parent_id"]
                cursor = region_map.get(pid) if pid else None
            r["full_path"] = " > ".join(path_parts)
            r["label"] = f'{r["full_path"]} ({r["material_count"]} 素材)'

        return sorted_regions

    @staticmethod
    async def list_materials_by_region(region_id: int, page: int = 1, page_size: int = 500) -> tuple:
        """列出某区域下的路网素材"""
        from app.models.admin import RoadMaterial
        q = RoadMaterial.filter(region_id=region_id)
        total = await q.count()
        objs = await q.offset((page - 1) * page_size).limit(page_size).order_by("-updated_at")
        data = []
        for m in objs:
            data.append({
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "file_name": m.file_name,
                "file_path": m.file_path,
                "file_size": m.file_size,
                "width": m.width,
                "height": m.height,
                "color_mode": m.color_mode,
                "bit_depth": m.bit_depth,
                "dpi": m.dpi,
                "format_type": m.format_type,
                "exif_data": m.exif_data,
                "source": m.source,
                "short_url_token": m.short_url_token,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            })
        return total, data

    # ── 复制到工作区（仅创建记录，不拷贝文件）──
    async def copy_records(
        self, file_ids: List[int], target_workspace_id: int,
    ) -> Tuple[List[dict], List[dict]]:
        """创建指向同一物理文件的数据库记录，生成新的短链接令牌"""
        results, errors = [], []
        for fid in file_ids:
            try:
                src = await self.model.filter(id=fid).first()
                if not src:
                    errors.append({"file_id": fid, "error": "文件不存在"})
                    continue
                if not os.path.exists(src.file_path):
                    errors.append({"file_id": fid, "error": "源文件已丢失"})
                    continue

                new_token = self._gen_short_token()
                obj = await self.model.create(
                    workspace_id=target_workspace_id,
                    name=src.name,
                    description=src.description,
                    file_name=src.file_name,
                    file_path=src.file_path,  # 指向同一文件
                    file_size=src.file_size,
                    source_type=src.source_type,
                    is_image=src.is_image,
                    width=src.width,
                    height=src.height,
                    color_mode=src.color_mode,
                    bit_depth=src.bit_depth,
                    dpi=src.dpi,
                    format_type=src.format_type,
                    exif_data=src.exif_data,
                    source=f"{src.source}_copied",
                    parent_file_id=src.parent_file_id,
                    short_url_token=new_token,
                )
                results.append(self._to_output(obj))
            except Exception as e:
                logger.exception(f"复制静态文件记录 {fid} 失败")
                errors.append({"file_id": fid, "error": str(e)})
        return results, errors

    # ── 输出转换 ──
    def _to_output(self, obj: StaticFile) -> dict:
        return {
            "id": obj.id,
            "workspace_id": obj.workspace_id,
            "name": obj.name,
            "description": obj.description,
            "file_name": obj.file_name,
            "file_path": obj.file_path,
            "file_size": obj.file_size,
            "source_type": obj.source_type,
            "is_image": obj.is_image,
            "width": obj.width,
            "height": obj.height,
            "color_mode": obj.color_mode,
            "bit_depth": obj.bit_depth,
            "dpi": obj.dpi,
            "format_type": obj.format_type,
            "exif_data": obj.exif_data,
            "source": obj.source,
            "parent_file_id": obj.parent_file_id,
            "short_url_token": obj.short_url_token,
            "short_url": self.short_url(obj.short_url_token) if obj.short_url_token else None,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }


static_file_controller = StaticFileController()
