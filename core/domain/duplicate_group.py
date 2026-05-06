from pydantic import BaseModel
from typing import List


class DuplicateGroup(BaseModel):
    """
    ZeroTraceBrowser 的重复文件分组。
    对应 duplicates.json 中的每一组。
    """

    # 哈希值（重复组的 key）
    hash: str

    # 属于该重复组的所有文件路径（绝对路径）
    paths: List[str]
