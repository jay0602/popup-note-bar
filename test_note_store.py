import json
import tempfile
import unittest
from pathlib import Path

from note_store import NoteStore


class NoteStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "notes.json"
        self.store = NoteStore(self.path)
        self.store.load()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_first_load_creates_welcome_note_and_file(self):
        self.assertEqual(len(self.store.notes), 1)
        self.assertTrue(self.path.exists())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["version"], 1)

    def test_add_update_search_and_reload(self):
        note = self.store.add("採買清單")
        self.store.update(note.id, "採買清單", "牛奶、咖啡、電池")
        self.assertEqual([item.id for item in self.store.search("咖啡")], [note.id])
        reloaded = NoteStore(self.path)
        reloaded.load()
        self.assertEqual(reloaded.get(note.id).content, "牛奶、咖啡、電池")

    def test_delete_keeps_one_editable_note(self):
        only_note = self.store.notes[0]
        self.assertTrue(self.store.delete(only_note.id))
        self.assertEqual(len(self.store.notes), 1)
        self.assertNotEqual(self.store.notes[0].id, only_note.id)

    def test_empty_title_uses_first_content_line(self):
        note = self.store.notes[0]
        updated = self.store.update(note.id, "", "  自動標題\n第二行")
        self.assertEqual(updated.title, "自動標題")


if __name__ == "__main__":
    unittest.main()
