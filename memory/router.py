class PromoteOrDropRouter:
    def route(self, content, metadata=None):
        metadata = metadata or {}

        if not content or not content.strip():
            return {
                "action": "drop",
                "reason": "empty content"
            }

        text = content.lower()

        important = metadata.get("important", False)
        event_type = metadata.get("event_type", "").lower()

        operational_events = {
            "delay",
            "delayed",
            "cancellation",
            "cancelled",
            "diversion",
            "diverted",
            "crew_change",
            "aircraft_change",
            "operational_disruption",
        }

        has_operational_keyword = any(
            event in text or event in event_type
            for event in operational_events
        )

       if important or has_operational_keyword:
    matched_keywords = [
        event
        for event in operational_events
        if event in text or event in event_type
    ]

    return {
        "action": "promote",
        "content": content,
        "metadata": metadata,
        "reason": "operational or important event",
        "matched_keywords": matched_keywords
    }

class PromptsGroupRouter(PromoteOrDropRouter):
    pass
