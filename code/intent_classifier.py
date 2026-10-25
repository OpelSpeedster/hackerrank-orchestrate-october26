"""Intent Classifier: determines whether request authorizes account deletion."""

from typing import Dict, Tuple
from reasoning_agent import reasoning_agent


class IntentClassifier:
    def __init__(self):
        self._cache: Dict[str, Tuple[bool, str]] = {}

    def is_deletion_authorized(self, case_id: str, request_text: str) -> Tuple[bool, str]:
        """Check if request authorizes deletion. Returns (authorized, explanation)."""
        if case_id in self._cache:
            return self._cache[case_id]

        auth, reason = reasoning_agent.classify_deletion_intent(request_text, case_id)
        self._cache[case_id] = (auth, reason)
        return auth, reason


intent_classifier = IntentClassifier()
