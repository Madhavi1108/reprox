import subprocess
from pathlib import Path

import pytest

from app.provenance.code import capture_code_provenance


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@reprox.local")
    _git(repo, "config", "user.name", "Reprox Test")


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "clean_repo"
    _init_repo(repo)
    (repo / "train.py").write_text("print('hello')\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


def test_clean_repo_captures_commit_and_is_not_dirty(clean_repo: Path):
    prov = capture_code_provenance(clean_repo)
    assert prov.vcs_present is True
    assert prov.git_commit_sha is not None
    assert len(prov.git_commit_sha) == 40
    assert prov.is_dirty is False
    assert prov.is_detached_head is False
    assert prov.is_shallow_clone is False
    assert prov.tree_fingerprint_hash is not None
    assert prov.file_count == 1


def test_dirty_tree_from_modified_tracked_file_is_detected(clean_repo: Path):
    baseline = capture_code_provenance(clean_repo)

    (clean_repo / "train.py").write_text("print('hello modified')\n")
    modified = capture_code_provenance(clean_repo)

    # Commit SHA is unchanged (nothing was committed) but the tree must
    # differ - this is the core "never report code identical when
    # uncommitted modifications exist" rule.
    assert modified.git_commit_sha == baseline.git_commit_sha
    assert modified.is_dirty is True
    assert modified.tree_fingerprint_hash != baseline.tree_fingerprint_hash


def test_dirty_tree_from_untracked_new_file_is_detected(clean_repo: Path):
    baseline = capture_code_provenance(clean_repo)

    (clean_repo / "new_helper.py").write_text("def helper(): pass\n")
    with_untracked = capture_code_provenance(clean_repo)

    assert with_untracked.is_dirty is True
    assert with_untracked.file_count == baseline.file_count + 1
    assert with_untracked.tree_fingerprint_hash != baseline.tree_fingerprint_hash


def test_detached_head_is_detected(clean_repo: Path):
    commit_sha = subprocess.run(
        ["git", "-C", str(clean_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    _git(clean_repo, "checkout", "-q", commit_sha)

    prov = capture_code_provenance(clean_repo)
    assert prov.is_detached_head is True
    assert prov.git_branch is None
    assert prov.git_commit_sha == commit_sha


def test_no_git_repository_falls_back_to_filesystem_walk(tmp_path: Path):
    plain_dir = tmp_path / "no_repo"
    plain_dir.mkdir()
    (plain_dir / "script.py").write_text("x = 1\n")

    prov = capture_code_provenance(plain_dir)
    assert prov.vcs_present is False
    assert prov.git_commit_sha is None
    assert prov.is_dirty is False
    assert prov.tree_fingerprint_hash is not None
    assert prov.file_count == 1
    assert prov.notes is not None and "no_git_repository" in prov.notes


def test_shallow_clone_is_detected(tmp_path: Path):
    origin = tmp_path / "origin"
    _init_repo(origin)
    (origin / "a.py").write_text("a = 1\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "first")
    (origin / "a.py").write_text("a = 2\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "second")

    shallow = tmp_path / "shallow"
    # --no-local forces git to treat this like a real network clone;
    # otherwise git's local-clone optimization silently ignores --depth
    # when both paths are on the same filesystem.
    subprocess.run(
        ["git", "clone", "--no-local", "--depth", "1", str(origin), str(shallow)],
        check=True, capture_output=True, text=True,
    )
    _git(shallow, "config", "user.email", "test@reprox.local")
    _git(shallow, "config", "user.name", "Reprox Test")

    prov = capture_code_provenance(shallow)
    assert prov.vcs_present is True
    assert prov.is_shallow_clone is True


def test_fingerprint_deterministic_across_repeated_capture(clean_repo: Path):
    a = capture_code_provenance(clean_repo)
    b = capture_code_provenance(clean_repo)
    assert a.tree_fingerprint_hash == b.tree_fingerprint_hash


def test_file_rename_changes_tree_hash_even_with_same_content(clean_repo: Path):
    baseline = capture_code_provenance(clean_repo)
    (clean_repo / "train.py").rename(clean_repo / "renamed_train.py")
    renamed = capture_code_provenance(clean_repo)
    assert renamed.tree_fingerprint_hash != baseline.tree_fingerprint_hash
    assert renamed.is_dirty is True
