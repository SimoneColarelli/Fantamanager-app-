import os
import tempfile
import unittest
from pathlib import Path

from persistence.env_loader import load_env_file


class EnvLoaderTests(unittest.TestCase):
    def test_load_env_file_without_overriding_existing_environment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "FANTAMANAGER_SYNC_MODE=auto",
                        "FANTAMANAGER_SUPABASE_DB_URL='postgresql://example'",
                    ]
                ),
                encoding="utf-8",
            )

            old_mode = os.environ.get("FANTAMANAGER_SYNC_MODE")
            old_url = os.environ.get("FANTAMANAGER_SUPABASE_DB_URL")
            os.environ["FANTAMANAGER_SYNC_MODE"] = "manual"
            os.environ.pop("FANTAMANAGER_SUPABASE_DB_URL", None)
            try:
                loaded = load_env_file(env_path)

                self.assertEqual(os.environ["FANTAMANAGER_SYNC_MODE"], "manual")
                self.assertEqual(
                    os.environ["FANTAMANAGER_SUPABASE_DB_URL"],
                    "postgresql://example",
                )
                self.assertNotIn("FANTAMANAGER_SYNC_MODE", loaded)
                self.assertEqual(
                    loaded["FANTAMANAGER_SUPABASE_DB_URL"],
                    "postgresql://example",
                )
            finally:
                if old_mode is None:
                    os.environ.pop("FANTAMANAGER_SYNC_MODE", None)
                else:
                    os.environ["FANTAMANAGER_SYNC_MODE"] = old_mode

                if old_url is None:
                    os.environ.pop("FANTAMANAGER_SUPABASE_DB_URL", None)
                else:
                    os.environ["FANTAMANAGER_SUPABASE_DB_URL"] = old_url


if __name__ == "__main__":
    unittest.main()
