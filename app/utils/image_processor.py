"""OpenCV 图片处理工具"""
from __future__ import annotations

import io
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class ImageProcessor:
    """基于 OpenCV 的图片处理工具"""

    @staticmethod
    def _load_image(filepath: str) -> np.ndarray:
        """加载图片"""
        import cv2
        img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"无法加载图片: {filepath}")
        return img

    @staticmethod
    def _save_image(img: np.ndarray, ext: str = ".png") -> bytes:
        """将 numpy 数组编码为图片字节"""
        import cv2
        success, buf = cv2.imencode(ext, img)
        if not success:
            raise ValueError("图片编码失败")
        return buf.tobytes()

    # ── 几何变换 ──

    @classmethod
    def resize(cls, filepath: str, width: int, height: int = 0) -> bytes:
        """缩放图片"""
        import cv2
        img = cls._load_image(filepath)
        h, w = img.shape[:2]
        if height <= 0:
            height = int(h * width / w)
        resized = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA if width < w else cv2.INTER_CUBIC)
        return cls._save_image(resized, _get_ext(filepath))

    @classmethod
    def rotate(cls, filepath: str, angle: float, scale: float = 1.0) -> bytes:
        """旋转图片"""
        import cv2
        img = cls._load_image(filepath)
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, scale)
        rotated = cv2.warpAffine(img, matrix, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        return cls._save_image(rotated, _get_ext(filepath))

    @classmethod
    def crop(cls, filepath: str, x: int, y: int, width: int, height: int) -> bytes:
        """裁剪图片"""
        img = cls._load_image(filepath)
        cropped = img[y:y + height, x:x + width]
        return cls._save_image(cropped, _get_ext(filepath))

    @classmethod
    def flip(cls, filepath: str, direction: int) -> bytes:
        """翻转图片 (0=垂直, 1=水平, -1=两者)"""
        import cv2
        img = cls._load_image(filepath)
        flipped = cv2.flip(img, direction)
        return cls._save_image(flipped, _get_ext(filepath))

    @classmethod
    def add_border(cls, filepath: str, top: int, bottom: int, left: int, right: int,
                   color: str = "#000000") -> bytes:
        """添加边框"""
        import cv2
        img = cls._load_image(filepath)
        # 解析颜色
        hex_color = color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        if len(img.shape) == 3 and img.shape[2] == 3:
            border_color = (b, g, r)
        elif len(img.shape) == 3 and img.shape[2] == 4:
            border_color = (b, g, r, 255)
        else:
            border_color = (b, g, r)
        bordered = cv2.copyMakeBorder(img, top, bottom, left, right,
                                       cv2.BORDER_CONSTANT, value=border_color)
        return cls._save_image(bordered, _get_ext(filepath))

    # ── 色彩光影 ──

    @classmethod
    def brightness(cls, filepath: str, value: float) -> bytes:
        """调整亮度 (0=暗, 1=原, >1=亮)"""
        import cv2
        img = cls._load_image(filepath)
        adjusted = cv2.convertScaleAbs(img, alpha=1.0, beta=(value - 1.0) * 255)
        return cls._save_image(adjusted, _get_ext(filepath))

    @classmethod
    def contrast(cls, filepath: str, value: float) -> bytes:
        """调整对比度 (0=灰, 1=原, >1=高对比)"""
        import cv2
        img = cls._load_image(filepath)
        adjusted = cv2.convertScaleAbs(img, alpha=value, beta=0)
        return cls._save_image(adjusted, _get_ext(filepath))

    @classmethod
    def color_space(cls, filepath: str, target: str) -> bytes:
        """转换色彩空间 (RGB/GRAY/HSV/LAB)"""
        import cv2
        img = cls._load_image(filepath)
        target = target.upper()
        if target == "GRAY":
            converted = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif target == "HSV":
            converted = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        elif target == "LAB":
            converted = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        elif target == "RGB":
            converted = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            raise ValueError(f"不支持的色彩空间: {target}")
        return cls._save_image(converted, _get_ext(filepath))

    # ── 图像增强 ──

    @classmethod
    def blur(cls, filepath: str, kernel_size: int = 5, blur_type: str = "gaussian") -> bytes:
        """模糊降噪"""
        import cv2
        img = cls._load_image(filepath)
        if kernel_size % 2 == 0:
            kernel_size += 1
        if blur_type == "median":
            result = cv2.medianBlur(img, kernel_size)
        elif blur_type == "bilateral":
            result = cv2.bilateralFilter(img, kernel_size, 75, 75)
        else:
            result = cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)
        return cls._save_image(result, _get_ext(filepath))

    @classmethod
    def morphology(cls, filepath: str, operation: str, kernel_size: int = 3,
                   iterations: int = 1) -> bytes:
        """形态学处理 (erode/dilate/open/close)"""
        import cv2
        img = cls._load_image(filepath)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        op_map = {
            "erode": cv2.MORPH_ERODE,
            "dilate": cv2.MORPH_DILATE,
            "open": cv2.MORPH_OPEN,
            "close": cv2.MORPH_CLOSE,
        }
        if operation not in op_map:
            raise ValueError(f"不支持的形态学操作: {operation}")
        result = cv2.morphologyEx(img, op_map[operation], kernel, iterations=iterations)
        return cls._save_image(result, _get_ext(filepath))

    @classmethod
    def smooth(cls, filepath: str, method: str = "bilateral",
               h: int = 10, template_window: int = 7, search_window: int = 21) -> bytes:
        """纹理平滑"""
        import cv2
        img = cls._load_image(filepath)
        if method == "nlmeans":
            result = cv2.fastNlMeansDenoisingColored(img, None, h, h, template_window, search_window)
        else:
            result = cv2.bilateralFilter(img, 9, h, h)
        return cls._save_image(result, _get_ext(filepath))

    @classmethod
    def histogram_eq(cls, filepath: str, method: str = "global",
                     clip_limit: float = 2.0, tile_size: int = 8) -> bytes:
        """直方图均衡化"""
        import cv2
        img = cls._load_image(filepath)
        if method == "clahe":
            # CLAHE 需要灰度图
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
            result = clahe.apply(gray)
        else:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            result = cv2.equalizeHist(gray)
        return cls._save_image(result, _get_ext(filepath))

    # ── 去背景 ──

    @classmethod
    def remove_bg(cls, filepath: str, method: str = "grabcut", margin: int = 10) -> bytes:
        """
        自动抠图去背景
        - grabcut: 基于统计建模的 GrabCut 算法
        - threshold: 基于边缘统计的自适应阈值
        """
        import cv2
        img = cls._load_image(filepath)

        if method == "threshold":
            result = cls._remove_bg_threshold(img, margin)
        else:
            result = cls._remove_bg_grabcut(img, margin)

        return cls._save_image(result, ".png")  # 去背景后需要 PNG 保留透明度

    @classmethod
    def _remove_bg_grabcut(cls, img: np.ndarray, margin: int) -> np.ndarray:
        """GrabCut 算法去背景"""
        import cv2
        import numpy as np
        h, w = img.shape[:2]

        # 确保有3通道用于GrabCut
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img_rgb = img[:, :, :3]
            alpha = img[:, :, 3]
        else:
            img_rgb = img.copy()
            alpha = None

        mask = np.zeros((h, w), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        # 矩形区域：稍微内缩 margin 像素
        rect = (margin, margin, w - 2 * margin, h - 2 * margin)

        cv2.grabCut(img_rgb if alpha is None else img_rgb, mask, rect,
                     bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)

        # 创建二值掩码：0=背景, 2=可能背景, 1=前景, 3=可能前景
        fg_mask = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)

        # 创建 RGBA 结果
        if img.shape[2] == 3:
            result = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            result[:, :, 3] = fg_mask
        else:
            result = img.copy()
            result[:, :, 3] = fg_mask

        return result

    @classmethod
    def _remove_bg_threshold(cls, img: np.ndarray, margin: int) -> np.ndarray:
        """基于边缘统计的自适应阈值去背景"""
        import cv2
        import numpy as np
        h, w = img.shape[:2]

        if len(img.shape) == 2:
            gray = img
        elif img.shape[2] == 4:
            gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)

        # 膨胀边缘区域
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (margin * 2 + 1, margin * 2 + 1))
        dilated = cv2.dilate(edges, kernel, iterations=2)

        # 在膨胀区域内做 Otsu 阈值分割
        roi_mask = dilated > 0
        if roi_mask.sum() > 0:
            roi_values = gray[roi_mask]
            thresh_val = np.mean(roi_values)

            # 创建前景掩码
            _, fg_mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

            # 形态学清理
            clean_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, clean_kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, clean_kernel)
        else:
            # 回退：Otsu 全局阈值
            _, fg_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 创建 RGBA 结果
        if len(img.shape) == 2:
            result = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:
            result = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        else:
            result = img.copy()
        result[:, :, 3] = fg_mask

        return result


def _get_ext(filepath: str) -> str:
    """获取文件扩展名"""
    import os
    _, ext = os.path.splitext(filepath)
    return ext if ext else ".png"
