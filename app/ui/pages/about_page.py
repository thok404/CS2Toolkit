import html
import os
import re
import sys
import threading

import requests

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from qfluentwidgets import TitleLabel, BodyLabel, PushButton, MessageBoxBase, SubtitleLabel
from app.release_endpoints import DONATION_MARKDOWN_URL, FORK_NOTICE, FORK_REPO_URL, UPSTREAM_REPO_URL


class SponsorshipDialog(MessageBoxBase):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)

        self.titleLabel = SubtitleLabel("赞赏支持", self)
        self.viewLayout.addWidget(self.titleLabel)

        self.textLabel = BodyLabel(
            "如果这个项目对你有帮助，欢迎自愿赞赏支持后续维护。\n"
            "赞赏仅代表对作者的支持，不对应任何功能、授权、更新承诺或专属服务。",
            self
        )
        self.textLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.textLabel)

        self.imageLabel = QLabel(self)
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.viewLayout.addWidget(self.imageLabel)

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.imageLabel.setText("未能加载赞赏码图片，请检查 sponsorship.jpg 是否存在。")
        else:
            self.imageLabel.setPixmap(
                pixmap.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        self.widget.setMinimumWidth(380)
        self.yesButton.setText("关闭")
        self.cancelButton.hide()


class AboutPage(QWidget):
    donation_content_fetched = Signal(str, bool)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.donation_content_fetched.connect(self._update_donation_content)
        self._setup_ui()
        self._fetch_donation_content()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 30)
        layout.setSpacing(10)

        layout.addWidget(TitleLabel("关于 CS2 工具箱"), 0, Qt.AlignTop)

        about_text = BodyLabel()
        about_text.setWordWrap(True)
        about_text.setText("""
这是一个为CS2设计的多功能软件，可自定义开屏动画、音效、游戏字体与实时播放音效，其他功能还在积极开发中，敬请期待！(｡･ω･｡)<br><br>
<b>版本: {version}</b><br>
fork 维护者: thok404<br>
fork 仓库与更新: <a href="{repo_url}">{repo_url}</a><br>
原作者: Moon4Quartz<br>
原项目: <a href="{upstream_url}">{upstream_url}</a><br>
许可证: GPLv3<br>
免责: 本项目按现状提供，不附带任何担保<br>
声明: 本项目与 Valve 无关联，相关商标归其各自权利人所有<br>
""".format(version=self.parent.version, repo_url=self.parent.repo_url, upstream_url=UPSTREAM_REPO_URL))
        about_text.setOpenExternalLinks(True)
        layout.addWidget(about_text, 0, Qt.AlignTop)

        self.fork_notice = BodyLabel(self)
        self.fork_notice.setWordWrap(True)
        self.fork_notice.setTextFormat(Qt.RichText)
        self.fork_notice.setText(f'<b>{FORK_NOTICE}</b><br><a href="{FORK_REPO_URL}">打开 fork 仓库</a>')
        self.fork_notice.setOpenExternalLinks(True)
        layout.addWidget(self.fork_notice, 0, Qt.AlignTop)

        self.check_update_btn = PushButton("检查更新")
        layout.addWidget(self.check_update_btn, 0, Qt.AlignTop)

        self.sponsorship_btn = None
        if os.path.isfile(self._get_sponsorship_image_path()):
            self.sponsorship_btn = PushButton("赞赏支持")
            layout.addWidget(self.sponsorship_btn, 0, Qt.AlignTop)

        self.donation_title = SubtitleLabel("原项目捐赠列表", self)
        self.donation_content = BodyLabel("正在从外部 Markdown 获取捐赠名单...", self)
        self.donation_content.setWordWrap(True)
        self.donation_content.setTextFormat(Qt.RichText)
        self.donation_content.setOpenExternalLinks(True)

        layout.addWidget(self.donation_title, 0, Qt.AlignTop)
        layout.addWidget(self.donation_content, 0, Qt.AlignTop)
        layout.addStretch()
        self._connect_signals()

    def _get_sponsorship_image_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "sponsorship.jpg")

    def _show_sponsorship_dialog(self):
        dialog = SponsorshipDialog(self._get_sponsorship_image_path(), self)
        dialog.exec()

    def _fetch_donation_content(self):
        self.donation_content.setText("正在从外部 Markdown 获取捐赠名单...")

        def fetch_task():
            try:
                proxies = {"http": None, "https": None}
                response = requests.get(DONATION_MARKDOWN_URL, timeout=5, proxies=proxies)
                if response.status_code == 200 and response.text.strip():
                    html_content = self._markdown_to_html(response.text)
                    self.donation_content_fetched.emit(html_content, False)
                else:
                    self.donation_content_fetched.emit("暂未获取到捐赠名单。", True)
            except Exception:
                self.donation_content_fetched.emit("捐赠名单获取失败，请稍后重试。", True)

        threading.Thread(target=fetch_task, daemon=True).start()

    def _update_donation_content(self, content, is_error):
        if is_error:
            self.donation_content.setText(content)
        else:
            self.donation_content.setText(content)

    def _format_inline_markdown(self, text):
        placeholders = {}

        def replace_link(match):
            key = f"__LINK_{len(placeholders)}__"
            placeholders[key] = (
                f'<a href="{html.escape(match.group(2), quote=True)}">'
                f'{html.escape(match.group(1))}</a>'
            )
            return key

        text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', replace_link, text)
        escaped = html.escape(text)
        escaped = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped)
        escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)

        for key, value in placeholders.items():
            escaped = escaped.replace(key, value)

        return escaped

    def _markdown_to_html(self, markdown_text):
        lines = markdown_text.splitlines()
        html_lines = []
        in_list = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                continue

            if line.startswith("# "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h3>{self._format_inline_markdown(line[2:])}</h3>")
                continue

            if line.startswith("## "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h4>{self._format_inline_markdown(line[3:])}</h4>")
                continue

            if line.startswith(("- ", "* ")):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{self._format_inline_markdown(line[2:])}</li>")
                continue

            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{self._format_inline_markdown(line)}</p>")

        if in_list:
            html_lines.append("</ul>")

        if not html_lines:
            return "暂未获取到捐赠名单。"
        return "".join(html_lines)

    def _connect_signals(self):
        self.check_update_btn.clicked.connect(self.parent.check_for_updates)
        if self.sponsorship_btn is not None:
            self.sponsorship_btn.clicked.connect(self._show_sponsorship_dialog)
