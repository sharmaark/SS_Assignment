# Challenge 2: idempotency evidence

Run `python scripts/challenge_2_idempotency.py` and save the output here as `output.txt`.

The output must show two simultaneous HTTP 201 responses with the same assignment ID and body, a sequential replay, HTTP 409 for the same key with a changed payload, one reservation, and one notification record. Copy Dispatch logs containing `concurrent_idempotency_replay` or `idempotency_replay`.

Claim: a unique key stores the canonical request fingerprint and terminal response. Notification independently deduplicates the stable delivery key.
