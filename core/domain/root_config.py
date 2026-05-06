from pydantic import BaseModel
import uuid

class RootConfig(BaseModel):
    root_id: str
    root_path: str

    @staticmethod
    def create(root_path: str):
        return RootConfig(
            root_id=str(uuid.uuid4()).replace("-", ""),
            root_path=root_path,
        )
