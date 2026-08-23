from memory.short_term import ShortTermMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.router import PromoteOrDropRouter
from memory.consolidation import ConsolidationLayer


class MemoryManager:
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.router = PromoteOrDropRouter()
        self.consolidation = ConsolidationLayer(
            self.episodic,
            self.semantic
        )

    def remember(self, content, metadata=None):
        metadata = metadata or {}

        decision = self.router.route(content, metadata)

        if decision["action"] == "promote":
            episode = self.episodic.store(
                decision["content"],
                decision["metadata"]
            )

            return {
                "action": "promote",
                "episode": episode,
                "reason": decision["reason"]
            }

        return {
            "action": "drop",
            "reason": decision["reason"]
        }

    def run_consolidation(self):
        return self.consolidation.consolidate()

    def recall(self, key):
        return self.semantic.get(key)

    def get_short_term(self):
        return self.short_term.get_all()

    def get_episodes(self):
        return self.episodic.get_all()

    def get_semantic(self):
        return self.semantic.get_all()
