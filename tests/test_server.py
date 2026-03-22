import json
import tempfile
import unittest
from pathlib import Path

import app


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        app.DATA_DIR = Path(self.tempdir.name)
        app.CONFIG_PATH = app.DATA_DIR / 'config.json'
        app.TASKS_PATH = app.DATA_DIR / 'tasks.json'
        app.ensure_data_files()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_default_files_created(self):
        self.assertTrue(app.CONFIG_PATH.exists())
        self.assertEqual(json.loads(app.TASKS_PATH.read_text()), [])

    def test_lobster_dry_run_dispatch(self):
        config = app.read_json(app.CONFIG_PATH, app.DEFAULT_CONFIG)
        service = app.LobsterService(config)
        result = service.dispatch({
            'queue': 'general',
            'target': 'demo',
            'channel': 'telegram',
            'parameters': {'k': 'v'},
        })
        self.assertTrue(result.ok)
        self.assertIn('dispatch', result.command)
        self.assertIn('Dry-run mode', result.stdout)


if __name__ == '__main__':
    unittest.main()
