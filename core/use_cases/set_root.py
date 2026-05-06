from pydantic import BaseModel
from core.config.root_config import RootConfig

class SetRootRequest(BaseModel):
    root_path: str

class SetRootUseCase:
    def __init__(self, settings_repo):
        self.settings_repo = settings_repo

    def execute(self, req):
        # 1. 创建 root config
        config = RootConfig.create(req.root_path)

        # 2. 保存 root.json
        self.settings_repo.save_root_config(config)

        # 3. 设置 active root
        self.settings_repo.set_active_root(config.root_id)

        return {"status": "ok", "root_id": config.root_id}

