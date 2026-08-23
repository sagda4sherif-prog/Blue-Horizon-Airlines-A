class PromoteOrDropRouter:
    def route(self, content, metadata=None):
        metadata = metadata or {}

        if not content or not content.strip():
            return {
                "action": "drop",
                "reason": "empty content",
                "matched_keywords": []
            }

        text = content.lower()
        event_type = str(metadata.get("event_type", "")).lower()
        important = metadata.get("important", False)

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

        matched_keywords = [
            event
            for event in operational_events
            if event in text or event in event_type
        ]

        if important or matched_keywords:
            return {
                "action": "promote",
                "content": content,
                "metadata": metadata,
                "reason": "operational or important event",
                "matched_keywords": matched_keywords
            }

        return {
            "action": "drop",
            "reason": "irrelevant event",
            "matched_keywords": []
        }


class PromptsGroupRouter(PromoteOrDropRouter):
    pass
