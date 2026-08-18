#!/usr/bin/env python3
"""Single-sender/idempotency primitives for Gmail automation.

This module does not send email. It provides the durable state machine that a
Gmail writer must use before/after mutation so independent workers cannot send
semantically equivalent messages twice.

Key idea:
- idempotency_key = recipient + semantic_thread + intent
- payload_fingerprint = exact normalized subject/body/attachments

The idempotency key intentionally excludes exact body text. Two drafts that say
substantially the same thing with different wording should still collide when
they share the same canonical semantic_thread + intent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

VALID_STATES = {"PENDING", "SENDING", "VERIFIED", "FAILED_PAYLOAD", "FAILED_TRANSPORT"}


def _norm_space(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_recipient(value: str) -> str:
    return _norm_space(value).lower()


def normalize_semantic_thread(value: str) -> str:
    return _norm_space(value).lower()


def normalize_intent(value: str) -> str:
    return _norm_space(value).lower().replace(" ", "_")


def idempotency_key(recipient: str, semantic_thread: str, intent: str) -> str:
    material = "\x1f".join(
        [normalize_recipient(recipient), normalize_semantic_thread(semantic_thread), normalize_intent(intent)]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def payload_fingerprint(
    recipient: str,
    subject: str,
    body: str,
    attachments: Optional[Iterable[str]] = None,
) -> str:
    payload = {
        "recipient": normalize_recipient(recipient),
        "subject": _norm_space(subject),
        "body": _norm_space(body),
        "attachments": sorted(_norm_space(x) for x in (attachments or [])),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SendRecord:
    key: str
    recipient: str
    semantic_thread: str
    intent: str
    payload_fingerprint: str
    state: str
    attempt_count: int
    sent_message_id: Optional[str]
    updated_at: float


class SingleSenderRegistry:
    """SQLite-backed durable registry with a unique semantic idempotency key."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS sends (
                idempotency_key TEXT PRIMARY KEY,
                recipient TEXT NOT NULL,
                semantic_thread TEXT NOT NULL,
                intent TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL,
                state TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                sent_message_id TEXT,
                last_error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL,
                event TEXT NOT NULL,
                detail TEXT,
                created_at REAL NOT NULL
            )
            """
        )

    def close(self) -> None:
        self.db.close()

    def _audit(self, key: str, event: str, detail: str = "") -> None:
        self.db.execute(
            "INSERT INTO audit(idempotency_key,event,detail,created_at) VALUES(?,?,?,?)",
            (key, event, detail, time.time()),
        )

    def get(self, key: str) -> Optional[SendRecord]:
        row = self.db.execute("SELECT * FROM sends WHERE idempotency_key=?", (key,)).fetchone()
        if not row:
            return None
        return SendRecord(
            key=row["idempotency_key"],
            recipient=row["recipient"],
            semantic_thread=row["semantic_thread"],
            intent=row["intent"],
            payload_fingerprint=row["payload_fingerprint"],
            state=row["state"],
            attempt_count=row["attempt_count"],
            sent_message_id=row["sent_message_id"],
            updated_at=row["updated_at"],
        )

    def acquire_send_lease(
        self,
        *,
        recipient: str,
        semantic_thread: str,
        intent: str,
        payload_fp: str,
        allow_retry_after_failure: bool = False,
    ) -> tuple[bool, SendRecord]:
        """Atomically acquire the only permitted SENDING lease.

        Rules:
        - new key: PENDING -> SENDING, attempt_count=1
        - SENDING or VERIFIED: deny
        - FAILED_*: deny unless caller has already reconciled Sent and explicitly
          allows one retry; maximum automatic attempts = 2
        """
        key = idempotency_key(recipient, semantic_thread, intent)
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM sends WHERE idempotency_key=?", (key,)).fetchone()
            if row is None:
                self.db.execute(
                    """
                    INSERT INTO sends(
                        idempotency_key,recipient,semantic_thread,intent,payload_fingerprint,
                        state,attempt_count,created_at,updated_at
                    ) VALUES(?,?,?,?,?,'SENDING',1,?,?)
                    """,
                    (
                        key,
                        normalize_recipient(recipient),
                        normalize_semantic_thread(semantic_thread),
                        normalize_intent(intent),
                        payload_fp,
                        now,
                        now,
                    ),
                )
                self._audit(key, "LEASE_ACQUIRED", "attempt=1")
                self.db.execute("COMMIT")
                return True, self.get(key)  # type: ignore[return-value]

            state = row["state"]
            attempts = int(row["attempt_count"])
            if state in {"SENDING", "VERIFIED"}:
                self._audit(key, "LEASE_DENIED", f"state={state}")
                self.db.execute("COMMIT")
                return False, self.get(key)  # type: ignore[return-value]

            if state.startswith("FAILED") and allow_retry_after_failure and attempts < 2:
                self.db.execute(
                    """
                    UPDATE sends
                    SET state='SENDING', attempt_count=attempt_count+1,
                        payload_fingerprint=?, last_error=NULL, updated_at=?
                    WHERE idempotency_key=?
                    """,
                    (payload_fp, now, key),
                )
                self._audit(key, "LEASE_ACQUIRED", f"retry_attempt={attempts + 1}")
                self.db.execute("COMMIT")
                return True, self.get(key)  # type: ignore[return-value]

            self._audit(key, "LEASE_DENIED", f"state={state};attempts={attempts}")
            self.db.execute("COMMIT")
            return False, self.get(key)  # type: ignore[return-value]
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def mark_failure(self, key: str, failure_class: str, error: str) -> None:
        if failure_class not in {"FAILED_PAYLOAD", "FAILED_TRANSPORT"}:
            raise ValueError(f"unsupported failure state: {failure_class}")
        self.db.execute(
            "UPDATE sends SET state=?, last_error=?, updated_at=? WHERE idempotency_key=?",
            (failure_class, error[:2000], time.time(), key),
        )
        self._audit(key, failure_class, error[:2000])

    def mark_verified(self, key: str, sent_message_id: str) -> None:
        self.db.execute(
            """
            UPDATE sends
            SET state='VERIFIED', sent_message_id=?, last_error=NULL, updated_at=?
            WHERE idempotency_key=?
            """,
            (sent_message_id, time.time(), key),
        )
        self._audit(key, "VERIFIED", f"message_id={sent_message_id}")

    def reconcile_after_error(self, key: str, equivalent_sent_message_id: Optional[str]) -> str:
        """Mandatory reconciliation after ANY send/draft tool error.

        If an equivalent message exists in Sent, mark VERIFIED and do not retry.
        If none exists, leave the failed state unchanged; caller may later acquire
        one explicit retry lease.
        """
        if equivalent_sent_message_id:
            self.mark_verified(key, equivalent_sent_message_id)
            self._audit(key, "RECONCILED_SENT_AFTER_ERROR", equivalent_sent_message_id)
            return "VERIFIED"
        self._audit(key, "RECONCILED_NO_SENT_COPY", "retry may be eligible")
        record = self.get(key)
        return record.state if record else "MISSING"


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Gmail semantic idempotency helper")
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--thread", required=True, help="canonical semantic thread key")
    parser.add_argument("--intent", required=True, help="typed intent, e.g. odsp.remote_accommodation")
    parser.add_argument("--subject", default="")
    parser.add_argument("--body", default="")
    args = parser.parse_args()
    out = {
        "idempotency_key": idempotency_key(args.recipient, args.thread, args.intent),
        "payload_fingerprint": payload_fingerprint(args.recipient, args.subject, args.body),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
