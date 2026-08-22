from enum import Enum


class RouteDecision(Enum):
    EPISODIC = "episodic"
    DROP = "drop"


class MemoryRouter:
    def __init__(self, episodic_memory):
        self.episodic_memory = episodic_memory

    def route(self, item):
        if not item:
            return RouteDecision.DROP

        content = item.get("content", "")
        metadata = item.get("metadata", {})

        important = metadata.get("important", False)
        has_context = bool(content.strip())

        if important or has_context:
            self.episodic_memory.add(
                content=content,
                metadata=metadata,
            )
            return RouteDecision.EPISODIC

        return RouteDecision.DROP
