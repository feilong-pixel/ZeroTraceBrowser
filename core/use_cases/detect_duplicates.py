class DetectDuplicatesUseCase:
    def __init__(self, index_repo, dup_repo, task_repo, hash_calculator, root_context):
        self.index_repo = index_repo
        self.dup_repo = dup_repo
        self.task_repo = task_repo
        self.hash_calculator = hash_calculator
        self.ctx = root_context

    def execute(self, root_hash: str, task_id: str):
        entries = self.index_repo.load_index(root_hash)

        # 1. 构建 hash_db.json
        hash_db = self.dup_repo.build_hash_db(entries, self.hash_calculator)

        # 2. 查找重复组
        groups = self.dup_repo.find_duplicates(hash_db)

        # 3. 保存 duplicates.json
        self.dup_repo.save_duplicates(groups)

        # 4. 保存任务报告
        csv_text = self.dup_repo.build_duplicate_report(groups)
        self.task_repo.write_report(task_id, csv_text)

        return {"status": "ok", "groups": len(groups)}

