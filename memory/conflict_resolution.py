from datetime import datetime


class ConflictResolution:
    def resolve(self, old_value, new_value):
        if old_value == new_value:
            return {
                "value": old_value,
                "reason": "no_conflict"
            }

        return {
            "value": new_value,
            "reason": "new_value_selected"
        }

    def resolve_records(self, old_record, new_record):
        if old_record is None:
            return {
                "value": new_record["value"],
                "metadata": new_record.get("metadata", {}),
                "updated_at": new_record.get("updated_at", datetime.utcnow()),
                "reason": "new_record"
            }

        if new_record is None:
            return {
                "value": old_record["value"],
                "metadata": old_record.get("metadata", {}),
                "updated_at": old_record.get("updated_at", datetime.utcnow()),
                "reason": "no_new_record"
            }

        old_time = old_record.get("updated_at")
        new_time = new_record.get("updated_at")

        if old_time is None or new_time is None:
            return {
                "value": new_record["value"],
                "metadata": new_record.get("metadata", {}),
                "updated_at": new_time or datetime.utcnow(),
                "reason": "missing_timestamp"
            }

        if new_time >= old_time:
            return {
                "value": new_record["value"],
                "metadata": new_record.get("metadata", {}),
                "updated_at": new_time,
                "reason": "newer_record"
            }

        return {
            "value": old_record["value"],
            "metadata": old_record.get("metadata", {}),
            "updated_at": old_time,
            "reason": "older_record_rejected"
        }
