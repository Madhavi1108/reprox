"""Code provenance capture (spec section 9-10).

Ground-truth identity for "what code was executed" is the
`tree_fingerprint_hash` computed from actual on-disk file content at
capture time - NOT the git commit SHA. A dirty working tree must never
collapse to "code identical" just because HEAD matches a known commit;
git metadata (`git_commit_sha`, `git_branch`, `is_dirty`,
`is_detached_head`, `is_shallow_clone`) is captured as supplementary
evidence, never as a substitute for the tree hash.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.provenance.canonicalize import canonical_hash, sha256_hex

CODE_FINGERPRINT_VERSION = "1.0.0"

_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".sql": "sql",
    ".sh": "shell",
    ".ipynb": "jupyter-notebook",
}

_DEFAULT_EXCLUDED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}


def _detect_language(path: Path) -> str | None:
    return _LANGUAGE_BY_EXTENSION.get(path.suffix.lower())


@dataclass(frozen=True)
class CodeFileEntry:
    relative_path: str
    size_bytes: int
    file_hash: str
    language: str | None


@dataclass(frozen=True)
class CodeProvenance:
    vcs_present: bool
    git_commit_sha: str | None
    git_branch: str | None
    is_dirty: bool
    is_detached_head: bool
    is_shallow_clone: bool
    tree_fingerprint_hash: str | None
    fingerprint_version: str
    files: list[CodeFileEntry] = field(default_factory=list)
    notes: str | None = None

    @property
    def file_count(self) -> int:
        return len(self.files)


def _run_git(root: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _is_git_repo(root: Path) -> bool:
    code, out, _ = _run_git(root, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out == "true"


def _list_git_tracked_and_untracked_files(root: Path) -> list[str]:
    """Tracked files (as of the index) plus untracked-but-not-ignored files,
    so the tree hash reflects what would actually be used to run the
    experiment right now - including files added but not yet committed."""
    _, tracked, _ = _run_git(root, "ls-files")
    _, untracked, _ = _run_git(root, "ls-files", "--others", "--exclude-standard")
    paths = set(p for p in tracked.splitlines() if p)
    paths.update(p for p in untracked.splitlines() if p)
    return sorted(paths)


def _hash_file(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), sha256_hex(data)


def _build_file_entries(root: Path, relative_paths: list[str]) -> list[CodeFileEntry]:
    entries: list[CodeFileEntry] = []
    for rel in relative_paths:
        full = root / rel
        if not full.is_file():
            continue  # deleted-but-still-indexed or a submodule/symlink edge case
        size, digest = _hash_file(full)
        entries.append(
            CodeFileEntry(
                relative_path=rel,
                size_bytes=size,
                file_hash=digest,
                language=_detect_language(full),
            )
        )
    return sorted(entries, key=lambda e: e.relative_path)


def _walk_filesystem(root: Path) -> list[str]:
    """Fallback enumeration when no git repository is present."""
    relative_paths: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _DEFAULT_EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        relative_paths.append(path.relative_to(root).as_posix())
    return sorted(relative_paths)


def _compute_tree_fingerprint(entries: list[CodeFileEntry]) -> str:
    payload = [
        {"path": e.relative_path, "size": e.size_bytes, "hash": e.file_hash, "language": e.language}
        for e in entries
    ]
    return canonical_hash(payload)


def capture_code_provenance(root: Path) -> CodeProvenance:
    """Capture code provenance for the tree rooted at `root`.

    Handles: no git repository, detached HEAD, shallow clone, dirty
    working tree (uncommitted modifications, staged changes, and
    untracked-but-not-ignored new files all count as dirty and are all
    reflected in the tree hash).
    """
    root = root.resolve()

    if not _is_git_repo(root):
        relative_paths = _walk_filesystem(root)
        entries = _build_file_entries(root, relative_paths)
        return CodeProvenance(
            vcs_present=False,
            git_commit_sha=None,
            git_branch=None,
            is_dirty=False,
            is_detached_head=False,
            is_shallow_clone=False,
            tree_fingerprint_hash=_compute_tree_fingerprint(entries) if entries else None,
            fingerprint_version=CODE_FINGERPRINT_VERSION,
            files=entries,
            notes="no_git_repository: tree hash computed from full filesystem walk",
        )

    commit_code, commit_sha, _ = _run_git(root, "rev-parse", "HEAD")
    git_commit_sha = commit_sha if commit_code == 0 else None

    _, branch_name, _ = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    is_detached_head = branch_name == "HEAD"
    git_branch = None if is_detached_head else (branch_name or None)

    _, status_output, _ = _run_git(root, "status", "--porcelain")
    is_dirty = bool(status_output.strip())

    _, shallow_output, _ = _run_git(root, "rev-parse", "--is-shallow-repository")
    is_shallow_clone = shallow_output == "true"

    relative_paths = _list_git_tracked_and_untracked_files(root)
    entries = _build_file_entries(root, relative_paths)

    notes = None
    if git_commit_sha is None:
        notes = "git_repository_with_no_commits: tree hash reflects working tree only"

    return CodeProvenance(
        vcs_present=True,
        git_commit_sha=git_commit_sha,
        git_branch=git_branch,
        is_dirty=is_dirty,
        is_detached_head=is_detached_head,
        is_shallow_clone=is_shallow_clone,
        tree_fingerprint_hash=_compute_tree_fingerprint(entries) if entries else None,
        fingerprint_version=CODE_FINGERPRINT_VERSION,
        files=entries,
        notes=notes,
    )
