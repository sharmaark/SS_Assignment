# Challenge 3A: resilience evidence

Run `python scripts/challenge_3a_resilience.py` and save the output here as `output.txt`.

The output must show a confirmed assignment with notification `PENDING` during deliberate provider failure, successful manual retry after recovery, and one `SENT` notification after the commit-then-slow response-loss case. Copy Dispatch logs showing three attempts and exponential backoff with jitter, plus Notification logs for the stable delivery key.

Claim: notification failure is bounded and degrades gracefully. Repeating after an ambiguous timeout does not duplicate delivery.
