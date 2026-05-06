from core.domain.timeline_item import TimelineItem

class BuildTimelineUseCase:
    def __init__(self, index_repo, timeline_repo, root_context):
        self.index_repo = index_repo
        self.timeline_repo = timeline_repo
        self.ctx = root_context

    def execute(self, root_hash: str):
        entries = self.index_repo.load_index(root_hash)

        # 按时间排序
        items = self.timeline_repo.build_timeline(entries)

        # 保存 timeline.json
        self.timeline_repo.save_timeline(root_hash, items)

        return {"status": "ok", "count": len(items)}
