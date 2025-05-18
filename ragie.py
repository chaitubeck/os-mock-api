from datetime import datetime
import json

class RagieInference:
    def __init__(self, schema_path):
        with open(schema_path, "r") as f:
            self.schema = json.load(f)

        with open("reject_error_codes.json", "r") as r:
            self.reject_codes = {item["code"]: item["description"] for item in json.load(r)}

        # Business-friendly priority mapping
        self.event_priority = {
            "referral-cancelled": 0,
            "delivered": 1,             # Most Confirming
            "in-transit": 1,            # Most Confirming
            "fill-dispensed": 2,        # Completed
            "clear-to-ship": 2,         # Completed
            "claim-reversed": 3,        # Resolved Issue
            "claim-rejected": 4,        # Action Required
            "prior-auth-denied": 4,     # Action Required
            "rx-hold": 5                # Needs Attention
        }

    def extract(self, data):
        events = data.get("events", [])
        if not events:
            return {
                "status": "Unknown",
                "urgency": "low",
                "reason": "No events found.",
                "recommended_action": "No action needed."
            }

        # Sort events by priority (lower number = higher priority) and latest timestamp
        sorted_events = sorted(
            events,
            key=lambda e: (
                self.event_priority.get(e.get("type", "").lower(), 99),
                datetime.fromisoformat(e.get("receivedTimestamp", "1970-01-01T00:00:00").replace("Z", ""))
            )
        )

        latest_event = sorted_events[0]
        event_type = latest_event.get("type", "").lower()
        status = self.schema["status"]["mapping"].get(event_type, event_type.replace("-", " ").title())

        # Urgency
        urgency = "low"
        for rule in self.schema["urgency"]["rules"]:
            if rule.get("if") and eval(rule["if"].replace("status", f"'{status}'")):
                urgency = rule["then"]
                break
            elif "default" in rule:
                urgency = rule["default"]

        # Additional info parsing
        additional_info = {
            item["name"]: item["value"]
            for item in latest_event.get("additionalInfo", [])
            if "name" in item and "value" in item
        }

               # Additional info parsing
        additional_info = {
            item["name"]: item["value"]
            for item in latest_event.get("additionalInfo", [])
            if "name" in item and "value" in item
        }

                # Better fallback-based reason selection
        reason = None
        reason_fields = [
            "Reject Information", "Hold Reason", "Error Detail", "Additional Information",
            "Reason for Hold", "Rejection Message", "Block Reason", "Failure Reason"
        ]

        for key in reason_fields:
            for actual_key in additional_info:
                if actual_key.lower() == key.lower():
                    reason = additional_info[actual_key]
                    break
            if reason:
                break

        # Fallback to comments
        if not reason:
            reason = latest_event.get("comments", "N/A")

        # Cleanup for known code patterns like "Reject Codes:75 - something"
        if "Reject Codes:" in reason:
            parts = reason.split("-", 1)
            if len(parts) == 2:
                reason = parts[1].strip()




        # Recommended Action
        template = self.schema["recommended_action"]["template"]
        recommended_action = template.get(status, template.get("default", "No action needed."))

        return {
            "status": status,
            "urgency": urgency,
            "reason": reason,
            "recommended_action": recommended_action
        }
