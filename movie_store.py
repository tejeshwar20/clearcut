"""Persistent storage for spoiler-safe movie reports, never source review text."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from pipeline import add_reader_review, enforce_reader_output, format_reception_review, opinion_verdict


MAX_SAVED_MOVIES = 100


class MovieReportStore:
    def __init__(self, database_path):
        self.database_path = Path(database_path)

    @contextmanager
    def _connection(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.database_path), timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS movie_reports (
                        page_id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        report_json TEXT NOT NULL,
                        saved_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    )
                    """
                )
                yield connection
        finally:
            connection.close()

    def get_report(self, page_id):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT report_json FROM movie_reports WHERE page_id = ?",
                (page_id,),
            ).fetchone()
        if row is None:
            return None
        report = json.loads(row["report_json"])
        if isinstance(report.get("movie"), dict):
            report["movie"].setdefault("id", page_id)
        if "overall" in report and "aspects" in report and ("review_sections" not in report or report.get("review_format_version", 0) < 4):
            for aspect in report["aspects"]:
                if aspect["safe_mentions"] and aspect.get("weighted_distribution"):
                    aspect["verdict"] = opinion_verdict(aspect["weighted_distribution"])
            format_reception_review(report)
        contract = report.get("reader_output", {})
        if contract.get("version") != 1 or contract.get("checked") is not True:
            if "aspects" in report:
                add_reader_review(report)
            else:
                report["reader_review"] = ""
            report["review"] = report["reader_review"]
            report["review_sections"] = []
        elif "aspects" in report and "reader_review" not in report:
            add_reader_review(report)
        return enforce_reader_output(report)

    def list_reports(self):
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT page_id, title, saved_at
                FROM movie_reports
                ORDER BY saved_at DESC, page_id DESC
                """
            ).fetchall()
        return [
            {"id": row["page_id"], "title": row["title"], "saved_at": row["saved_at"]}
            for row in rows
        ]

    def save_report(self, page_id, title, report):
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO movie_reports (page_id, title, report_json)
                VALUES (?, ?, ?)
                ON CONFLICT(page_id) DO UPDATE SET
                    title = excluded.title,
                    report_json = excluded.report_json,
                    saved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (page_id, title, json.dumps(report, ensure_ascii=False)),
            )
            connection.execute(
                """
                DELETE FROM movie_reports
                WHERE page_id NOT IN (
                    SELECT page_id
                    FROM movie_reports
                    ORDER BY saved_at DESC, page_id DESC
                    LIMIT ?
                )
                """,
                (MAX_SAVED_MOVIES,),
            )
