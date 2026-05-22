import sqlite3
import json

DB_PATH = "equipment.db"

SCHEMA_INFO = """
테이블: equipment (설비)
컬럼:
  - id       : INTEGER  (설비 고유번호, PK)
  - name     : TEXT     (설비명, 예: EQ-001)
  - type     : TEXT     (설비 유형, 값: 'normal', 'special')
  - product  : TEXT     (생산 제품, 값: 'prod1', 'prod2', 'prod3')
  - status   : TEXT     (운영 상태, 값: 'active', 'inactive')
  - location : TEXT     (위치, 값: 'A동', 'B동', 'C동')
"""

SAMPLE_DATA = [
    ("EQ-001", "normal",  "prod1", "active",   "A동"),
    ("EQ-002", "normal",  "prod1", "active",   "A동"),
    ("EQ-003", "normal",  "prod2", "active",   "B동"),
    ("EQ-004", "special", "prod1", "active",   "A동"),
    ("EQ-005", "special", "prod2", "inactive", "B동"),
    ("EQ-006", "normal",  "prod3", "active",   "C동"),
    ("EQ-007", "normal",  "prod2", "active",   "B동"),
    ("EQ-008", "special", "prod3", "active",   "C동"),
    ("EQ-009", "normal",  "prod1", "inactive", "A동"),
    ("EQ-010", "normal",  "prod3", "active",   "C동"),
    ("EQ-011", "special", "prod2", "active",   "A동"),
    ("EQ-012", "normal",  "prod2", "inactive", "B동"),
]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            type     TEXT NOT NULL,
            product  TEXT,
            status   TEXT DEFAULT 'active',
            location TEXT
        )
    """)
    cur.execute("SELECT COUNT(*) FROM equipment")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO equipment (name, type, product, status, location) VALUES (?,?,?,?,?)",
            SAMPLE_DATA,
        )
        conn.commit()
    conn.close()


def execute_query(sql: str) -> dict:
    """SELECT 쿼리를 실행하고 결과를 반환합니다."""
    sql_stripped = sql.strip()
    if not sql_stripped.upper().startswith("SELECT"):
        return {"error": "SELECT 쿼리만 허용됩니다.", "columns": [], "rows": []}
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(sql_stripped)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
        return {"columns": columns, "rows": rows, "error": None}
    except Exception as e:
        return {"error": str(e), "columns": [], "rows": []}


def result_to_text(result: dict) -> str:
    """쿼리 결과를 사람이 읽기 쉬운 텍스트로 변환합니다."""
    if result.get("error"):
        return f"오류: {result['error']}"
    columns = result["columns"]
    rows = result["rows"]
    if not rows:
        return "조회 결과가 없습니다."
    lines = [" | ".join(columns)]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    return "\n".join(lines)
