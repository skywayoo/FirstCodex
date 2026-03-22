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
        app.DOCS_DIR = app.DATA_DIR / 'openclaw_docs'
        app.ensure_data_files()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_default_files_created(self):
        self.assertTrue(app.CONFIG_PATH.exists())
        self.assertEqual(json.loads(app.TASKS_PATH.read_text()), [])
        self.assertTrue((app.DOCS_DIR / 'memory.md').exists())

    def test_openclaw_preview_uses_agent_fields_and_docs(self):
        config = app.read_json(app.CONFIG_PATH, app.DEFAULT_CONFIG)
        preview = app.OpenClawService(config).preview_command()
        self.assertIn('agent', preview)
        self.assertIn('--model', preview)
        self.assertIn('--memory-file', preview)
        self.assertIn(str(app.DOCS_DIR / 'memory.md'), preview)

    def test_sync_markdown_files_writes_docs(self):
        config = app.read_json(app.CONFIG_PATH, app.DEFAULT_CONFIG)
        config['openclaw']['docs']['memoryMd'] = '# memory\n\n- updated'
        paths = app.sync_markdown_files(config)
        self.assertEqual(paths['memoryMd'].read_text(encoding='utf-8'), '# memory\n\n- updated')

    def test_lobster_dry_run_dispatch_for_openclaw_agent(self):
        config = app.read_json(app.CONFIG_PATH, app.DEFAULT_CONFIG)
        service = app.LobsterService(config)
        result = service.dispatch({
            'queue': 'general',
            'target': 'demo',
            'channel': 'telegram',
            'mission': 'Summarize a competitor website.',
            'parameters': {'topic': 'ai agents'},
        })
        self.assertTrue(result.ok)
        self.assertIn('--agent', result.command)
        self.assertIn('Dry-run mode', result.stdout)


if __name__ == '__main__':
    unittest.main()
