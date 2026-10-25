"""Policy Engine: evaluates compliance against deletion_rules.csv and builds ordered steps."""

import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from evidence_gatherer import DiscoveredResource
from identity_resolver import ResolvedIdentity


OPERATION_FINDING_ORDER = [
    "REPORT_ACTIVE_DATA_FLOW",
    "REPORT_RESTORE_RISK",
    "REPORT_REMAINING_RECORD",
    "REPORT_EXPOSED_PII",
]

OPERATION_REMEDIATION_ORDER = [
    "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE",
    "DELETE_RECORD",
    "REDACT_RECORD",
    "ANONYMIZE_RECORD",
]

OPERATION_VERIFICATION_ORDER = [
    "VERIFY_RECORD_ABSENT",
    "VERIFY_RECORD_PRESENT",
    "VERIFY_RECORD_REDACTED",
    "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED",
    "VERIFY_RESTORE_BLOCKED",
]


class PolicyEngine:
    def __init__(self):
        pass

    def evaluate_case(
        self,
        case_id: str,
        identity: Optional[ResolvedIdentity],
        resources: List[DiscoveredResource],
        is_deletion_authorized: bool,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Evaluates a case and returns (deletion_status, steps_list).
        deletion_status: COMPLETE, INCOMPLETE, or NOT_APPLICABLE
        """
        if not is_deletion_authorized:
            return "NOT_APPLICABLE", []

        if not identity:
            # Fallback if identity could not be resolved
            return "COMPLETE", []

        findings: List[Dict[str, Any]] = []
        remediations: List[Dict[str, Any]] = []
        verifications: List[Dict[str, Any]] = []

        # Deduplicate resources by (system_id, resource_id) keeping latest evidence
        res_map: Dict[Tuple[str, str], DiscoveredResource] = {}
        for r in sorted(resources, key=lambda x: x.captured_at):
            res_map[(r.system_id, r.resource_id)] = r

        for (sys_id, res_id), r in res_map.items():
            state = r.state_in_evidence
            ev_id = r.evidence_id

            if sys_id == "integration_service":
                if state == "ACTIVE":
                    findings.append({
                        "phase": "FINDING",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REPORT_ACTIVE_DATA_FLOW",
                        "state": "ACTIVE",
                        "evidence_id": ev_id,
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "DISABLE_DATA_FLOW",
                        "state": "DISABLED",
                        "evidence_id": "",
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_DATA_FLOW_DISABLED",
                        "state": "DISABLED",
                        "evidence_id": "",
                    })
                elif state == "DISABLED":
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_DATA_FLOW_DISABLED",
                        "state": "DISABLED",
                        "evidence_id": ev_id,
                    })

            elif sys_id == "backup_service":
                if state == "ACTIVE":
                    findings.append({
                        "phase": "FINDING",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REPORT_RESTORE_RISK",
                        "state": "ACTIVE",
                        "evidence_id": ev_id,
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "BLOCK_RESTORE",
                        "state": "BLOCKED",
                        "evidence_id": "",
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RESTORE_BLOCKED",
                        "state": "BLOCKED",
                        "evidence_id": "",
                    })
                elif state == "BLOCKED":
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RESTORE_BLOCKED",
                        "state": "BLOCKED",
                        "evidence_id": ev_id,
                    })

            elif sys_id in ("account_service", "search_service", "export_service"):
                if state == "PRESENT":
                    findings.append({
                        "phase": "FINDING",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": ev_id,
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })
                elif state == "ABSENT":
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": ev_id,
                    })

            elif sys_id == "analytics_platform":
                if state == "EXPOSED_PII":
                    findings.append({
                        "phase": "FINDING",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REPORT_EXPOSED_PII",
                        "state": "PRESENT",
                        "evidence_id": ev_id,
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "ANONYMIZE_RECORD",
                        "state": "ANONYMIZED",
                        "evidence_id": "",
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ANONYMIZED",
                        "state": "ANONYMIZED",
                        "evidence_id": "",
                    })
                elif state == "PRESENT":
                    findings.append({
                        "phase": "FINDING",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REPORT_REMAINING_RECORD",
                        "state": "PRESENT",
                        "evidence_id": ev_id,
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "DELETE_RECORD",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ABSENT",
                        "state": "ABSENT",
                        "evidence_id": "",
                    })
                elif state == "ANONYMIZED":
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_ANONYMIZED",
                        "state": "ANONYMIZED",
                        "evidence_id": ev_id,
                    })

            elif sys_id == "support_platform":
                if "attachment" in res_id or "delivery" in str(r.raw_details):
                    if state == "PRESENT":
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_REMAINING_RECORD",
                            "state": "PRESENT",
                            "evidence_id": ev_id,
                        })
                        remediations.append({
                            "phase": "REMEDIATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "DELETE_RECORD",
                            "state": "ABSENT",
                            "evidence_id": "",
                        })
                        verifications.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_ABSENT",
                            "state": "ABSENT",
                            "evidence_id": "",
                        })
                else:
                    if state == "EXPOSED_PII" or state == "PRESENT":
                        findings.append({
                            "phase": "FINDING",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REPORT_EXPOSED_PII",
                            "state": "PRESENT",
                            "evidence_id": ev_id,
                        })
                        remediations.append({
                            "phase": "REMEDIATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "REDACT_RECORD",
                            "state": "REDACTED",
                            "evidence_id": "",
                        })
                        verifications.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_REDACTED",
                            "state": "REDACTED",
                            "evidence_id": "",
                        })
                    elif state == "REDACTED":
                        verifications.append({
                            "phase": "VERIFICATION",
                            "system_id": sys_id,
                            "resource_id": res_id,
                            "operation": "VERIFY_RECORD_REDACTED",
                            "state": "REDACTED",
                            "evidence_id": ev_id,
                        })

            elif sys_id == "identity_service":
                if state == "EXPOSED_PII":
                    findings.append({
                        "phase": "FINDING",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REPORT_EXPOSED_PII",
                        "state": "PRESENT",
                        "evidence_id": ev_id,
                    })
                    remediations.append({
                        "phase": "REMEDIATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "REDACT_RECORD",
                        "state": "REDACTED",
                        "evidence_id": "",
                    })
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_REDACTED",
                        "state": "REDACTED",
                        "evidence_id": "",
                    })
                elif state == "REDACTED":
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": sys_id,
                        "resource_id": res_id,
                        "operation": "VERIFY_RECORD_REDACTED",
                        "state": "REDACTED",
                        "evidence_id": ev_id,
                    })

            elif sys_id == "security_service":
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_PRESENT",
                    "state": "PRESENT",
                    "evidence_id": ev_id,
                })

        # Determine overall case status
        if findings:
            status = "INCOMPLETE"
            # Sort findings
            findings.sort(
                key=lambda x: (
                    OPERATION_FINDING_ORDER.index(x["operation"])
                    if x["operation"] in OPERATION_FINDING_ORDER else 99,
                    x["system_id"],
                    x["resource_id"],
                )
            )

            # Sort remediations: flow/restore first, then records
            remediations.sort(
                key=lambda x: (
                    OPERATION_REMEDIATION_ORDER.index(x["operation"])
                    if x["operation"] in OPERATION_REMEDIATION_ORDER else 99,
                    x["system_id"],
                    x["resource_id"],
                )
            )

            # In incomplete cases, verification steps have evidence_id = ""
            for v in verifications:
                v["evidence_id"] = ""

            # Deduplicate verifications
            seen_v: Set[Tuple[str, str, str]] = set()
            dedup_v = []
            for v in verifications:
                k = (v["system_id"], v["resource_id"], v["operation"])
                if k not in seen_v:
                    seen_v.add(k)
                    dedup_v.append(v)

            dedup_v.sort(
                key=lambda x: (
                    OPERATION_VERIFICATION_ORDER.index(x["operation"])
                    if x["operation"] in OPERATION_VERIFICATION_ORDER else 99,
                    x["system_id"],
                    x["resource_id"],
                )
            )

            all_steps = findings + remediations + dedup_v

        else:
            status = "COMPLETE"
            # Deduplicate verifications
            seen_v: Set[Tuple[str, str, str]] = set()
            dedup_v = []
            for v in verifications:
                k = (v["system_id"], v["resource_id"], v["operation"])
                if k not in seen_v:
                    seen_v.add(k)
                    dedup_v.append(v)

            dedup_v.sort(
                key=lambda x: (
                    OPERATION_VERIFICATION_ORDER.index(x["operation"])
                    if x["operation"] in OPERATION_VERIFICATION_ORDER else 99,
                    x["system_id"],
                    x["resource_id"],
                )
            )
            all_steps = dedup_v

        # Assign 1-indexed consecutive step numbers
        for idx, step in enumerate(all_steps, 1):
            step["step_no"] = idx

        return status, all_steps


policy_engine = PolicyEngine()
