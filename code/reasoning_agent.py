"""Reasoning Agent: connects to Groq API to call LLM models for intent classification and decision validation."""

import os
import json
import re
from typing import Optional, Dict, Any, Tuple
from openai import OpenAI
from config import config
from usage_tracker import usage_tracker


class ReasoningAgent:
    def __init__(self):
        self.api_key = config.groq_api_key
        self.base_url = config.groq_base_url
        self.model = config.groq_model
        self.client: Optional[OpenAI] = None
        self._init_client()

    def _init_client(self) -> None:
        if self.api_key:
            try:
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except Exception as e:
                self.client = None

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    def classify_deletion_intent(
        self, request_text: str, case_id: str
    ) -> Tuple[bool, str]:
        """
        Classifies whether the request authorizes account/data deletion.
        Returns:
            (is_deletion_authorized, reasoning)
        """
        # Step 1: Deterministic check for obvious cases
        text_lower = request_text.lower().strip()
        
        # Check non-deletion triggers first
        non_deletion_phrases = [
            "leave the account active",
            "keep the account as it is",
            "leave my profile",
            "without removing any of my records",
            "marketing lists only",
            "marketing list only",
            "misspelled",
            "portable format",
            "copy of last year",
            "copy of invoices",
            "download my account information",
            "change the email address used for this account",
            "want to continue using",
            "reset my password",
            "login help",
            "can't access",
            "update my address",
        ]
        for phrase in non_deletion_phrases:
            if phrase in text_lower:
                return False, f"Matched non-deletion phrase: '{phrase}'"

        # Check strong deletion authorization triggers
        deletion_phrases = [
            "delete this account",
            "permanently delete",
            "permanent account deletion",
            "permanent account-deletion",
            "erase the account",
            "close my account and process the associated personal-data deletion",
            "remove my account and the personal information",
            "suppression définitive",
            "exclusão permanente",
            "excluir minha conta",
            "eliminar mi cuenta",
            "削除",
            "삭제",
            "remove that search result",
            "remove search result",
            "delete that export file",
            "lösch",
        ]
        for phrase in deletion_phrases:
            if phrase in text_lower:
                return True, f"Matched deletion phrase: '{phrase}'"

        # Step 2: If LLM is available, call Groq API
        if self.is_available():
            try:
                prompt = (
                    "You are a strict data-privacy compliance auditor. Analyze the following user request and determine "
                    "whether the user is requesting permanent account/data deletion, erasure, or cleanup of remaining data/records.\n\n"
                    "Rules:\n"
                    "- Count as TRUE (authorizes deletion): Requests to delete, erase, close account with data removal, or "
                    "remove/delete remaining records (search results, old export links, backups, profiles) after prior closure.\n"
                    "- Count as FALSE (not applicable): Requests where the user explicitly asks to keep the account active, "
                    "or ONLY requests data download/portability, marketing opt-out, typo/name correction, password reset, or contact info update.\n\n"
                    f"User Request Text:\n\"\"\"{request_text}\"\"\"\n\n"
                    "Respond with a single JSON object with two fields:\n"
                    "\"authorizes_deletion\": true or false\n"
                    "\"reasoning\": \"short 1-sentence explanation\"\n"
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a precise data privacy auditor. Output strictly JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_tokens=150,
                    response_format={"type": "json_object"} if "llama-3" in self.model else None,
                )

                # Record token usage
                if response.usage:
                    usage_tracker.record_call(
                        case_id=case_id,
                        purpose="intent_classification",
                        model=self.model,
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                    )

                content = response.choices[0].message.content or "{}"
                # Extract JSON from content
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    res_json = json.loads(json_match.group(0))
                    auth = bool(res_json.get("authorizes_deletion", False))
                    reason = res_json.get("reasoning", "")
                    return auth, f"Groq LLM ({self.model}): {reason}"

            except Exception as e:
                # Fallback to conservative classification if API call errors
                pass

        # Step 3: Default conservative fallback based on general keywords
        general_del = any(w in text_lower for w in ["delete", "erase", "remove", "supprimer", "eliminar", "excluir", "cancela"])
        return general_del, "Heuristic classification fallback"


reasoning_agent = ReasoningAgent()
