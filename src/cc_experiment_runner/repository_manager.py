"""Repository management for cloning and organizing experiment runs."""

import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
import json

import git


class RunContext:
    """Context for managing experiment runs."""

    def __init__(
        self,
        run_id: str,
        repo_url: str,
        base_data_dir: Path,
        library_name: Optional[str] = None,
        library_version: Optional[str] = None,
        branch: Optional[str] = None,
        commit_hash: Optional[str] = None,
        docs_path: Optional[str] = None
    ):
        self.run_id = run_id
        self.repo_url = repo_url
        self.base_data_dir = base_data_dir
        self.library_name = library_name
        self.library_version = library_version
        self.branch = branch
        self.commit_hash = commit_hash
        self.docs_path = docs_path

        # Simple directory structure: just the repository
        self.repo_dir = base_data_dir / run_id

        # Metadata
        self.created_at = datetime.now().isoformat()
        self.status = "initializing"

    def save_metadata(self) -> None:
        """Save run context metadata to JSON file."""
        metadata = {
            "run_id": self.run_id,
            "repo_url": self.repo_url,
            "library_name": self.library_name,
            "library_version": self.library_version,
            "branch": self.branch,
            "commit_hash": self.commit_hash,
            "docs_path": self.docs_path,
            "created_at": self.created_at,
            "status": self.status,
        }

        metadata_file = self.repo_dir / ".metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    def mark_cloned(self) -> None:
        """Mark repository cloning as completed."""
        self.status = "cloned"
        self.save_metadata()

    @classmethod
    def load(cls, run_id: str, base_data_dir: Path) -> "RunContext":
        """Load existing run context by ID."""
        repo_dir = base_data_dir / run_id
        metadata_file = repo_dir / ".metadata.json"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Run context not found: {run_id}")

        with open(metadata_file) as f:
            metadata = json.load(f)

        context = cls(
            run_id=metadata["run_id"],
            repo_url=metadata["repo_url"],
            base_data_dir=base_data_dir,
            library_name=metadata.get("library_name"),
            library_version=metadata.get("library_version"),
            branch=metadata.get("branch"),
            commit_hash=metadata.get("commit_hash"),
            docs_path=metadata.get("docs_path")
        )
        context.created_at = metadata["created_at"]
        context.status = metadata["status"]

        return context


class RepositoryManager:
    """Manages repository cloning for experiments."""

    def __init__(self, base_data_dir: Optional[Path] = None):
        """Initialize repository manager with data directory."""
        self.base_data_dir = base_data_dir or Path.cwd() / "data"
        self.base_data_dir.mkdir(parents=True, exist_ok=True)

    def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
        run_id: Optional[str] = None,
        library_name: Optional[str] = None,
        library_version: Optional[str] = None,
        docs_path: Optional[str] = None
    ) -> RunContext:
        """Clone repository for experiment.

        Args:
            repo_url: Git repository URL to clone
            branch: Git branch to clone (default: main)
            run_id: Optional run ID (if None, will be auto-generated)
            library_name: Optional library name for metadata
            library_version: Optional library version for metadata
            docs_path: Optional base documentation path (e.g., 'docs')

        Returns:
            RunContext with cloned repository
        """
        # Generate run_id if not provided
        if not run_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            run_id = f"experiment_{repo_name}_{timestamp}"

        # Create run context
        context = RunContext(
            run_id=run_id,
            repo_url=repo_url,
            base_data_dir=self.base_data_dir,
            library_name=library_name,
            library_version=library_version,
            branch=branch,
            docs_path=docs_path
        )

        # Check if directory already exists
        if context.repo_dir.exists():
            raise RuntimeError(
                f"Repository directory already exists: {context.repo_dir}\n"
                f"Please remove it first or use a different run_id"
            )

        try:
            # Create directory
            context.repo_dir.mkdir(parents=True, exist_ok=True)

            # Clone repository
            print(f"📦 Cloning {repo_url} (branch: {branch})...")
            cloned_repo = git.Repo.clone_from(
                repo_url,
                context.repo_dir,
                branch=branch
            )

            # Get actual commit hash
            context.commit_hash = cloned_repo.head.commit.hexsha[:7]
            print(f"✅ Cloned successfully (commit: {context.commit_hash})")

            # Save metadata and mark as cloned
            context.mark_cloned()

            return context

        except Exception as e:
            # Cleanup on failure
            if context.repo_dir.exists():
                shutil.rmtree(context.repo_dir)
            raise RuntimeError(f"Failed to clone repository {repo_url}: {e}")

    def cleanup_run(self, run_id: str) -> None:
        """Remove a run directory and all its contents."""
        run_dir = self.base_data_dir / run_id
        if run_dir.exists():
            print(f"🗑️  Removing {run_dir}")
            shutil.rmtree(run_dir)

    def list_runs(self) -> list[str]:
        """List all available run IDs."""
        runs = []
        for item in self.base_data_dir.iterdir():
            if item.is_dir() and (item / ".metadata.json").exists():
                runs.append(item.name)
        return runs
