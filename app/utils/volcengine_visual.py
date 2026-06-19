"""火山引擎视觉服务（Volcengine VisualService）工具"""
import asyncio
import base64
import logging

logger = logging.getLogger(__name__)


class VolcengineVisualService:
    """火山引擎视觉服务封装

    API 参数来源：
    - token 字段：逗号分隔 → access_key, secret_key
    - model 字段：req_key
    """

    @staticmethod
    async def process_image(
        image_data: bytes,
        access_key: str,
        secret_key: str,
        req_key: str,
        prompt: str = "",
        return_url: bool = False,
    ) -> bytes:
        """
        调用火山引擎视觉服务处理图片

        Args:
            image_data: 原始图片字节数据
            access_key: 火山引擎 Access Key
            secret_key: 火山引擎 Secret Key
            req_key: 模型 req_key（如 high_aes_general_v20_L）
            prompt: 处理提示词
            return_url: 是否返回 URL（默认返回图片字节）

        Returns:
            处理后的图片字节数据
        """
        try:
            from volcengine.visual.VisualService import VisualService
        except ImportError:
            raise ImportError("请安装火山引擎视觉SDK: pip install volcengine-python-sdk[visual]")

        visual_service = VisualService()
        visual_service.set_ak(access_key)
        visual_service.set_sk(secret_key)

        # 将图片转为 base64
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        # 根据不同的 req_key 构建请求参数
        # 通用高清分割/美化等场景
        form = {
            "req_key": req_key,
            "image_urls": [image_base64],  # 支持 base64
            "prompt": prompt,
            "return_url": return_url,
        }

        # 同步调用在线程池中执行
        def _call():
            try:
                resp = visual_service.high_aes_smart_drawing(form)
                return resp
            except Exception as e:
                logger.error(f"火山引擎视觉服务调用失败: {e}")
                raise

        resp = await asyncio.to_thread(_call)

        # 解析响应，获取图片
        if resp and resp.get("code") == 10000:
            data = resp.get("data", {})
            # 获取处理后的图片（base64）
            if "image_urls" in data and data["image_urls"]:
                result_b64 = data["image_urls"][0]
                return base64.b64decode(result_b64)
            elif "binary_data_base64" in data and data["binary_data_base64"]:
                result_list = data["binary_data_base64"]
                if isinstance(result_list, list):
                    result_b64 = result_list[0]
                else:
                    result_b64 = result_list
                return base64.b64decode(result_b64)
            else:
                raise ValueError(f"未获取到处理后的图片数据: {resp}")
        else:
            error_msg = resp.get("message", "未知错误") if resp else "无响应"
            raise ValueError(f"火山引擎视觉服务返回错误 (code={resp.get('code') if resp else 'N/A'}): {error_msg}")

    @staticmethod
    def parse_ai_proxy_credentials(token: str, model: str):
        """
        从 AIProxy 字段解析认证信息

        token 格式: access_key,secret_key
        model 字段: req_key

        Returns:
            (access_key, secret_key, req_key)
        """
        parts = token.split(",") if token else []
        if len(parts) < 2:
            raise ValueError("token 字段格式错误，应为 access_key,secret_key（逗号分隔）")
        access_key = parts[0].strip()
        secret_key = parts[1].strip()
        req_key = model.strip() if model else ""
        if not req_key:
            raise ValueError("model 字段（req_key）不能为空")
        return access_key, secret_key, req_key


volcengine_visual = VolcengineVisualService()
