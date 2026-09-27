"""Mise task-orchestration contract tests."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


class MiseTests(unittest.TestCase):
    def test_root_check_aggregates_nested_monorepo_checks(self):
        mise = shutil.which("mise")
        self.assertIsNotNone(mise, "mise must be on PATH")

        with tempfile.TemporaryDirectory(prefix="mise-monorepo-") as tmp:
            root = Path(tmp)
            (root / "packages/a").mkdir(parents=True)
            (root / "packages/nested/b").mkdir(parents=True)
            (root / "mise.toml").write_text(
                """\
monorepo_root = true

[monorepo]
config_roots = ["packages/a", "packages/nested/b"]

[tasks.check]
depends = ["//...:check"]
"""
            )
            markers = [root / "package-a-ran", root / "package-b-ran"]
            for config, marker in zip(
                (
                    root / "packages/a/mise.toml",
                    root / "packages/nested/b/mise.toml",
                ),
                markers,
            ):
                script = f"from pathlib import Path; Path({str(marker)!r}).touch()"
                command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"
                config.write_text(f"[tasks.check]\nrun = {json.dumps(command)}\n")
            global_config = root / "empty-global.toml"
            global_config.touch()
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("MISE_")
            }
            env.update(
                {
                    "MISE_AUTO_INSTALL": "0",
                    "MISE_GLOBAL_CONFIG_FILE": str(global_config),
                    "MISE_NO_HOOKS": "1",
                    "MISE_OFFLINE": "1",
                    "MISE_TRUSTED_CONFIG_PATHS": str(root),
                    "NO_COLOR": "1",
                }
            )

            result = subprocess.run(
                [mise, "-C", str(root), "run", "check"],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(all(marker.is_file() for marker in markers), result.stdout)


if __name__ == "__main__":
    unittest.main()
