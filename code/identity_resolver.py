"""Identity Resolver: reconciles current and historical identifiers for users."""

from dataclasses import dataclass, field
from typing import Set, List, Optional, Dict, Any
from data_loader import data_loader
from identity_index import identity_index


@dataclass
class ResolvedIdentity:
    user_id: str
    name: str
    current_email: str
    emails: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    email_hash: str = ""
    names: Set[str] = field(default_factory=set)

    def get_search_terms(self) -> Set[str]:
        """All unique terms identifying this user across systems and logs."""
        terms = {self.user_id, self.current_email}
        if self.name:
            terms.add(self.name)
        if self.email_hash:
            terms.add(self.email_hash)
        terms.update(self.emails)
        terms.update(self.phones)
        terms.update(self.names)
        return {t.strip().lower() for t in terms if t and t.strip()}


class IdentityResolver:
    def __init__(self):
        self._user_cache: Dict[str, ResolvedIdentity] = {}
        self._email_to_uid: Dict[str, str] = {}
        self._phone_to_uid: Dict[str, str] = {}
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        data_loader.init_database()
        with data_loader.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Load all current identities
            cursor.execute(
                "SELECT user_id, name, email, phone, email_hash FROM user_identities"
            )
            for row in cursor.fetchall():
                uid = row["user_id"]
                name = row["name"] or ""
                email = (row["email"] or "").strip().lower()
                phone = (row["phone"] or "").strip()
                email_hash = row["email_hash"] or ""

                res = ResolvedIdentity(
                    user_id=uid,
                    name=name,
                    current_email=email,
                    emails={email} if email else set(),
                    phones={phone} if phone else set(),
                    email_hash=email_hash,
                    names={name} if name else set(),
                )
                self._user_cache[uid] = res
                if email:
                    self._email_to_uid[email] = uid
                if phone:
                    self._phone_to_uid[phone] = uid

            # 2. Augment with historical values from user_audit_log
            cursor.execute(
                "SELECT user_id, field_name, old_value, new_value FROM user_audit_log"
            )
            for row in cursor.fetchall():
                uid = row["user_id"]
                if uid not in self._user_cache:
                    continue
                res = self._user_cache[uid]
                field_name = row["field_name"]
                old_val = (row["old_value"] or "").strip()
                new_val = (row["new_value"] or "").strip()

                if field_name == "email":
                    if old_val:
                        res.emails.add(old_val.lower())
                        self._email_to_uid[old_val.lower()] = uid
                    if new_val:
                        res.emails.add(new_val.lower())
                        self._email_to_uid[new_val.lower()] = uid
                elif field_name == "phone":
                    if old_val:
                        res.phones.add(old_val)
                        self._phone_to_uid[old_val] = uid
                    if new_val:
                        res.phones.add(new_val)
                        self._phone_to_uid[new_val] = uid
                elif field_name == "name":
                    if old_val:
                        res.names.add(old_val)
                    if new_val:
                        res.names.add(new_val)

        self._initialized = True

    def resolve(self, email: str, fallback_query: Optional[str] = None) -> Optional[ResolvedIdentity]:
        """Resolve a user identity by email, with FAISS fallback."""
        self._ensure_initialized()
        clean_email = (email or "").strip().lower()

        # 1. Exact match in email map (covers current and historical)
        if clean_email in self._email_to_uid:
            return self._user_cache[self._email_to_uid[clean_email]]

        # 2. FAISS similarity match fallback
        search_str = f"Email: {clean_email}"
        if fallback_query:
            search_str += f" | {fallback_query}"

        try:
            matches = identity_index.search(search_str, top_k=1)
            if matches:
                top_match, score = matches[0]
                uid = top_match["user_id"]
                if uid in self._user_cache:
                    return self._user_cache[uid]
        except Exception:
            pass

        return None

    def get_by_user_id(self, user_id: str) -> Optional[ResolvedIdentity]:
        self._ensure_initialized()
        return self._user_cache.get(user_id)


identity_resolver = IdentityResolver()
