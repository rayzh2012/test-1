import os
import tempfile
import unittest

from gmail_single_sender import (
    SingleSenderRegistry,
    idempotency_key,
    payload_fingerprint,
)


class SingleSenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "registry.sqlite3")
        self.registry = SingleSenderRegistry(self.db_path)
        self.recipient = "aisha.chaudry@dcls.clcj.ca"
        self.thread = "odsp matter / dcls accommodation"
        self.intent = "odsp.remote_accommodation"

    def tearDown(self):
        self.registry.close()
        self.tmp.cleanup()

    def test_semantically_equivalent_rewording_collides(self):
        key1 = idempotency_key(self.recipient, self.thread, self.intent)
        key2 = idempotency_key("Aisha.Chaudry@DCLS.CLCJ.CA", " ODSP   matter / DCLS accommodation ", "ODSP.REMOTE_ACCOMMODATION")
        self.assertEqual(key1, key2)

        fp1 = payload_fingerprint(self.recipient, "Re: Your ODSP Matter", "I cannot attend in person. Please accommodate me by email.")
        fp2 = payload_fingerprint(self.recipient, "Medical Accommodation Request – Your ODSP Matter", "Because of POTS I cannot safely attend. Please arrange remote participation.")
        self.assertNotEqual(fp1, fp2, "exact payload fingerprints should remain distinct for audit")

    def test_second_writer_is_denied_while_sending(self):
        fp1 = payload_fingerprint(self.recipient, "Re: Your ODSP Matter", "remote accommodation request")
        ok1, first = self.registry.acquire_send_lease(
            recipient=self.recipient,
            semantic_thread=self.thread,
            intent=self.intent,
            payload_fp=fp1,
        )
        self.assertTrue(ok1)
        self.assertEqual(first.state, "SENDING")

        fp2 = payload_fingerprint(self.recipient, "Different subject", "same semantic request with rewording")
        ok2, second = self.registry.acquire_send_lease(
            recipient=self.recipient,
            semantic_thread=self.thread,
            intent=self.intent,
            payload_fp=fp2,
        )
        self.assertFalse(ok2)
        self.assertEqual(second.attempt_count, 1)

    def test_error_then_sent_readback_becomes_verified_no_retry(self):
        fp = payload_fingerprint(self.recipient, "Re: Your ODSP Matter", "remote accommodation request")
        ok, rec = self.registry.acquire_send_lease(
            recipient=self.recipient,
            semantic_thread=self.thread,
            intent=self.intent,
            payload_fp=fp,
        )
        self.assertTrue(ok)
        self.registry.mark_failure(rec.key, "FAILED_PAYLOAD", "Failed to build message payload")

        state = self.registry.reconcile_after_error(rec.key, "1a012dd48e42d83f")
        self.assertEqual(state, "VERIFIED")

        ok_retry, after = self.registry.acquire_send_lease(
            recipient=self.recipient,
            semantic_thread=self.thread,
            intent=self.intent,
            payload_fp=fp,
            allow_retry_after_failure=True,
        )
        self.assertFalse(ok_retry)
        self.assertEqual(after.state, "VERIFIED")
        self.assertEqual(after.attempt_count, 1)

    def test_one_retry_only_after_failed_reconciliation(self):
        fp = payload_fingerprint(self.recipient, "Re: Your ODSP Matter", "remote accommodation request")
        ok, rec = self.registry.acquire_send_lease(
            recipient=self.recipient,
            semantic_thread=self.thread,
            intent=self.intent,
            payload_fp=fp,
        )
        self.assertTrue(ok)
        self.registry.mark_failure(rec.key, "FAILED_PAYLOAD", "payload error")
        state = self.registry.reconcile_after_error(rec.key, None)
        self.assertEqual(state, "FAILED_PAYLOAD")

        ok_retry, retry = self.registry.acquire_send_lease(
            recipient=self.recipient,
            semantic_thread=self.thread,
            intent=self.intent,
            payload_fp=fp,
            allow_retry_after_failure=True,
        )
        self.assertTrue(ok_retry)
        self.assertEqual(retry.attempt_count, 2)

        self.registry.mark_failure(retry.key, "FAILED_TRANSPORT", "timeout")
        self.registry.reconcile_after_error(retry.key, None)
        ok_third, third = self.registry.acquire_send_lease(
            recipient=self.recipient,
            semantic_thread=self.thread,
            intent=self.intent,
            payload_fp=fp,
            allow_retry_after_failure=True,
        )
        self.assertFalse(ok_third)
        self.assertEqual(third.attempt_count, 2)


if __name__ == "__main__":
    unittest.main()
