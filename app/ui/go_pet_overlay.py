from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QPoint, Signal, QObject, QUrl
from PySide6.QtGui import QPixmap, QMovie
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from qfluentwidgets import BodyLabel
import ctypes
import os
import random
from ..logic.image_loader import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, load_pixmap, create_image_movie, dispose_image_movie

class GoPetSignals(QObject):
    update_pet = Signal(str) # image path
    hide_pet = Signal()

class _BasePetWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.pet_label = QLabel(self)
        self.pet_label.setScaledContents(True)
        self.pet_movie = None
        self.pet_video_widget = QVideoWidget(self)
        self.pet_video_widget.hide()
        self.pet_media_player = QMediaPlayer(self)
        self.pet_audio_output = QAudioOutput(self)
        self.pet_audio_output.setVolume(0)
        self.pet_media_player.setAudioOutput(self.pet_audio_output)
        self.pet_media_player.setVideoOutput(self.pet_video_widget)

        self._current_image_path = ""
        self.pet_size = 200
        self._video_exts = VIDEO_EXTENSIONS
        self._image_exts = IMAGE_EXTENSIONS

    def _resolve_media_path(self, image_path):
        if not image_path:
            return ""
        if os.path.isdir(image_path):
            valid_exts = self._image_exts | self._video_exts
            files = [
                os.path.join(image_path, f)
                for f in os.listdir(image_path)
                if os.path.isfile(os.path.join(image_path, f)) and os.path.splitext(f)[1].lower() in valid_exts
            ]
            if not files:
                return ""
            return random.choice(files)
        return image_path if os.path.exists(image_path) else ""

    def _clear_media(self):
        self.pet_media_player.stop()
        self.pet_media_player.setSource(QUrl())
        self.pet_video_widget.hide()
        if self.pet_movie:
            dispose_image_movie(self.pet_movie)
            self.pet_movie = None
            self.pet_label.setMovie(None)
        self.pet_label.setPixmap(QPixmap())

    def update_pet(self, image_path):
        resolved_path = self._resolve_media_path(image_path)
        if not resolved_path:
            self.hide_pet()
            return

        self._current_image_path = resolved_path
        suffix = os.path.splitext(resolved_path)[1].lower()
        is_video = suffix in self._video_exts
        movie = None if is_video else create_image_movie(resolved_path, self)

        if is_video:
            if self.pet_movie:
                dispose_image_movie(self.pet_movie)
                self.pet_movie = None
                self.pet_label.setMovie(None)
            self.pet_label.hide()
            self.pet_label.setPixmap(QPixmap())
            self.pet_video_widget.show()
            self.pet_media_player.setSource(QUrl.fromLocalFile(resolved_path))
            self.pet_media_player.play()
        elif movie is not None:
            self.pet_media_player.stop()
            self.pet_media_player.setSource(QUrl())
            self.pet_video_widget.hide()
            if self.pet_movie:
                dispose_image_movie(self.pet_movie)
            self.pet_movie = movie
            self.pet_label.setMovie(self.pet_movie)
            self.pet_movie.start()
            self.pet_label.show()
        else:
            self.pet_media_player.stop()
            self.pet_media_player.setSource(QUrl())
            self.pet_video_widget.hide()
            if self.pet_movie:
                dispose_image_movie(self.pet_movie)
                self.pet_movie = None
                self.pet_label.setMovie(None)
            self.pet_label.setPixmap(load_pixmap(resolved_path))
            self.pet_label.show()

        self._update_geometry()
        self._after_media_updated()

    def hide_pet(self):
        self._current_image_path = ""
        self._clear_media()
        self.hide()

    def set_size(self, size):
        self.pet_size = size
        self._update_geometry()

    def _set_media_geometry(self):
        self.pet_label.setGeometry(self.rect())
        self.pet_video_widget.setGeometry(self.rect())

    def _after_media_updated(self):
        self.show()

    def _update_geometry(self):
        raise NotImplementedError


class GoPetOverlay(_BasePetWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._edit_mode = False
        self._drag_pos = None

        # Position offset from bottom right
        self.offset_x = 50
        self.offset_y = 50

        self.hide()

    def ensure_on_top(self):
        if not self.isVisible():
            return

        self.raise_()

        # On Windows, explicitly move the pet window to the topmost band again
        # so transient visual overlays do not cover it.
        try:
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(
                int(self.winId()),
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
            )
        except Exception:
            pass

    def set_edit_mode(self, enabled):
        self._edit_mode = enabled
        if enabled:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool) # Remove TransparentForInput
            self.setStyleSheet("background-color: rgba(255, 255, 255, 50); border: 2px dashed #0078d4;")
            self.show()
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
            self.setStyleSheet("background-color: transparent; border: none;")
            if not self._current_image_path:
                self.hide()
        self.show() # Re-apply flags
        self.ensure_on_top()

    def _after_media_updated(self):
        self.show()
        self.ensure_on_top()

    def hide_pet(self):
        if not self._edit_mode:
            self._current_image_path = ""
            self._clear_media()
            self.hide()

    def set_size(self, size):
        self.pet_size = size
        self._update_geometry()

    def set_position(self, x, y):
        self.offset_x = x
        self.offset_y = y
        self._update_geometry()

    def _update_geometry(self):
        screen = self.screen().geometry()
        x = screen.width() - self.pet_size - self.offset_x
        y = screen.height() - self.pet_size - self.offset_y
        self.setGeometry(x, y, self.pet_size, self.pet_size)
        self._set_media_geometry()

    def mousePressEvent(self, event):
        if self._edit_mode and event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._edit_mode and event.buttons() == Qt.LeftButton and self._drag_pos:
            new_pos = event.globalPos() - self._drag_pos
            self.move(new_pos)
            
            # Calculate new offsets
            screen = self.screen().geometry()
            self.offset_x = screen.width() - new_pos.x() - self.pet_size
            self.offset_y = screen.height() - new_pos.y() - self.pet_size
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._edit_mode and event.button() == Qt.LeftButton:
            self._drag_pos = None
            # Here we could emit a signal to save the new offset_x and offset_y
            event.accept()


class GoPetCaptureWindow(_BasePetWindow):
    def __init__(self):
        super().__init__()
        # 主播输出窗口需要允许 OBS 采集，同时背景保持透明且不强制置顶。
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background-color: transparent;")
        self.pet_label.setStyleSheet("background-color: transparent;")
        self.pet_video_widget.setStyleSheet("background-color: transparent;")
        self.setWindowTitle("GO桌宠主播输出")

        self._drag_pos = None
        self._shell_enabled = False
        self._has_initial_position = False

        self.placeholder_label = BodyLabel("GO桌宠主播输出窗口\n可直接在 OBS 中捕获本窗口")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setParent(self)
        self.placeholder_label.setWordWrap(True)
        self._update_placeholder_style()
        self.placeholder_label.show()

        self.hide()

    def _update_placeholder_style(self):
        self.placeholder_label.setStyleSheet(
            "color: rgba(255, 255, 255, 0.78);"
            "background-color: rgba(0, 0, 0, 0.26);"
            "border: 1px dashed rgba(255, 255, 255, 0.24);"
            "border-radius: 12px;"
            "padding: 12px;"
        )

    def show_output_shell(self):
        self._shell_enabled = True
        if not self._current_image_path:
            self.placeholder_label.show()
        self._update_geometry()
        self.show()

    def hide_output_shell(self):
        self._shell_enabled = False
        self._current_image_path = ""
        self._clear_media()
        self.hide()

    def _after_media_updated(self):
        self.placeholder_label.hide()
        self.show()

    def hide_pet(self):
        self._current_image_path = ""
        self._clear_media()
        if self._shell_enabled:
            self.placeholder_label.show()
            self._update_geometry()
            self.show()
        else:
            self.hide()

    def _update_geometry(self):
        if not self._has_initial_position:
            screen = self.screen().availableGeometry()
            x = screen.x() + max(0, (screen.width() - self.pet_size) // 2)
            y = screen.y() + max(0, (screen.height() - self.pet_size) // 2)
            self.setGeometry(x, y, self.pet_size, self.pet_size)
            self._has_initial_position = True
        else:
            self.resize(self.pet_size, self.pet_size)
        self._set_media_geometry()
        self.placeholder_label.setGeometry(self.rect())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            event.accept()
