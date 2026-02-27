import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class DebianCiWorkflowTests(unittest.TestCase):
    def test_ci_defines_debian_package_assurance_job(self):
        content = CI_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("deb-package-assurance:", content)
        self.assertIn("name: Debian Package Assurance", content)
        self.assertIn("docker build -f Dockerfile.deb -t screenux-deb-ci .", content)
        self.assertIn("docker run --rm -v \"$PWD/dist-deb:/out\" screenux-deb-ci", content)

    def test_ci_checks_security_integrity_and_performance_for_deb(self):
        content = CI_WORKFLOW.read_text(encoding="utf-8")

        required_snippets = [
            "dpkg-deb --info \"$deb_file\"",
            "dpkg-deb --contents \"$deb_file\"",
            "dpkg-deb -f \"$deb_file\" Package",
            "sha256sum \"$deb_file\"",
            "find \"$extract_dir\" -type f -perm /6000",
            "find \"$extract_dir\" -type f -perm -0002",
            "help_startup_ms=",
            "max_help_startup_ms=4000",
            "actions/upload-artifact@v4",
            "name: deb-ci-reports",
        ]

        for snippet in required_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, content)


if __name__ == "__main__":
    unittest.main()
