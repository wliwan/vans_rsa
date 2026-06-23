"""文档图片提取工具 — 从 PPT/PPTX、DOC/DOCX、XLS/XLSX、PDF 中提取所有图片"""

import io
import os
import uuid
from typing import List, Optional, Tuple

from PIL import Image

from app.log import logger
from app.settings.config import settings

EXTRACT_TEMP_DIR = os.path.join(settings.BASE_DIR, "uploads", "temp_extracted")


def _ensure_temp_dir() -> str:
    os.makedirs(EXTRACT_TEMP_DIR, exist_ok=True)
    return EXTRACT_TEMP_DIR


def _get_ext(original_name: str) -> str:
    """规范化扩展名"""
    return os.path.splitext(original_name)[1].lower() if "." in original_name else ".bin"


def _image_properties(data: bytes, default_format: str = "PNG") -> dict:
    """从 bytes 中提取图片属性（宽高、格式等）"""
    props = {"is_image": True}
    try:
        img = Image.open(io.BytesIO(data))
        props["width"], props["height"] = img.size
        props["color_mode"] = img.mode
        mode_bits = {"1": 1, "L": 8, "P": 8, "RGB": 24, "LAB": 24, "HSV": 24, "YCbCr": 24, "RGBA": 32, "CMYK": 32, "I;16": 16, "F": 32}
        props["bit_depth"] = mode_bits.get(img.mode)
        fmt = img.format
        props["format_type"] = fmt.upper() if fmt else default_format.upper()
        dpi = img.info.get("dpi")
        if dpi:
            props["dpi"] = float(dpi[0]) if isinstance(dpi, (tuple, list)) else float(dpi)
        img.close()
    except Exception as e:
        logger.warning(f"读取图片属性失败: {e}")
        props["format_type"] = default_format.upper()
    return props


def _save_temp_image(data: bytes, ext: str = ".png") -> Tuple[str, int]:
    """保存到临时目录，返回 (文件路径, 文件大小)"""
    _ensure_temp_dir()
    unique = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(EXTRACT_TEMP_DIR, unique)
    with open(path, "wb") as f:
        f.write(data)
    return path, os.path.getsize(path)


# ═══════════════════════════════════════════
#  PPTX 提取
# ═══════════════════════════════════════════

def _find_pptx_image_blobs(pptx_path: str) -> List[Tuple[bytes, str, str]]:
    """
    从 pptx 中提取所有图片。
    返回 [(image_bytes, image_ext, guessed_format), ...]
    使用 python-pptx 遍历 slide 和 slide layout 的 rels
    """
    from pptx import Presentation
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT

    results: List[Tuple[bytes, str, str]] = []
    prs = Presentation(pptx_path)
    seen = set()

    # Helper: 检查 part 是否已处理
    def _check_blob(blob, rel_type):
        h = hash(blob)
        if h in seen:
            return
        seen.add(h)
        ext = ".png"
        fmt = "PNG"
        if b"JFIF" in blob[:10] or blob[:2] == b"\xff\xd8":
            ext = ".jpg"
            fmt = "JPEG"
        elif blob[:4] == b"GIF8":
            ext = ".gif"
            fmt = "GIF"
        elif blob[:2] == b"BM":
            ext = ".bmp"
            fmt = "BMP"
        elif blob[:4] == b"RIFF":
            ext = ".webp"
            fmt = "WEBP"
        elif b"IHDR" in blob[:30] and blob[:8] == b"\x89PNG":
            ext = ".png"
            fmt = "PNG"
        results.append((blob, ext, fmt))

    # 遍历 slides 和 slide layouts
    for slide in prs.slides:
        for rel in slide.part.rels.values():
            if rel.reltype == RT.IMAGE:
                try:
                    _check_blob(rel.target_part.blob, rel.reltype)
                except Exception:
                    pass

    # Slide layouts
    for layout in prs.slide_layouts:
        for rel in layout.part.rels.values():
            if rel.reltype == RT.IMAGE:
                try:
                    _check_blob(rel.target_part.blob, rel.reltype)
                except Exception:
                    pass

    # Slide masters
    for master in prs.slide_masters:
        for rel in master.part.rels.values():
            if rel.reltype == RT.IMAGE:
                try:
                    _check_blob(rel.target_part.blob, rel.reltype)
                except Exception:
                    pass

    return results


# ═══════════════════════════════════════════
#  DOCX 提取
# ═══════════════════════════════════════════

def _find_docx_image_blobs(docx_path: str) -> List[Tuple[bytes, str, str]]:
    """
    从 docx 中提取所有内嵌图片。
    python-docx 访问 document.part 内所有 image rels。
    """
    from docx import Document
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    results: List[Tuple[bytes, str, str]] = []
    doc = Document(docx_path)
    seen = set()

    def _check_blob(blob):
        h = hash(blob)
        if h in seen:
            return
        seen.add(h)
        ext, fmt = ".png", "PNG"
        if b"JFIF" in blob[:10] or blob[:2] == b"\xff\xd8":
            ext, fmt = ".jpg", "JPEG"
        elif blob[:4] == b"GIF8":
            ext, fmt = ".gif", "GIF"
        elif blob[:2] == b"BM":
            ext, fmt = ".bmp", "BMP"
        elif blob[:4] == b"RIFF":
            ext, fmt = ".webp", "WEBP"
        results.append((blob, ext, fmt))

    # 遍历 document part 内所有 image rels
    for rel in doc.part.rels.values():
        if rel.reltype == RT.IMAGE:
            try:
                _check_blob(rel.target_part.blob)
            except Exception:
                pass

    # 也检查 header/footer parts
    for section in doc.sections:
        for header_part_name in ("header", "first_page_header", "even_page_header"):
            try:
                hdr = getattr(section, header_part_name, None)
                if hdr and hdr.part:
                    for rel in hdr.part.rels.values():
                        if rel.reltype == RT.IMAGE:
                            try:
                                _check_blob(rel.target_part.blob)
                            except Exception:
                                pass
            except Exception:
                pass

        for footer_part_name in ("footer", "first_page_footer", "even_page_footer"):
            try:
                ftr = getattr(section, footer_part_name, None)
                if ftr and ftr.part:
                    for rel in ftr.part.rels.values():
                        if rel.reltype == RT.IMAGE:
                            try:
                                _check_blob(rel.target_part.blob)
                            except Exception:
                                pass
            except Exception:
                pass

    return results


# ═══════════════════════════════════════════
#  XLSX 提取
# ═══════════════════════════════════════════

def _find_xlsx_image_blobs(xlsx_path: str) -> List[Tuple[bytes, str, str]]:
    """
    从 xlsx 中提取所有图片。
    使用 openpyxl 遍历所有 worksheet 的 images。
    """
    import openpyxl

    results: List[Tuple[bytes, str, str]] = []
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    seen = set()

    for ws_name in wb.sheetnames:
        ws = wb[ws_name]
        for img in ws._images:
            try:
                blob = img._data()
                h = hash(blob)
                if h in seen:
                    continue
                seen.add(h)
                ext = os.path.splitext(img.path or "image.png")[1].lower() or ".png"
                fmt = ext[1:].upper()
                if fmt == "JPG":
                    fmt = "JPEG"
                results.append((blob, ext, fmt))
            except Exception as e:
                logger.warning(f"提取 xlsx 图片失败 (sheet={ws_name}): {e}")

    wb.close()
    return results


# ═══════════════════════════════════════════
#  PDF 提取
# ═══════════════════════════════════════════

def _find_pdf_image_blobs(pdf_path: str) -> List[Tuple[bytes, str, str]]:
    """
    从 PDF 中提取所有内嵌图片。
    使用 pypdf 遍历所有页的 images。
    """
    from pypdf import PdfReader

    results: List[Tuple[bytes, str, str]] = []
    reader = PdfReader(pdf_path)
    seen = set()

    for page_idx, page in enumerate(reader.pages):
        try:
            for img_key in page.images:
                img = page.images[img_key]
                blob = img.data
                if not blob:
                    continue
                h = hash(blob)
                if h in seen:
                    continue
                seen.add(h)

                # 确定格式
                ext, fmt = ".png", "PNG"
                if b"JFIF" in blob[:10] or blob[:2] == b"\xff\xd8":
                    ext, fmt = ".jpg", "JPEG"
                elif blob[:4] == b"GIF8":
                    ext, fmt = ".gif", "GIF"
                elif blob[:2] == b"BM":
                    ext, fmt = ".bmp", "BMP"
                elif blob[:4] == b"\x89PNG":
                    ext, fmt = ".png", "PNG"

                results.append((blob, ext, fmt))
        except Exception as e:
            logger.warning(f"提取 PDF 图片失败 (page={page_idx}): {e}")

    return results


# ═══════════════════════════════════════════
#  统一入口
# ═══════════════════════════════════════════

EXTRACTORS = {
    ".pptx": _find_pptx_image_blobs,
    ".docx": _find_docx_image_blobs,
    ".xlsx": _find_xlsx_image_blobs,
    ".pdf": _find_pdf_image_blobs,
}

SUPPORTED_EXTENSIONS = list(EXTRACTORS.keys())


def extract_images_from_document(file_data: bytes, original_filename: str) -> List[dict]:
    """
    从文档中提取所有图片，返回图片元数据列表。

    每项包含:
        - temp_path: 临时文件路径
        - file_name: 建议文件名
        - file_size: 文件大小(字节)
        - width / height / color_mode / bit_depth / dpi / format_type

    返回 [] 表示没有提取到图片或格式不支持。
    """
    ext = _get_ext(original_filename)
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 {', '.join(SUPPORTED_EXTENSIONS)}")

    # 写入临时文件供库读取
    _ensure_temp_dir()
    tmp_doc = os.path.join(EXTRACT_TEMP_DIR, f"_doc_{uuid.uuid4().hex}{ext}")
    with open(tmp_doc, "wb") as f:
        f.write(file_data)

    try:
        blobs = extractor(tmp_doc)
    finally:
        # 清理临时文档文件
        try:
            os.remove(tmp_doc)
        except Exception:
            pass

    if not blobs:
        return []

    results: List[dict] = []
    for idx, (blob, img_ext, img_fmt) in enumerate(blobs):
        try:
            temp_path, file_size = _save_temp_image(blob, img_ext)
            props = _image_properties(blob, img_fmt)
            base = os.path.splitext(os.path.basename(original_filename))[0]
            results.append({
                "index": idx,
                "temp_path": temp_path,
                "file_name": f"{base}_image_{idx + 1}{img_ext}",
                "file_size": file_size,
                "is_image": True,
                "width": props.get("width"),
                "height": props.get("height"),
                "color_mode": props.get("color_mode"),
                "bit_depth": props.get("bit_depth"),
                "dpi": props.get("dpi"),
                "format_type": props.get("format_type", img_fmt),
            })
        except Exception as e:
            logger.warning(f"保存提取图片失败 [idx={idx}]: {e}")

    return results
