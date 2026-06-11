"""HTTP 响应工具"""

from urllib.parse import quote

from fastapi.responses import FileResponse, Response


def make_download_response(
    content: bytes = None,
    path: str = None,
    filename: str = "download",
    media_type: str = "application/octet-stream",
) -> Response:
    """
    创建带 RFC 5987 编码文件名的下载响应，避免中文文件名 latin-1 编码错误。

    用法:
        # FileResponse 方式
        return file_download(path="/path/to/file.xlsx", filename="中文名称.xlsx")

        # bytes 方式
        return file_download(content=pdf_bytes, filename="报告.pdf", media_type="application/pdf")

    内部使用 filename*=UTF-8''xxx 格式编码 Content-Disposition 头。
    """
    encoded = quote(filename, safe="")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}

    if path is not None:
        return FileResponse(path=path, media_type=media_type, headers=headers)
    else:
        return Response(content=content, media_type=media_type, headers=headers)
