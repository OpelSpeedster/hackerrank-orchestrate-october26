"""Data loader: loads CSVs and evidence metadata into SQLite database."""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
from config import config


class DataLoader:
    def __init__(self, db_path: Optional[Path] = None, dataset_dir: Optional[Path] = None):
        self.db_path = db_path or config.db_path
        self.dataset_dir = dataset_dir or config.dataset_dir

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self, force_reload: bool = False) -> None:
        """Initialize the SQLite database and populate tables from CSVs."""
        if not force_reload and self.db_path.exists():
            # Check if tables exist
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='user_identities'"
                )
                if cursor.fetchone()[0] > 0:
                    return  # Already initialized

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            # 1. user_identities
            user_identities_df = pd.read_csv(
                self.dataset_dir / "user_identities.csv", encoding="utf-8"
            )
            user_identities_df.to_sql(
                "user_identities", conn, if_exists="replace", index=False
            )

            # 2. user_audit_log
            user_audit_df = pd.read_csv(
                self.dataset_dir / "user_audit_log.csv", encoding="utf-8"
            )
            user_audit_df.to_sql("user_audit_log", conn, if_exists="replace", index=False)

            # 3. system_activity
            system_activity_df = pd.read_csv(
                self.dataset_dir / "system_activity.csv", encoding="utf-8"
            )
            system_activity_df.to_sql(
                "system_activity", conn, if_exists="replace", index=False
            )

            # 4. deletion_rules
            deletion_rules_df = pd.read_csv(
                self.dataset_dir / "deletion_rules.csv", encoding="utf-8"
            )
            deletion_rules_df.to_sql(
                "deletion_rules", conn, if_exists="replace", index=False
            )

            # 5. evidence_files
            evidence_files_df = pd.read_csv(
                self.dataset_dir / "evidence_files.csv", encoding="utf-8"
            )
            evidence_files_df.to_sql(
                "evidence_files", conn, if_exists="replace", index=False
            )

            # 6. deletion_requests
            deletion_requests_df = pd.read_csv(
                self.dataset_dir / "deletion_requests.csv", encoding="utf-8"
            )
            deletion_requests_df.to_sql(
                "deletion_requests", conn, if_exists="replace", index=False
            )

            # 7. sample_deletion_requests
            sample_requests_df = pd.read_csv(
                self.dataset_dir / "sample_deletion_requests.csv", encoding="utf-8"
            )
            sample_requests_df.to_sql(
                "sample_deletion_requests", conn, if_exists="replace", index=False
            )

            # 8. sample_output
            sample_output_df = pd.read_csv(
                self.dataset_dir / "sample_output.csv", encoding="utf-8"
            )
            sample_output_df.to_sql(
                "sample_output", conn, if_exists="replace", index=False
            )

            # Create performance indexes
            cursor = conn.cursor()
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON user_identities(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON user_identities(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_phone ON user_identities(phone);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON user_audit_log(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_val ON user_audit_log(old_value);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_resource ON system_activity(resource_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_time ON system_activity(event_time);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_fid ON evidence_files(file_id);")
            conn.commit()

    def get_user_identities_df(self) -> pd.DataFrame:
        return pd.read_csv(self.dataset_dir / "user_identities.csv", encoding="utf-8")

    def get_deletion_requests_df(self, sample_only: bool = False) -> pd.DataFrame:
        filename = "sample_deletion_requests.csv" if sample_only else "deletion_requests.csv"
        return pd.read_csv(self.dataset_dir / filename, encoding="utf-8")

    def get_deletion_rules_df(self) -> pd.DataFrame:
        return pd.read_csv(self.dataset_dir / "deletion_rules.csv", encoding="utf-8")

    def get_evidence_files_df(self) -> pd.DataFrame:
        return pd.read_csv(self.dataset_dir / "evidence_files.csv", encoding="utf-8")


data_loader = DataLoader()
