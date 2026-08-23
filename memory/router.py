class PromoteOrDropRouter:
    def route(self, content, metadata=None):
        metadata = metadata or {}

        if not content or not content.strip():
            return {
                "action": "drop",
                "reason": "empty content"
            }

        important = metadata.get("important", False)
        event_type = metadata.get("event_type", "")

        operational_events = {
            "delay",
            "cancellation",
            "diversion",
            "crew_change",
            "aircraft_change",
            "operational_disruption",
        }

        if important or event_type in operational_events:
            return {
                "action": "promote",
                "content": content,
                "metadata": metadata,
                "reason": "operational or important event"
            }

        return {
            "action": "drop",
            "reason": "irrelevant event"
        }


class PromptsGroupRouter(PromoteOrDropRouter):
    pass
