import csv
import io
from datetime import datetime, timezone

from dal.base import BaseFileDAL, BaseTimeSeriesDAL
from models.file import FileMeta


class FileService:
    def __init__(self, file_dal: BaseFileDAL, ts_dal: BaseTimeSeriesDAL):
        self._file_dal = file_dal
        self._ts_dal = ts_dal

    async def list_files(self) -> list[FileMeta]:
        return await self._file_dal.list()

    async def ingest_csv(
        self, *, filename: str, raw_bytes: bytes, session_id: str | None = None
    ) -> tuple[FileMeta, int]:
        text = raw_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))

        rows = list(reader)
        if not rows:
            raise ValueError("CSV为空")

        header = [h.strip() for h in rows[0]]
        data_rows = rows[1:]

        time_col_idx = self._detect_time_col(header)
        column_names = header
        row_count = len(data_rows)

        file_meta = await self._file_dal.create(
            filename=filename,
            size=len(raw_bytes),
            row_count=row_count,
            column_names=column_names,
            session_id=session_id,
        )

        ts_docs = []
        for row in data_rows:
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))

            ts = self._parse_datetime(row[time_col_idx])
            if ts is None:
                continue

            metadata: dict[str, str] = {}
            metrics: dict[str, float] = {}

            for idx, col_name in enumerate(header):
                if idx == time_col_idx:
                    continue
                val = (row[idx] or "").strip()
                if val == "":
                    continue
                num = self._to_float(val)
                if num is None:
                    metadata[col_name] = val
                else:
                    metrics[col_name] = num

            ts_docs.append(
                {
                    "timestamp": ts,
                    "metadata": metadata,
                    **metrics,
                }
            )

        inserted = await self._ts_dal.insert_rows(file_id=file_meta.id, rows=ts_docs)
        return file_meta, inserted

    def _detect_time_col(self, header: list[str]) -> int:
        for idx, name in enumerate(header):
            lower = name.lower()
            if "timestamp" in lower or "datetime" in lower:
                return idx
            if lower in {"time", "date"}:
                return idx
            if "time" in lower or "date" in lower:
                return idx
        return 0

    def _parse_datetime(self, value: str) -> datetime | None:
        s = (value or "").strip()
        if not s:
            return None
        s = s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        return None

    def _to_float(self, value: str) -> float | None:
        try:
            return float(value)
        except ValueError:
            return None
