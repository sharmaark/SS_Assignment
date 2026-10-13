from datetime import datetime, timezone
from uuid import uuid4

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


def public_notification(document: dict) -> dict:
    return {key: value for key, value in document.items() if key != "_id"} | {"id": document["_id"]}


class NotificationRepository:
    def __init__(self, mongodb_url: str, database_name: str):
        self.client = MongoClient(mongodb_url)
        self.db = self.client[database_name]
        self.notifications = self.db.notifications

    def initialise(self) -> None:
        self.client.admin.command("ping")
        self.notifications.create_index("delivery_key", unique=True)

    def health(self) -> None:
        self.client.admin.command("ping")

    def get_by_key(self, delivery_key: str) -> dict | None:
        item = self.notifications.find_one({"delivery_key": delivery_key})
        return public_notification(item) if item else None

    def claim(self, payload: dict) -> tuple[dict, bool]:
        existing = self.notifications.find_one({"delivery_key": payload["delivery_key"]})
        if existing and existing["status"] == "SENT":
            return public_notification(existing), False

        owner_token = str(uuid4())
        now = datetime.now(timezone.utc)
        if not existing:
            document = {
                "_id": str(uuid4()),
                **payload,
                "status": "PROCESSING",
                "owner_token": owner_token,
                "attempts": 1,
                "created_at": now,
                "sent_at": None,
            }
            try:
                self.notifications.insert_one(document)
                return public_notification(document), True
            except DuplicateKeyError:
                pass

        item = self.notifications.find_one_and_update(
            {"delivery_key": payload["delivery_key"], "status": "FAILED"},
            {"$set": {"status": "PROCESSING", "owner_token": owner_token}, "$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if item:
            return public_notification(item), True
        return public_notification(self.notifications.find_one({"delivery_key": payload["delivery_key"]})), False

    def mark_sent(self, delivery_key: str) -> dict:
        item = self.notifications.find_one_and_update(
            {"delivery_key": delivery_key},
            {"$set": {"status": "SENT", "sent_at": datetime.now(timezone.utc), "owner_token": None}},
            return_document=ReturnDocument.AFTER,
        )
        return public_notification(item)

    def mark_failed(self, delivery_key: str) -> dict:
        item = self.notifications.find_one_and_update(
            {"delivery_key": delivery_key, "status": "PROCESSING"},
            {"$set": {"status": "FAILED", "owner_token": None}},
            return_document=ReturnDocument.AFTER,
        )
        return public_notification(item)

    def list_all(self) -> list[dict]:
        return [public_notification(item) for item in self.notifications.find().sort("created_at", 1)]
