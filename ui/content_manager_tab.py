"""
Content Manager Tab - 컨텐츠 관리 탭
발행 이력 조회, 검색, 삭제, 통계
"""
import logging
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLineEdit, QDateEdit, QMessageBox,
    QFrame, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate

from core.post_history import (
    get_recent_posts, get_posts_by_date_range,
    get_stats, delete_post
)

logger = logging.getLogger(__name__)

# 모드 / 상태 표시 매핑
MODE_DISPLAY = {"info": "정보성", "delivery": "출고후기"}
STATUS_DISPLAY = {"published": "발행완료", "scheduled": "예약", "failed": "실패"}
STATUS_COLORS = {"published": "#48BB78", "scheduled": "#4299E1", "failed": "#E53E3E"}


class StatCard(QFrame):
    """통계 카드 위젯"""

    def __init__(self, title: str, value: str, bg: str, accent: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background-color: {bg}; border-left: 4px solid {accent}; "
            f"border-radius: 6px; padding: 12px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 11px; color: #5A5A6E; font-weight: bold; border: none;")
        layout.addWidget(lbl_title)

        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"font-size: 22px; color: {accent}; font-weight: bold; border: none;")
        layout.addWidget(self.lbl_value)

    def set_value(self, value: str):
        self.lbl_value.setText(value)


class ContentManagerTab(QWidget):
    """컨텐츠 관리 탭"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._posts = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- 통계 카드 ---
        stats_row = QHBoxLayout()
        self.card_total = StatCard("총 발행 수", "0", "#FFF0EC", "#FF6B6B")
        self.card_week = StatCard("이번 주", "0", "#F0F8FF", "#4299E1")
        self.card_month = StatCard("이번 달 (30일)", "0", "#F0FFF4", "#48BB78")
        self.card_top_cat = StatCard("카테고리 최다", "-", "#FFFFF0", "#F6AD55")
        for card in (self.card_total, self.card_week, self.card_month, self.card_top_cat):
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # --- 필터 ---
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("기간:"))

        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-30))
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        filter_row.addWidget(self.date_start)

        filter_row.addWidget(QLabel("~"))

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        filter_row.addWidget(self.date_end)

        btn_filter = QPushButton("조회")
        btn_filter.setObjectName("secondaryButton")
        btn_filter.clicked.connect(self.filter_by_date)
        filter_row.addWidget(btn_filter)

        filter_row.addSpacing(20)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("제목/주제 검색...")
        self.txt_search.returnPressed.connect(self._do_search)
        filter_row.addWidget(self.txt_search)

        btn_search = QPushButton("검색")
        btn_search.setObjectName("secondaryButton")
        btn_search.clicked.connect(self._do_search)
        filter_row.addWidget(btn_search)

        layout.addLayout(filter_row)

        # --- 테이블 ---
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["날짜", "제목", "주제", "카테고리", "모드", "태그", "상태"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 날짜
        header.setSectionResizeMode(1, QHeaderView.Stretch)           # 제목
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # 주제
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 카테고리
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 모드
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # 태그
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 상태

        layout.addWidget(self.table)

        # --- 하단 ---
        bottom_row = QHBoxLayout()
        self.lbl_count = QLabel("총 0건")
        self.lbl_count.setStyleSheet("font-weight: bold;")
        bottom_row.addWidget(self.lbl_count)
        bottom_row.addStretch()

        btn_delete = QPushButton("삭제")
        btn_delete.setObjectName("dangerButton")
        btn_delete.clicked.connect(self.delete_selected)
        bottom_row.addWidget(btn_delete)

        btn_refresh = QPushButton("새로고침")
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.clicked.connect(self.refresh_data)
        bottom_row.addWidget(btn_refresh)

        layout.addLayout(bottom_row)

    # --------------------------------------------------
    # Public methods
    # --------------------------------------------------

    def refresh_data(self):
        """DB에서 전체 데이터 다시 로드"""
        try:
            self._posts = get_recent_posts(limit=200)
            self._populate_table(self._posts)
            self._update_stats()
        except Exception as e:
            logger.error(f"Failed to refresh data: {e}")

    def filter_by_date(self):
        """날짜 범위로 필터"""
        start = self.date_start.date().toString("yyyy-MM-dd")
        end = self.date_end.date().toString("yyyy-MM-dd")
        try:
            self._posts = get_posts_by_date_range(start, end)
            self._populate_table(self._posts)
            self._update_stats()
        except Exception as e:
            logger.error(f"Failed to filter by date: {e}")

    def delete_selected(self):
        """선택된 행 삭제"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "알림", "삭제할 항목을 선택해주세요.")
            return

        post_id = self.table.item(row, 0).data(Qt.UserRole)
        title = self.table.item(row, 1).text()

        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{title}' 이력을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if delete_post(post_id):
                self.refresh_data()

    # --------------------------------------------------
    # Internal
    # --------------------------------------------------

    def _do_search(self):
        """검색어로 테이블 필터"""
        keyword = self.txt_search.text().strip().lower()
        if not keyword:
            self._populate_table(self._posts)
            return
        filtered = [
            p for p in self._posts
            if keyword in (p.get("title") or "").lower()
            or keyword in (p.get("topic") or "").lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, posts: list):
        """테이블에 데이터 채우기"""
        self.table.setRowCount(len(posts))
        for i, p in enumerate(posts):
            # 날짜
            raw_date = p.get("published_at", "")
            try:
                dt = datetime.fromisoformat(raw_date)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                date_str = raw_date[:16] if raw_date else ""
            item_date = QTableWidgetItem(date_str)
            item_date.setData(Qt.UserRole, p.get("id"))
            self.table.setItem(i, 0, item_date)

            # 제목, 주제, 카테고리
            self.table.setItem(i, 1, QTableWidgetItem(p.get("title", "")))
            self.table.setItem(i, 2, QTableWidgetItem(p.get("topic", "")))
            self.table.setItem(i, 3, QTableWidgetItem(p.get("category", "")))

            # 모드
            mode_raw = p.get("mode", "info")
            self.table.setItem(i, 4, QTableWidgetItem(MODE_DISPLAY.get(mode_raw, mode_raw)))

            # 태그
            self.table.setItem(i, 5, QTableWidgetItem(p.get("tags", "")))

            # 상태
            status_raw = p.get("status", "published")
            item_status = QTableWidgetItem(STATUS_DISPLAY.get(status_raw, status_raw))
            color = STATUS_COLORS.get(status_raw, "#2D2D3A")
            from PySide6.QtGui import QColor
            item_status.setForeground(QColor(color))
            self.table.setItem(i, 6, item_status)

        self.lbl_count.setText(f"총 {len(posts)}건")

    def _update_stats(self):
        """통계 카드 업데이트"""
        try:
            stats = get_stats(days=30)
            self.card_total.set_value(str(stats.get("total", 0)))
            self.card_week.set_value(str(stats.get("this_week", 0)))
            self.card_month.set_value(str(stats.get("this_month", 0)))

            by_cat = stats.get("by_category", {})
            if by_cat:
                top = max(by_cat, key=by_cat.get)
                self.card_top_cat.set_value(f"{top} ({by_cat[top]})")
            else:
                self.card_top_cat.set_value("-")
        except Exception as e:
            logger.error(f"Failed to update stats: {e}")

    def showEvent(self, event):
        """탭이 보여질 때 자동 새로고침"""
        super().showEvent(event)
        self.refresh_data()
