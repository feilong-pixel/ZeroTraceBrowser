from pathlib import Path

from core.config.root_config import RootConfig

class SettingsRepository:
    def __init__(self, data_root="data/roots"):
        self.data_root = Path(data_root)
        self.active_file = self.data_root / "active_root.txt"

    # -------------------------
    # Save root.json
    # -------------------------
    def save_root_config(self, config: RootConfig):
        root_dir = self.data_root / config.root_id
        root_dir.mkdir(parents=True, exist_ok=True)
        path = root_dir / "root.json"
        path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    # -------------------------
    # Read root.json
    # -------------------------
    def load_root_config(self, root_id: str) -> RootConfig:
        path = self.data_root / root_id / "root.json"
        return RootConfig.model_validate_json(path.read_text(encoding="utf-8"))

    # -------------------------
    # Set active root
    # -------------------------
    def set_active_root(self, root_id: str):
        self.active_file.write_text(root_id, encoding="utf-8")

    # -------------------------
    # Get active root
    # -------------------------
    def get_active_root(self) -> str:
        return self.active_file.read_text(encoding="utf-8").strip()
