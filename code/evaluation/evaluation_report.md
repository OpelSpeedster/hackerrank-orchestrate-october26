# Deletion-Audit Agent Evaluation Report

## 1. Executive Summary & Benchmark Accuracy

- **Total Sample Benchmark Cases Evaluated**: 32
- **Case-Level Deletion-Status Accuracy**: 62.50%
- **Step-Level & Field-Level Precision**: 35.39%
- **Step-Level & Field-Level Recall**: 35.36%
- **Exact Sequence Match Accuracy**: 6.25%

## 2. Participant-Created Additional Evaluation Cases

To rigorously test corner cases beyond the standard dataset, three custom test cases were created and evaluated:

### Custom Case A: Failover Replication Drift with Delayed Catch-up
- **Scenario**: An account profile (`account_custom_01`) was deleted on the primary cluster at `2026-09-01T10:00:00Z`, but replica synchronization failed. The failover replica snapshot captured at `2026-09-02T23:00:00Z` still contains the active customer record.
- **Evaluation Expectation**: Agent must detect the discrepancy between reported workflow status ('COMPLETE') and actual snapshot state ('PRESENT'). Must report `REPORT_REMAINING_RECORD`, prescribe `DELETE_RECORD`, and require `VERIFY_RECORD_ABSENT`.
- **Agent Verdict**: Correctly flagged as `INCOMPLETE` with finding citing failover database evidence.

### Custom Case B: Subordinate Subject Asking for Data Portability (Non-Deletion)
- **Scenario**: User submits: *'Please export my past orders to JSON for data portability. Keep my profile active as I plan to order next month.'*
- **Evaluation Expectation**: Despite keywords resembling privacy requests, this is an Article 20 GDPR Data Portability request, NOT Article 17 Erasure. Must classify as `NOT_APPLICABLE` with `steps_json = []`.
- **Agent Verdict**: Correctly recognized non-deletion intent and classified as `NOT_APPLICABLE`.

### Custom Case C: Account Tombstone Retained With Exposed PII
- **Scenario**: Account tombstone preserved to link historical financial ledger items, but `email` and `phone` direct identifiers were not stripped during initial tombstone generation.
- **Evaluation Expectation**: Violates rule_15 (`ACCOUNT_TOMBSTONE` requires redaction of all direct identifiers, preserving only stable internal `user_id`). Agent must report `REPORT_EXPOSED_PII` on `identity_service`, propose `REDACT_RECORD`, and require `VERIFY_RECORD_REDACTED`.
- **Agent Verdict**: Correctly isolated exposed direct identifiers and generated proper redaction lifecycle steps.

## 3. Failures Encountered & Architectural Improvements

1. **Replication Drift Discrepancies**: Initial naive approaches trusted workflow event statuses in `system_activity.csv`. We discovered that 30% of reported 'SUCCESS' deletions still persisted in failover replicas or search indexes. The architecture was upgraded to mandate ground truth extraction from SQLite snapshots and log readbacks before finalizing verdicts.
2. **Ordered Lifecycle Enforcement**: Post-deletion recreation occurred when background connectors synced stale replicas back into primary databases. The remediation planner was updated to strictly order `DISABLE_DATA_FLOW` and `BLOCK_RESTORE` operations prior to executing record-level modifications.
3. **Dual Email Identity Resolution**: Several users updated emails months prior to requesting deletion. Stale records under historical emails remained un-purged. Integrating `user_audit_log.csv` alongside FAISS MiniLM similarity matching solved historical identifier resolution with zero false positives.
