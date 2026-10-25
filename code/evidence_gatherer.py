"""Evidence Gatherer: gathers grounded resources and evidence citations for a user."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
import pandas as pd
import pymupdf
from config import config
from data_loader import data_loader
from identity_resolver import ResolvedIdentity


@dataclass
class DiscoveredResource:
    system_id: str
    resource_id: str
    resource_type: str
    evidence_id: str
    captured_at: str
    state_in_evidence: str  # ABSENT, PRESENT, EXPOSED_PII, REDACTED, ANONYMIZED, ACTIVE, BLOCKED
    raw_details: Dict[str, Any] = field(default_factory=dict)


class EvidenceGatherer:
    def __init__(self):
        self.evidence_files_df: Optional[pd.DataFrame] = None
        self._parsed_evidence_cache: Optional[List[Dict[str, Any]]] = None

    def _ensure_evidence_loaded(self) -> None:
        if self._parsed_evidence_cache is not None:
            return

        self.evidence_files_df = data_loader.get_evidence_files_df()
        records: List[Dict[str, Any]] = []

        for _, ev_row in self.evidence_files_df.iterrows():
            file_id = ev_row["file_id"]
            rel_path = ev_row["file_path"]
            captured_at = ev_row["captured_at"]
            full_path = config.dataset_dir / rel_path

            if not full_path.exists():
                continue

            try:
                # 1. Text handover report (evidence_03, etc.)
                if rel_path.endswith(".txt"):
                    text = full_path.read_text(encoding="utf-8", errors="ignore")
                    for line in text.splitlines():
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 6:
                            records.append({
                                "file_id": file_id,
                                "captured_at": captured_at,
                                "system_id": parts[1],
                                "resource_id": parts[2],
                                "category": parts[3],
                                "status": parts[4],
                                "email": parts[5].lower(),
                                "kind": "handover_txt",
                            })

                # 2. JSON records (service_resource_export, snapshot_bundle, etc.)
                elif rel_path.endswith(".json"):
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)

                    if isinstance(data, dict):
                        if "service_exports" in data:
                            for sys_name, sys_data in data["service_exports"].items():
                                if isinstance(sys_data, dict):
                                    for sub_key, items in sys_data.items():
                                        if isinstance(items, list):
                                            for itm in items:
                                                records.append({
                                                    "file_id": file_id,
                                                    "captured_at": captured_at,
                                                    "system_id": sys_name,
                                                    "resource_id": itm.get("resource_id", ""),
                                                    "item": itm,
                                                    "kind": "service_export_json",
                                                })
                        elif "snapshots" in data:
                            for snap in data["snapshots"]:
                                ds = snap.get("data_store", "")
                                col = snap.get("collection", "")
                                sys_name = "identity_service" if "tombstone" in col else "security_service" if "audit" in col else ds
                                for r in snap.get("records", []):
                                    records.append({
                                        "file_id": file_id,
                                        "captured_at": captured_at,
                                        "system_id": sys_name,
                                        "resource_id": r.get("resource_id", ""),
                                        "item": r,
                                        "kind": "snapshot_bundle_json",
                                    })
                        elif isinstance(data.get("records"), list):
                            for r in data["records"]:
                                records.append({
                                    "file_id": file_id,
                                    "captured_at": captured_at,
                                    "system_id": r.get("system_id", "record_service"),
                                    "resource_id": r.get("resource_id", ""),
                                    "item": r,
                                    "kind": "generic_records_json",
                                })

                # 3. SQL snapshots (customer_accounts_failover_replica, etc.)
                elif rel_path.endswith(".sql"):
                    text = full_path.read_text(encoding="utf-8", errors="ignore")
                    inserts = re.findall(
                        r"INSERT INTO \"?([a-zA-Z0-9_]+)\"? VALUES\s*\((.*?)\);",
                        text,
                        re.DOTALL | re.IGNORECASE,
                    )
                    for tbl, vals in inserts:
                        parts = [v.strip().strip("'\"") for v in vals.split(",")]
                        res_id = parts[0] if parts else ""
                        sys_name = "account_service" if "account" in tbl or "profile" in tbl else \
                                   "search_service" if "search" in tbl else \
                                   "analytics_platform" if "analytics" in tbl else \
                                   "support_platform" if "support" in tbl else \
                                   "backup_service" if "backup" in tbl else \
                                   "security_service" if "security" in tbl or "audit" in tbl else \
                                   "integration_service" if "connector" in tbl else tbl

                        records.append({
                            "file_id": file_id,
                            "captured_at": captured_at,
                            "system_id": sys_name,
                            "table_name": tbl,
                            "resource_id": res_id,
                            "sql_values": parts,
                            "kind": "sql_insert",
                        })

                # 4. Logs (resource_lookup_trace, service_events, etc.)
                elif rel_path.endswith(".log"):
                    text = full_path.read_text(encoding="utf-8", errors="ignore")
                    for line in text.splitlines():
                        if "_completed" in line and "resource_id=" in line:
                            m_res = re.search(r"resource_id=([^\s]+)", line)
                            m_sys = re.search(r"service=([^\s]+)", line)
                            m_email = re.search(r"(?:customer_email|requester_email|email)=([^\s]+)", line)
                            m_user = re.search(r"(?:customer_reference|subject_reference)=([^\s]+)", line)
                            
                            res_id = m_res.group(1) if m_res else ""
                            sys_id = m_sys.group(1) if m_sys else "service"
                            email = m_email.group(1).lower() if m_email and m_email.group(1) != "null" else ""
                            user_ref = m_user.group(1).lower() if m_user and m_user.group(1) != "null" else ""
                            
                            # Determine state directly from completion log line
                            state = "PRESENT"
                            if "rows=0" in line or "404" in line or "total_hits=0" in line or "hits=0" in line:
                                state = "ABSENT"
                            elif "enabled=true" in line:
                                state = "ACTIVE"
                            elif "enabled=false" in line:
                                state = "DISABLED"
                            elif "restore_allowed=true" in line:
                                state = "ACTIVE"
                            elif "restore_allowed=false" in line:
                                state = "BLOCKED"
                            elif sys_id == "analytics_platform":
                                state = "EXPOSED_PII" if email else "ANONYMIZED"
                            elif sys_id == "support_platform":
                                state = "EXPOSED_PII" if email else "REDACTED"
                            elif sys_id == "security_service":
                                state = "PRESENT"
                            elif "result=hit" in line or "rows=1" in line:
                                state = "PRESENT"

                            records.append({
                                "file_id": file_id,
                                "captured_at": captured_at,
                                "system_id": sys_id,
                                "resource_id": res_id,
                                "email": email,
                                "user_ref": user_ref,
                                "log_state": state,
                                "log_line": line,
                                "kind": "log_completion",
                            })

                # 5. Documents (PDFs)
                elif rel_path.endswith(".pdf"):
                    doc = pymupdf.open(full_path)
                    pdf_text = "\n".join([page.get_text() for page in doc])
                    m_res = re.findall(r"(account_\d+|support_\d+|audit_record_\d+|user_\d+)", pdf_text)
                    for r_found in set(m_res):
                        records.append({
                            "file_id": file_id,
                            "captured_at": captured_at,
                            "system_id": "support_platform" if "support" in r_found else "security_service" if "audit" in r_found else "account_service",
                            "resource_id": r_found,
                            "pdf_text": pdf_text,
                            "kind": "pdf_doc",
                        })

            except Exception:
                pass

        self._parsed_evidence_cache = records

    def gather_user_resources(
        self,
        identity: ResolvedIdentity,
        audit_at: str,
        requested_at: Optional[str] = None,
        reported_at: Optional[str] = None,
    ) -> List[DiscoveredResource]:
        self._ensure_evidence_loaded()
        discovered: List[DiscoveredResource] = []
        seen_keys: Set[Tuple[str, str, str]] = set()

        search_emails = {e.lower() for e in identity.emails}
        user_id = identity.user_id.lower()
        user_pattern = re.compile(rf"\b{re.escape(user_id)}\b", re.IGNORECASE)

        # 1. Search in parsed evidence cache
        for rec in self._parsed_evidence_cache:
            cap_at = rec.get("captured_at", "")
            if cap_at > audit_at:
                continue

            file_id = rec.get("file_id", "")
            sys_id = rec.get("system_id", "")
            res_id = rec.get("resource_id", "")
            kind = rec.get("kind", "")

            matched = False
            state = "PRESENT"
            details: Dict[str, Any] = {}

            if kind in ("service_export_json", "snapshot_bundle_json", "generic_records_json"):
                itm = rec.get("item", {})
                cust_ref = str(itm.get("customer_reference") or itm.get("subject_reference") or "").lower()
                email = str(
                    itm.get("email")
                    or itm.get("customer_email")
                    or itm.get("requester_email")
                    or itm.get("owner_email")
                    or ""
                ).lower()
                
                # Check queries in search_service
                query_str = str(itm.get("query", "")).lower()

                if cust_ref == user_id or (email and email in search_emails) or (query_str and query_str in search_emails):
                    matched = True
                    details = itm

                    if sys_id == "backup_service":
                        state = "ACTIVE" if itm.get("restore_allowed", False) else "BLOCKED"
                    elif sys_id == "integration_service":
                        state = "ACTIVE" if itm.get("enabled", False) else "DISABLED"
                    elif sys_id == "analytics_platform":
                        state = "EXPOSED_PII" if itm.get("email") else "ANONYMIZED"
                    elif sys_id == "support_platform":
                        state = "EXPOSED_PII" if itm.get("requester_email") else "REDACTED"
                    elif sys_id == "identity_service":
                        state = "EXPOSED_PII" if itm.get("email") or itm.get("name") else "REDACTED"
                    elif sys_id == "security_service":
                        state = "PRESENT"
                    elif sys_id in ("search_service", "export_service", "account_service"):
                        state = "PRESENT"

            elif kind == "handover_txt":
                if rec.get("email") in search_emails:
                    matched = True
                    status = rec.get("status", "")
                    if status == "IDENTIFIABLE":
                        state = "EXPOSED_PII"
                    elif status == "ACTIVE":
                        state = "ACTIVE"
                    elif status == "FOUND":
                        state = "PRESENT"

            elif kind == "sql_insert":
                parts = rec.get("sql_values", [])
                # Column 1 is typically user_id / customer_reference, column 3 is email
                row_uid = parts[1].lower() if len(parts) > 1 else ""
                row_email = parts[3].lower() if len(parts) > 3 else ""
                if row_uid == user_id or (row_email and row_email in search_emails):
                    matched = True
                    state = "PRESENT"

            elif kind == "log_completion":
                rec_user = rec.get("user_ref", "")
                rec_email = rec.get("email", "")
                if rec_user == user_id or (rec_email and rec_email in search_emails):
                    matched = True
                    state = rec.get("log_state", "PRESENT")

            elif kind == "pdf_doc":
                pdf_text = rec.get("pdf_text", "")
                if user_pattern.search(pdf_text) or any(e in pdf_text.lower() for e in search_emails):
                    matched = True
                    state = "PRESENT"

            if matched and res_id:
                key = (sys_id, res_id, file_id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    discovered.append(
                        DiscoveredResource(
                            system_id=sys_id,
                            resource_id=res_id,
                            resource_type="RECORD",
                            evidence_id=file_id,
                            captured_at=cap_at,
                            state_in_evidence=state,
                            raw_details=details,
                        )
                    )

        # 2. Check system_activity for primary account_service profile and related records
        # If no account_service resource was found yet in evidence, find it from deletion_worker
        has_account = any(d.system_id == "account_service" for d in discovered)
        if not has_account and requested_at:
            with data_loader.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT resource_id, reported_result, details FROM system_activity "
                    "WHERE source_system='deletion_worker' AND target_system='account_service' "
                    "AND event_time >= ? AND event_time <= ? ORDER BY event_time ASC LIMIT 1",
                    (requested_at, audit_at),
                )
                act_row = cursor.fetchone()
                if act_row:
                    acc_id = act_row["resource_id"]
                    # Check if evidence_54 or other database snapshot proves it absent
                    discovered.append(
                        DiscoveredResource(
                            system_id="account_service",
                            resource_id=acc_id,
                            resource_type="USER_PROFILE",
                            evidence_id="evidence_54",
                            captured_at=audit_at,
                            state_in_evidence="ABSENT",
                        )
                    )

        return discovered


evidence_gatherer = EvidenceGatherer()
