"""文件操作辅助工具"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


async def safe_delete_file(file_path: str, model_class, exclude_record_id: int) -> bool:
    """安全删除物理文件：仅当没有其他数据库记录引用该文件时才执行删除。

    用于"复制到工作区"场景 —— 复制操作只创建数据库记录（多记录指向同一物理文件）。
    删除记录时需检查是否还有其他记录引用同一文件，避免破坏其他工作区的数据。

    Args:
        file_path: 物理文件路径
        model_class: Tortoise ORM 模型类（如 OriginalSheet, StaticFile 等）
        exclude_record_id: 当前待删除记录的 ID（排除自身）

    Returns:
        True 表示文件已被删除，False 表示文件被其他记录引用而保留
    """
    if not file_path or not os.path.exists(file_path):
        return False

    # 检查同一模型中是否有其他记录引用同一文件
    other_count = await model_class.filter(
        file_path=file_path
    ).exclude(id=exclude_record_id).count()

    if other_count > 0:
        logger.info(
            f"文件被 {other_count} 条其他 {model_class.__name__} 记录引用，跳过物理删除: {file_path}"
        )
        return False

    try:
        os.remove(file_path)
        logger.info(f"已删除文件（无其他引用）: {file_path}")
        return True
    except OSError as e:
        logger.warning(f"删除文件失败: {file_path}, {e}")
        return False
