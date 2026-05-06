import json
from collections import defaultdict

class DuplicateRepository:
    def __init__(self, root_context):
        self.ctx = root_context

    def build_hash_db(self, entries, hash_calculator):
        hash_db = {}
        for e in entries:
            h = hash_calculator.compute_hash(e.path)
            hash_db[e.path] = h

        path = self.ctx.data_root / "hash_db.json"
        path.write_text(json.dumps(hash_db, indent=2), encoding="utf-8")
        return hash_db

    def find_duplicates(self, hash_db):
        groups = defaultdict(list)
        for path, h in hash_db.items():
            groups[h].append(path)
        return {h: v for h, v in groups.items() if len(v) > 1}

    def save_duplicates(self, groups):
        path = self.ctx.data_root / "duplicates.json"
        path.write_text(json.dumps(groups, indent=2), encoding="utf-8")

    def build_duplicate_report(self, groups):
        lines = ["hash,path"]
        for h, paths in groups.items():
            for p in paths:
                lines.append(f"{h},{p}")
        return "\n".join(lines)
