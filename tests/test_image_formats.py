"""Decode real files and exercise the actual image display controls."""
import gzip
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.logic.image_loader import IMAGE_FILTER, IMAGE_EXTENSIONS, image_files, load_image, create_image_movie, dispose_image_movie
from app.logic.visual_handler import OverlayWindow
from app.ui.go_pet_overlay import GoPetCaptureWindow


class ImageFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = Image.new('RGBA', (32, 32), (244, 25, 48, 123))
        self.samples = {}
        formats = {'png':'PNG', 'apng':'PNG', 'jpg':'JPEG', 'jpeg':'JPEG', 'jpe':'JPEG', 'jfif':'JPEG',
                   'bmp':'BMP', 'dib':'DIB', 'gif':'GIF', 'webp':'WEBP', 'tif':'TIFF', 'tiff':'TIFF',
                   'avif':'AVIF', 'ico':'ICO', 'tga':'TGA'}
        for extension, format_name in formats.items():
            path = self.root / ('sample.' + extension)
            image = self.source.convert('RGB') if format_name in ('JPEG', 'BMP', 'DIB', 'GIF') else self.source
            image.save(path, format=format_name)
            self.samples[extension] = path
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#f41930" fill-opacity="0.48"/></svg>'
        for extension, data in (('svg', svg), ('svgz', gzip.compress(svg))):
            path = self.root / ('sample.' + extension)
            path.write_bytes(data)
            self.samples[extension] = path

    def animation(self, extension):
        path = self.root / ('animated.' + extension)
        frames = [Image.new('RGBA', (32, 32), color) for color in ('red', 'green')]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=80, loop=0, lossless=True)
        return path

    def test_all_advertised_formats_decode_real_files(self):
        self.assertEqual({'.' + extension for extension in self.samples}, IMAGE_EXTENSIONS)
        for extension, path in self.samples.items():
            with self.subTest(extension=extension):
                image = load_image(path)
                self.assertFalse(image.isNull(), extension)
                self.assertGreater(image.width(), 0)
                self.assertIn('*.' + extension, IMAGE_FILTER)

    def test_transparency_survives_native_and_avif_fallback_decoding(self):
        for extension in ('png', 'webp', 'tif', 'tiff', 'avif', 'tga'):
            with self.subTest(extension=extension):
                image = load_image(self.samples[extension])
                self.assertTrue(image.hasAlphaChannel())
                self.assertLessEqual(abs(image.pixelColor(0, 0).alpha() - 123), 1)

    def test_exif_orientation_is_applied(self):
        path = self.root / 'rotated.jpg'
        image = Image.new('RGB', (24, 12), 'red')
        exif = Image.Exif()
        exif[274] = 6
        image.save(path, exif=exif)
        decoded = load_image(path)
        self.assertEqual((decoded.width(), decoded.height()), (12, 24))

    def test_loader_uses_content_for_renamed_file(self):
        path = self.root / 'renamed.avif'
        path.write_bytes(self.samples['png'].read_bytes())
        self.assertFalse(load_image(path).isNull())

    def test_corrupt_missing_and_empty_paths_return_empty_image(self):
        path = self.root / 'broken.avif'
        path.write_bytes(b'not an image')
        for invalid in (path, self.root / 'missing.png', ''):
            self.assertTrue(load_image(invalid).isNull())

    def test_folder_selection_is_case_insensitive_and_excludes_subdirectories(self):
        upper = self.root / 'upper.WEBP'
        upper.write_bytes(self.samples['webp'].read_bytes())
        (self.root / 'folder.png').mkdir()
        (self.root / 'text.txt').write_text('text')
        files = image_files(self.root)
        self.assertIn(str(upper), files)
        self.assertNotIn(str(self.root / 'folder.png'), files)
        self.assertNotIn(str(self.root / 'text.txt'), files)
        self.assertEqual(len(files), len(self.samples) + 1)

    def test_gif_and_webp_movies_advance_frames(self):
        for extension in ('gif', 'webp'):
            with self.subTest(extension=extension):
                movie = create_image_movie(self.animation(extension))
                self.assertIsNotNone(movie)
                seen = []
                movie.frameChanged.connect(seen.append)
                movie.start()
                QTest.qWait(220)
                self.assertIn(0, seen)
                self.assertIn(1, seen)
                dispose_image_movie(movie)

    def test_real_overlay_displays_all_static_formats(self):
        with patch('app.logic.visual_handler.find_cs2_window', return_value=0):
            overlay = OverlayWindow()
            overlay.focus_timer.stop()
            overlay.geometry_timer.stop()
            try:
                for extension, path in self.samples.items():
                    with self.subTest(extension=extension):
                        overlay.set_flash_image(str(path))
                        self.assertFalse(overlay.flash_label.pixmap().isNull(), 'flash ' + extension)
                        overlay.set_death_media(str(path))
                        overlay.show_death()
                        self.assertFalse(overlay.death_label.pixmap().isNull(), 'death ' + extension)
                        overlay.hide_death()
                        overlay.show_kill_icon(str(path))
                        if overlay.kill_icon_movie:
                            self.assertTrue(overlay.kill_icon_movie.isValid())
                        else:
                            self.assertFalse(overlay.kill_icon_label.pixmap().isNull(), 'kill ' + extension)
            finally:
                overlay.close()

    def test_capture_pet_displays_all_static_formats_and_animated_webp(self):
        pet = GoPetCaptureWindow()
        try:
            for extension, path in self.samples.items():
                with self.subTest(extension=extension):
                    pet.update_pet(str(path))
                    if pet.pet_movie:
                        self.assertTrue(pet.pet_movie.isValid())
                    else:
                        self.assertFalse(pet.pet_label.pixmap().isNull(), extension)
            pet.update_pet(str(self.animation('webp')))
            self.assertIsNotNone(pet.pet_movie)
            QTest.qWait(120)
            pet.update_pet(str(self.samples['avif']))
            self.assertIsNone(pet.pet_movie)
            self.assertFalse(pet.pet_label.pixmap().isNull())
        finally:
            pet._clear_media()
            pet.close()


if __name__ == '__main__':
    unittest.main()
