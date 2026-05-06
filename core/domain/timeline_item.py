from pydantic import BaseModel
from typing import Optional


class TimelineItem(BaseModel):
    """
    ZeroTraceBrowser 的时间线条目。
    对应 timeline.json 中的每一项。
    """

    # 相对路径（前端展示用）
    relative_path: str

    # 时间线排序依据
    timestamp: Optional[str] = None

    # 文件哈希（用于前端快速定位）
    hash: Optional[str] = None
