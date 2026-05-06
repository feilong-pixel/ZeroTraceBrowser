import json
from core.domain.timeline_item import TimelineItem

class TimelineRepository:
    def __init__(self, root_context):
        self.ctx = root_context

    def build_timeline(self, entries):
        items = []
        for e in entries:
            items.append(
                TimelineItem(
                    relative_path=e.relative_path,
                    timestamp=e.timestamp,
                    hash=e.hash,
                )
            )
        return sorted(items, key=lambda x: x.timestamp or "")
