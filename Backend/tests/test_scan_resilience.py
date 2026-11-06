"""Offline checks for OCR trust configuration and optional-OCR scan failures."""
import importlib.util
import os
from pathlib import Path
import ssl
import sys
from types import ModuleType
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]


def load_file(name, relative, stubs):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def load_ocr():
    return load_file('ocr_test', 'vision/ocr.py',
                     {name: MagicMock() for name in ('cv2', 'easyocr', 'numpy', 'pandas')})


class CertificateTests(unittest.TestCase):
    def test_default_bundle_and_reader_cached(self):
        module = load_ocr()
        with patch.dict(os.environ, {}, clear=True):
            first = module.get_reader()
            self.assertEqual(os.environ['SSL_CERT_FILE'], module.certifi.where())
            context = ssl.create_default_context()
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            self.assertIs(module.get_reader(), first)
        module.easyocr.Reader.assert_called_once_with(['en'], gpu=False)

    def test_existing_trust_configuration_preserved(self):
        for key in ('SSL_CERT_FILE', 'SSL_CERT_DIR'):
            module = load_ocr()
            with self.subTest(key=key), patch.dict(os.environ, {key: '/custom/trust'}, clear=True):
                module.get_reader()
                self.assertEqual(os.environ[key], '/custom/trust')
                if key == 'SSL_CERT_DIR':
                    self.assertNotIn('SSL_CERT_FILE', os.environ)


class ScanTests(unittest.IsolatedAsyncioTestCase):
    def route(self, ocr_error=None):
        security = ModuleType('security')
        security.get_current_user = lambda: None
        database = ModuleType('database.configurations')
        database.inventory = MagicMock()
        database.inventory.update_one = AsyncMock()
        detector = ModuleType('vision.detector')
        detector.detect_ingredients = MagicMock(return_value={'ingredients': [{'name': 'apple', 'confidence': .9}]})
        ocr = ModuleType('vision.ocr')
        ocr.detect_text_ingredients = MagicMock(side_effect=ocr_error, return_value=[{'name': 'milk', 'confidence': .8}])
        route = load_file('scan_test', 'routes/scan.py', {
            'security': security, 'database.configurations': database,
            'vision.detector': detector, 'vision.ocr': ocr,
            'vision.video_detector': MagicMock()})
        return route

    def upload(self):
        return type('Upload', (), {'content_type': 'image/png', 'read': AsyncMock(return_value=b'image'), 'close': AsyncMock()})()

    async def test_download_failure_keeps_yolo_and_inventory_update(self):
        route = self.route(URLError(ssl.SSLCertVerificationError('certificate failed')))
        with self.assertLogs(route.__name__, level='WARNING'):
            result = await route.scan(self.upload(), {'_id': 'user'})
        self.assertEqual(result['ingredients'], ['apple'])
        self.assertEqual(len(result['warnings']), 1)
        route.inventory.update_one.assert_awaited_once()

    async def test_success_still_merges_ocr(self):
        route = self.route()
        result = await route.scan(self.upload(), {'_id': 'user'})
        self.assertEqual(result['ingredients'], ['apple', 'milk'])
        self.assertEqual(result['warnings'], [])

    async def test_failed_yolo_is_not_hidden(self):
        from fastapi import HTTPException
        route = self.route()
        route.detect_ingredients.side_effect = FileNotFoundError('missing weights')
        with self.assertRaises(HTTPException) as caught:
            await route.scan(self.upload(), {'_id': 'user'})
        self.assertEqual(caught.exception.status_code, 503)
        route.detect_text_ingredients.assert_not_called()
