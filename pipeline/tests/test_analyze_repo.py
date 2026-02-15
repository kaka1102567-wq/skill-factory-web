"""Tests for pipeline/commands/analyze_repo.py."""

import json
import os
import shutil
import tempfile

import pytest

from pipeline.commands.analyze_repo import (
    scan_repo,
    extract_docs,
    analyze_code,
    _file_importance,
    run_analyze_repo,
)


@pytest.fixture
def mock_repo(tmp_path):
    """Create a fake repository structure for testing."""
    # README
    (tmp_path / "README.md").write_text("# My Project\nA test project.", encoding="utf-8")

    # Source files
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")
    (src / "utils.py").write_text("def helper():\n    return 42\n", encoding="utf-8")
    (src / "app.ts").write_text("export function app() { return true; }", encoding="utf-8")

    # Docs
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# User Guide\nHow to use.", encoding="utf-8")
    (docs / "api.md").write_text("# API Reference\nEndpoints.", encoding="utf-8")

    # Config
    (tmp_path / "package.json").write_text('{"name": "test"}', encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("flask\nrequests\n", encoding="utf-8")

    # Tests
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text("def test_main(): pass\n", encoding="utf-8")

    # .git (should be ignored)
    git = tmp_path / ".git"
    git.mkdir()
    (git / "config").write_text("git config", encoding="utf-8")

    # node_modules (should be ignored)
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "some_pkg.js").write_text("module.exports = {}", encoding="utf-8")

    return str(tmp_path)


@pytest.fixture
def tmp_output():
    d = tempfile.mkdtemp(prefix="sf_test_output_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestScanRepo:
    def test_scan_finds_readme(self, mock_repo):
        result = scan_repo(mock_repo)
        assert result["readme"] == "README.md"

    def test_scan_finds_source_files(self, mock_repo):
        result = scan_repo(mock_repo)
        paths = result["source_files"]
        assert any("main.py" in p for p in paths)
        assert any("utils.py" in p for p in paths)
        assert any("app.ts" in p for p in paths)

    def test_scan_finds_docs(self, mock_repo):
        result = scan_repo(mock_repo)
        assert len(result["docs"]) == 2

    def test_scan_finds_config_files(self, mock_repo):
        result = scan_repo(mock_repo)
        assert any("package.json" in p for p in result["config_files"])

    def test_scan_finds_test_files(self, mock_repo):
        result = scan_repo(mock_repo)
        assert len(result["test_files"]) == 1

    def test_scan_detects_languages(self, mock_repo):
        result = scan_repo(mock_repo)
        assert "python" in result["languages"]
        assert "typescript" in result["languages"]

    def test_scan_ignores_git_and_node_modules(self, mock_repo):
        result = scan_repo(mock_repo)
        all_paths = (
            result["source_files"] + result["docs"]
            + result["config_files"] + result["test_files"]
        )
        for p in all_paths:
            assert ".git" not in p
            assert "node_modules" not in p

    def test_scan_total_files(self, mock_repo):
        result = scan_repo(mock_repo)
        # README + 3 source + 2 docs + 2 config + 1 test = 9
        assert result["total_files"] == 9


class TestExtractDocs:
    def test_extract_readme(self, mock_repo, tmp_output):
        scan = scan_repo(mock_repo)
        created = extract_docs(mock_repo, "https://github.com/test/repo", scan, tmp_output)
        assert len(created) >= 1
        readme_path = os.path.join(tmp_output, "repo_readme.md")
        assert os.path.exists(readme_path)
        content = open(readme_path, encoding="utf-8").read()
        assert "source_type: github_readme" in content
        assert "My Project" in content

    def test_extract_docs_files(self, mock_repo, tmp_output):
        scan = scan_repo(mock_repo)
        created = extract_docs(mock_repo, "https://github.com/test/repo", scan, tmp_output)
        # README + 2 docs = 3
        assert len(created) == 3


class TestAnalyzeCode:
    def test_analyze_creates_json(self, mock_repo, tmp_output):
        scan = scan_repo(mock_repo)
        out_path = analyze_code(mock_repo, "https://github.com/test/repo", scan, tmp_output)
        assert os.path.exists(out_path)
        assert out_path.endswith("code_analysis.json")

    def test_analyze_json_structure(self, mock_repo, tmp_output):
        scan = scan_repo(mock_repo)
        analyze_code(mock_repo, "https://github.com/test/repo", scan, tmp_output)
        with open(os.path.join(tmp_output, "code_analysis.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert "repo_url" in data
        assert "repo_structure" in data
        assert "analyzed_files" in data
        assert data["repo_structure"]["primary_language"] == "python"

    def test_analyze_files_have_content(self, mock_repo, tmp_output):
        scan = scan_repo(mock_repo)
        analyze_code(mock_repo, "https://github.com/test/repo", scan, tmp_output)
        with open(os.path.join(tmp_output, "code_analysis.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["analyzed_files"]) > 0
        for af in data["analyzed_files"]:
            assert "path" in af
            assert "content" in af
            assert "language" in af


class TestFileImportance:
    def test_entry_point_high_score(self, mock_repo):
        score = _file_importance(mock_repo, "src/main.py")
        generic = _file_importance(mock_repo, "src/utils.py")
        assert score > generic


class TestRunAnalyzeRepo:
    def test_run_with_local_path(self, mock_repo, tmp_output):
        code = run_analyze_repo(mock_repo, tmp_output, analyze_code_flag=True)
        assert code == 0
        assert os.path.exists(os.path.join(tmp_output, "repo_readme.md"))
        assert os.path.exists(os.path.join(tmp_output, "code_analysis.json"))

    def test_run_docs_only(self, mock_repo, tmp_output):
        code = run_analyze_repo(mock_repo, tmp_output, analyze_code_flag=False)
        assert code == 0
        assert os.path.exists(os.path.join(tmp_output, "repo_readme.md"))
        assert not os.path.exists(os.path.join(tmp_output, "code_analysis.json"))

    def test_run_with_bad_url(self, tmp_output):
        code = run_analyze_repo("https://gitlab.com/user/repo", tmp_output)
        assert code == 1
