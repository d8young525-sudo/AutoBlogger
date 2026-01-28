"""
Post History Manager
발행 이력 관리 - SQLite DB 저장, 중복 주제 방지, 통계
"""
import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "post_history.db"


def _get_conn() -> sqlite3.Connection:
    """Get database connection, create table if not exists."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS post_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            topic TEXT,
            category TEXT,
            mode TEXT DEFAULT 'info',
            content_preview TEXT,
            published_at TEXT NOT NULL,
            status TEXT DEFAULT 'published',
            tags TEXT
        )
    """)
    conn.commit()
    return conn


def add_post(
    title: str,
    topic: str = "",
    category: str = "",
    mode: str = "info",
    content_preview: str = "",
    tags: str = "",
    status: str = "published"
) -> int:
    """
    발행 기록 추가.
    
    Args:
        title: 글 제목
        topic: 원본 주제
        category: 발행 카테고리
        mode: 'info' or 'delivery'
        content_preview: 본문 앞부분 (200자)
        tags: 해시태그 (쉼표 구분)
        status: 'published', 'scheduled', 'failed'
        
    Returns:
        Inserted row ID
    """
    conn = _get_conn()
    try:
        preview = content_preview[:200] if content_preview else ""
        cur = conn.execute(
            """INSERT INTO post_history 
               (title, topic, category, mode, content_preview, published_at, status, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, topic, category, mode, preview,
             datetime.now().isoformat(), status, tags)
        )
        conn.commit()
        row_id = cur.lastrowid
        logger.info(f"Post history added: id={row_id}, title={title[:30]}")
        return row_id
    finally:
        conn.close()


def get_recent_posts(limit: int = 50) -> List[Dict[str, Any]]:
    """최근 발행 이력 조회."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM post_history ORDER BY published_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_posts_by_date_range(
    start_date: str, 
    end_date: str
) -> List[Dict[str, Any]]:
    """날짜 범위로 이력 조회 (ISO format: YYYY-MM-DD)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM post_history 
               WHERE published_at >= ? AND published_at < ?
               ORDER BY published_at DESC""",
            (start_date, end_date + "T23:59:59")
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def is_duplicate_topic(topic: str, days: int = 30) -> bool:
    """
    최근 N일 내 동일/유사 주제 발행 여부 확인.
    
    Args:
        topic: 확인할 주제
        days: 검색 기간 (일)
        
    Returns:
        True if duplicate found
    """
    if not topic:
        return False
    
    conn = _get_conn()
    try:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT topic, title FROM post_history 
               WHERE published_at >= ? AND status = 'published'""",
            (since,)
        ).fetchall()
        
        topic_lower = topic.strip().lower()
        for row in rows:
            existing = (row["topic"] or "").strip().lower()
            existing_title = (row["title"] or "").strip().lower()
            # Exact match or high similarity
            if topic_lower == existing or topic_lower == existing_title:
                return True
            # Substring containment (at least 10 chars)
            if len(topic_lower) >= 10:
                if topic_lower in existing or existing in topic_lower:
                    return True
        
        return False
    finally:
        conn.close()


def get_stats(days: int = 30) -> Dict[str, Any]:
    """
    발행 통계 반환.
    
    Returns:
        {
            "total": int,
            "this_week": int,
            "this_month": int,
            "by_category": {"cat": count, ...},
            "by_mode": {"info": count, "delivery": count}
        }
    """
    conn = _get_conn()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM post_history WHERE status='published'"
        ).fetchone()[0]
        
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        this_week = conn.execute(
            "SELECT COUNT(*) FROM post_history WHERE published_at >= ? AND status='published'",
            (week_ago,)
        ).fetchone()[0]
        
        month_ago = (datetime.now() - timedelta(days=days)).isoformat()
        this_month = conn.execute(
            "SELECT COUNT(*) FROM post_history WHERE published_at >= ? AND status='published'",
            (month_ago,)
        ).fetchone()[0]
        
        # By category
        cat_rows = conn.execute(
            """SELECT category, COUNT(*) as cnt FROM post_history 
               WHERE status='published' GROUP BY category ORDER BY cnt DESC"""
        ).fetchall()
        by_category = {r["category"] or "(미지정)": r["cnt"] for r in cat_rows}
        
        # By mode
        mode_rows = conn.execute(
            """SELECT mode, COUNT(*) as cnt FROM post_history 
               WHERE status='published' GROUP BY mode"""
        ).fetchall()
        by_mode = {r["mode"]: r["cnt"] for r in mode_rows}
        
        return {
            "total": total,
            "this_week": this_week,
            "this_month": this_month,
            "by_category": by_category,
            "by_mode": by_mode
        }
    finally:
        conn.close()


def delete_post(post_id: int) -> bool:
    """이력 삭제."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM post_history WHERE id = ?", (post_id,))
        conn.commit()
        return True
    finally:
        conn.close()
