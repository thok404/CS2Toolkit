"""Shared image formats and decoding for backgrounds and game overlays."""

import os
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtGui import QImage, QImageReader, QPixmap, QMovie

IMAGE_EXTENSIONS = frozenset({
    '.png', '.apng', '.jpg', '.jpeg', '.jpe', '.jfif', '.bmp', '.dib',
    '.gif', '.webp', '.tif', '.tiff', '.avif', '.ico', '.svg', '.svgz', '.tga',
})
VIDEO_EXTENSIONS = frozenset({'.mp4', '.webm', '.avi', '.mov', '.mkv'})
IMAGE_FILTER = '图片文件 (' + ' '.join('*' + extension for extension in sorted(IMAGE_EXTENSIONS)) + ')'
MEDIA_FILTER = '媒体文件 (' + ' '.join('*' + extension for extension in sorted(IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)) + ')'


def image_files(directory):
    if not os.path.isdir(directory):
        return []
    return [str(path) for path in sorted(Path(directory).iterdir())
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]


def load_image(path):
    """Decode by content, preserving transparency and EXIF orientation."""
    reader = QImageReader(os.fspath(path))
    reader.setAutoTransform(True)
    image = reader.read()
    if not image.isNull():
        return image
    try:
        with Image.open(path) as source:
            rgba = ImageOps.exif_transpose(source).convert('RGBA')
            return QImage(rgba.tobytes(), rgba.width, rgba.height, rgba.width * 4,
                          QImage.Format_RGBA8888).copy()
    except (OSError, ValueError, Image.DecompressionBombError):
        return QImage()


def load_pixmap(path):
    return QPixmap.fromImage(load_image(path))


def create_image_movie(path, parent=None):
    """Play native GIF/animated WebP; static formats use load_pixmap."""
    reader = QImageReader(os.fspath(path))
    if not reader.supportsAnimation():
        return None
    movie = QMovie(os.fspath(path), parent=parent)
    if not movie.isValid():
        movie.deleteLater()
        return None
    return movie


def dispose_image_movie(movie):
    if movie is not None:
        movie.stop()
        movie.setFileName('')
        movie.deleteLater()
