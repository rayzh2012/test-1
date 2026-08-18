# Gmail Single Sender Skill

Use this skill for every autonomous Gmail write path.

## Goal
Never allow more than one semantically equivalent outbound email, even when:
- multiple agents/runs are active;
- subjects differ (`Re:` vs a new subject);
- the body is reworded;
- a connector reports timeout or payload-build failure after another writer already sent;
- a fallback draft/send path is attempted.

## Required identity fields
Before every write, derive and persist:
1. `recipient` — normalized mailbox address.
2. `semantic_thread` — canonical topic key independent of Gmail `thread_id`.
3. `intent` — typed action, e.g. `odsp.remote_accommodation`, `recruiting.resume_share`, `interview.confirm_availability`.
4. `idempotency_key = SHA256(recipient | semantic_thread | intent)`.
5. `payload_fingerprint` — exact normalized recipient + subject + body + attachments fingerprint for audit only.

The body fingerprint MUST NOT be the idempotency key. Rewording the same request must still collide.

## Mandatory pre-send gate
Immediately before any Gmail mutation:
1. Read the complete relevant inbound thread.
2. Search/read Sent for the recipient and semantic topic, including separate Gmail threads with different subjects.
3. If an equivalent intent already exists in Sent, mark `VERIFIED` and do not send.
4. Acquire the single serialized `SENDING` lease for the idempotency key.
5. If lease acquisition fails because state is `SENDING` or `VERIFIED`, do not send.

## State machine
`PENDING → SENDING → VERIFIED`

Failure states:
- `FAILED_PAYLOAD` — connector could not construct the message payload.
- `FAILED_TRANSPORT` — timeout/network/provider failure.

After ANY error:
1. Do not immediately retry or switch to another write path.
2. Re-read Sent using recipient + semantic topic/intent.
3. If an equivalent message is present, mark `VERIFIED`; stop.
4. If no equivalent Sent copy exists, preserve the exact pending payload and failure state.
5. Permit at most one later automatic retry after a fresh reconciliation.

## Single-writer rule
All autonomous Gmail code paths, orchestrators, fallback agents, drafts-to-send handlers and manual-agent helpers must share the same registry/lease. There must not be independent sender state per workflow.

## Success rule
Tool success is provisional. Report `sent` only after Gmail Sent/thread readback verifies:
- recipient;
- semantic intent/topic;
- expected body/attachment evidence;
- exactly one equivalent outbound message.

## Regression fixture
2026-08-17 DCLS/ODSP accommodation incident:
- two separate outbound messages were sent to `aisha.chaudry@dcls.clcj.ca` within minutes;
- subjects differed but semantic intent was the same: disability/POTS remote accommodation;
- later Gmail write calls returned `Failed to build message payload`;
- Sent readback revealed the duplicate.

This incident is the canonical test: concurrent writers plus a connector error must never produce two equivalent Sent messages.

## Executable helper
Use `tools/gmail_single_sender.py` for semantic keys and durable lease/state behavior. Run regression tests with:

```bash
cd tools
python -m unittest -v test_gmail_single_sender.py
```
