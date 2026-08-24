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

        operational_keywords = {
            "delay",
            "delayed",
            "cancellation",
            "cancelled",
            "diversion",
            "diverted",
            "crew change",
            "crew_change",
            "aircraft change",
            "aircraft_change",
            "assigned aircraft",
            "aircraft",
            "maintenance",
            "disruption",
        }

        matched_keywords = [
            keyword
            for keyword in operational_keywords
            if keyword in text
        ]

        important = metadata.get("important", False)
        event_type = metadata.get("event_type", "")

        if important or event_type or matched_keywords:
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
