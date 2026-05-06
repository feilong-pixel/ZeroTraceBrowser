from pydantic import BaseModel
from typing import Optional


class ImageEntry(BaseModel):
    """
    ZeroTraceBrowser 的索引条目。
    对应 index.json 中的每一项。
    """

    # 文件路径（绝对路径）
    path: str

    # 相对 root 的路径（前端展示、删除、恢复都用它）
    relative_path: str

    # 文件的唯一哈希（用于重复检测）
    hash: Optional[str] = None

    # 拍摄时间（EXIF 或文件时间）
    timestamp: Optional[str] = None

    # 图像尺寸
    width: Optional[int] = None
    height: Optional[int] = None
