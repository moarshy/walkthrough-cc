"""Repository management for cloning and organizing API signature analysis runs."""

import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

import git


class RunContext:
    """Context for managing API signature analysis runs."""

    def __init__(
        self,
        run_id: str,
        repo_url: str,
        base_data_dir: Path,
        analysis_type: str = "api_signature",
        library_name: Optional[str] = None,
        library_version: Optional[str] = None,
        branch: Optional[str] = None,
        doc_commit_hash: Optional[str] = None,
        docs_path: Optional[str] = None,
        include_folders: Optional[List[str]] = None
    ):
        self.run_id = run_id
        self.repo_url = repo_url
        self.analysis_type = analysis_type
        self.base_data_dir = base_data_dir
        self.library_name = library_name
        self.library_version = library_version
        self.branch = branch
        self.doc_commit_hash = doc_commit_hash
        self.docs_path = docs_path
        self.include_folders = include_folders or []

        # Directory structure
        self.run_dir = base_data_dir / run_id
        self.repo_dir = self.run_dir / "repository"
        self.results_dir = self.run_dir / "results"
        self.cache_dir = self.run_dir / "cache"

        # Metadata
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.status = "initializing"
        self.num_workers: Optional[int] = None
        self.extraction_duration_seconds: Optional[float] = None
        self.api_validation_duration_seconds: Optional[float] = None
        self.code_validation_duration_seconds: Optional[float] = None

        # Document discovery & filtering metrics
        self.total_markdown_files: Optional[int] = None
        self.markdown_in_include_folders: Optional[int] = None
        self.filtered_api_reference_count: Optional[int] = None
        self.validated_document_count: Optional[int] = None

    @classmethod
    def create(
        cls,
        repo_url: str,
        base_data_dir: Path,
        analysis_type: str = "api_signature"
    ) -> "RunContext":
        """Create a new run context with unique run ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        run_id = f"{analysis_type}_{repo_name}_{timestamp}"

        return cls(run_id, repo_url, base_data_dir, analysis_type)

    def create_directories(self) -> None:
        """Create necessary directories for the run."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.repo_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)

        # Save context metadata
        self.save_metadata()

    def save_metadata(self) -> None:
        """Save run context metadata to JSON file."""
        metadata = {
            "run_id": self.run_id,
            "repo_url": self.repo_url,
            "analysis_type": self.analysis_type,
            "library_name": self.library_name,
            "library_version": self.library_version,
            "branch": self.branch,
            "doc_commit_hash": self.doc_commit_hash,
            "docs_path": self.docs_path,
            "include_folders": self.include_folders,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "num_workers": self.num_workers,
            "extraction_duration_seconds": self.extraction_duration_seconds,
            "api_validation_duration_seconds": self.api_validation_duration_seconds,
            "code_validation_duration_seconds": self.code_validation_duration_seconds,
            "total_markdown_files": self.total_markdown_files,
            "markdown_in_include_folders": self.markdown_in_include_folders,
            "filtered_api_reference_count": self.filtered_api_reference_count,
            "validated_document_count": self.validated_document_count,
        }

        metadata_file = self.run_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    def mark_clone_completed(self) -> None:
        """Mark repository cloning as completed."""
        self.status = "cloned"
        self.save_metadata()

    def mark_analysis_completed(self) -> None:
        """Mark analysis as completed."""
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()
        self.save_metadata()

    @classmethod
    def load(cls, run_id: str, base_data_dir: Path) -> "RunContext":
        """Load existing run context by ID."""
        run_dir = base_data_dir / run_id
        metadata_file = run_dir / "metadata.json"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Run context not found: {run_id}")

        with open(metadata_file) as f:
            metadata = json.load(f)

        context = cls(
            run_id=metadata["run_id"],
            repo_url=metadata["repo_url"],
            base_data_dir=base_data_dir,
            analysis_type=metadata.get("analysis_type", "api_signature"),
            library_name=metadata.get("library_name"),
            library_version=metadata.get("library_version"),
            branch=metadata.get("branch"),
            doc_commit_hash=metadata.get("doc_commit_hash"),
            docs_path=metadata.get("docs_path"),
            include_folders=metadata.get("include_folders", [])
        )
        context.created_at = metadata["created_at"]
        context.completed_at = metadata.get("completed_at")
        context.status = metadata["status"]
        context.num_workers = metadata.get("num_workers")
        context.extraction_duration_seconds = metadata.get("extraction_duration_seconds")
        context.api_validation_duration_seconds = metadata.get("api_validation_duration_seconds")
        context.code_validation_duration_seconds = metadata.get("code_validation_duration_seconds")
        context.total_markdown_files = metadata.get("total_markdown_files")
        context.markdown_in_include_folders = metadata.get("markdown_in_include_folders")
        context.filtered_api_reference_count = metadata.get("filtered_api_reference_count")
        context.validated_document_count = metadata.get("validated_document_count")

        return context


class RepositoryManager:
    """Manages repository cloning and run organization for API signature analysis."""

    def __init__(self, base_data_dir: Optional[Path] = None):
        """Initialize repository manager with data directory."""
        self.base_data_dir = base_data_dir or Path.cwd() / "data"
        self.base_data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def resolve_commit_hash(repo_url: str, branch: str, commit: Optional[str] = None) -> str:
        """Resolve commit hash from branch HEAD if not provided.

        Args:
            repo_url: Git repository URL
            branch: Git branch name
            commit: Optional commit hash (if provided, returned as-is)

        Returns:
            Resolved commit hash (7-40 characters)

        Raises:
            RuntimeError: If commit resolution fails
        """
        # If commit provided, return it directly
        if commit:
            # Basic validation: commit should be alphanumeric (git commit hashes)
            if not all(c in '0123456789abcdef' for c in commit.lower()):
                raise RuntimeError(f"Invalid commit hash format: {commit}")
            return commit

        # Otherwise, resolve branch HEAD to commit hash
        import tempfile
        temp_dir = Path(tempfile.mkdtemp(prefix="stackbench_resolve_"))

        try:
            # Shallow clone (depth=1) to get latest commit only - faster
            repo = git.Repo.clone_from(
                repo_url,
                temp_dir,
                branch=branch,
                depth=1
            )

            # Get HEAD commit hash (short form: 7 chars)
            commit_hash = repo.head.commit.hexsha[:7]

            return commit_hash

        except Exception as e:
            raise RuntimeError(f"Failed to resolve commit hash for {repo_url}@{branch}: {e}")

        finally:
            # Cleanup temporary directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
        run_id: Optional[str] = None,
        library_name: Optional[str] = None,
        library_version: Optional[str] = None,
        commit: Optional[str] = None,
        docs_path: Optional[str] = None,
        include_folders: Optional[List[str]] = None
    ) -> RunContext:
        """Clone repository and set up run directory structure.

        Args:
            repo_url: Git repository URL to clone
            branch: Git branch to clone (default: main)
            run_id: Optional run ID (if None, will be auto-generated)
            library_name: Optional library name for metadata
            library_version: Optional library version for metadata
            commit: Optional commit hash (if None, will be resolved from branch HEAD)
            docs_path: Optional base documentation path (e.g., 'docs/src')
            include_folders: Optional list of folders relative to docs_path

        Returns:
            RunContext with cloned repository and directory structure
        """
        # Resolve commit hash first (before cloning)
        print(f"🔍 Resolving commit hash for {branch}...")
        resolved_commit = self.resolve_commit_hash(repo_url, branch, commit)
        print(f"✅ Resolved commit: {resolved_commit}")

        # Create run context with configuration
        if run_id:
            # Use provided run_id
            context = RunContext(
                run_id=run_id,
                repo_url=repo_url,
                base_data_dir=self.base_data_dir,
                library_name=library_name,
                library_version=library_version,
                branch=branch,
                doc_commit_hash=resolved_commit,
                docs_path=docs_path,
                include_folders=include_folders
            )
        else:
            # Generate run_id automatically
            context = RunContext.create(
                repo_url=repo_url,
                base_data_dir=self.base_data_dir
            )
            # Update metadata fields even for auto-generated IDs
            context.library_name = library_name
            context.library_version = library_version
            context.branch = branch
            context.doc_commit_hash = resolved_commit
            context.docs_path = docs_path
            context.include_folders = include_folders or []
        context.create_directories()

        try:
            # Clone repository with specific branch
            cloned_repo = git.Repo.clone_from(repo_url, context.repo_dir, branch=branch)

            # If specific commit was provided, checkout that commit
            if commit:
                print(f"🔄 Checking out commit {commit}...")
                cloned_repo.git.checkout(commit)

            # Clean up non-essential files to save space and focus on relevant content
            self.cleanup_for_signature_analysis(context.repo_dir)

            # Mark clone as completed and save
            context.mark_clone_completed()

            return context

        except Exception as e:
            # Cleanup on failure
            if context.run_dir.exists():
                shutil.rmtree(context.run_dir)
            raise RuntimeError(f"Failed to clone repository {repo_url}: {e}")

    def cleanup_for_signature_analysis(self, repo_dir: Path) -> None:
        """Remove files not needed for signature analysis.

        Keeps: .py, .md, .mdx, .toml, .json, .yaml, .yml files
        Preserves: .git directory and its contents
        Removes: All other files and empty directories

        Args:
            repo_dir: Path to the cloned repository directory
        """
        # Extensions to keep for signature analysis
        allowed_extensions = {'.py', '.md', '.mdx', '.toml', '.json', '.yaml', '.yml', '.txt', '.rst'}
        preserved_dirs = {'.git'}

        # Walk the directory tree from bottom up to handle directory removal
        for root, dirs, files in os.walk(repo_dir, topdown=False):
            root_path = Path(root)

            # Skip .git directory and its contents
            if any(preserved_dir in root_path.parts for preserved_dir in preserved_dirs):
                continue

            # Remove files that don't match allowed extensions
            for file in files:
                file_path = root_path / file
                if file_path.suffix.lower() not in allowed_extensions:
                    try:
                        file_path.unlink()
                    except OSError:
                        # Skip files that can't be removed (permissions, etc.)
                        pass

            # Remove empty directories (but not the root repo directory)
            if root_path != repo_dir:
                try:
                    # Only remove if directory is empty
                    if not any(root_path.iterdir()):
                        root_path.rmdir()
                except OSError:
                    # Directory not empty or can't be removed
                    pass

    def find_python_files(self, context: RunContext) -> List[Path]:
        """Find all Python files in the cloned repository.

        Args:
            context: Run context with repository path

        Returns:
            List of Python file paths
        """
        python_files = []

        for root, _, files in os.walk(context.repo_dir):
            # Skip common non-source directories
            root_path = Path(root)
            relative_root = root_path.relative_to(context.repo_dir)

            # Skip test directories and virtual environments
            skip_dirs = {
                '__pycache__', '.pytest_cache', 'node_modules',
                '.venv', 'venv', '.env', 'env', 'build', 'dist',
                '.git', '.tox', '.mypy_cache'
            }

            if any(skip_dir in relative_root.parts for skip_dir in skip_dirs):
                continue

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    # Skip test files by convention
                    if not (file.startswith('test_') or file.endswith('_test.py') or 'test' in file_path.parts):
                        python_files.append(file_path)

        return python_files

    def find_markdown_files(self, context: RunContext, include_folders: Optional[List[str]] = None) -> Dict[str, Any]:
        """Find markdown files that likely contain API documentation.

        Args:
            context: Run context with repository path
            include_folders: Specific folders to include, ALREADY COMBINED with docs_path
                           (e.g., ['docs/src/python'] not just ['python'])

        Returns:
            Dict with:
                - files: List[Path] - Files to validate
                - total_found: int - All .md/.mdx in repository
                - in_include_folders: int - After path filtering, before API ref filtering
                - filtered_api_reference: int - Count of API reference pages filtered
                - api_reference_files: List[str] - Names of filtered API ref files
        """
        md_files = []
        api_reference_pages = []  # Track filtered API reference pages for reporting
        total_markdown_count = 0  # All .md/.mdx files in repo
        in_include_folders_count = 0  # After path filtering

        # Build full paths by combining docs_path with include_folders
        # Note: The pipeline should pass already-combined paths
        full_include_paths = []
        if include_folders:
            for folder in include_folders:
                # If docs_path is in context and folder is relative, combine them
                if context.docs_path and not folder.startswith(context.docs_path):
                    full_path = f"{context.docs_path}/{folder}".replace('//', '/')
                    full_include_paths.append(full_path)
                else:
                    full_include_paths.append(folder)

        for root, _, files in os.walk(context.repo_dir):
            # Prioritize documentation directories
            root_path = Path(root)
            relative_root = root_path.relative_to(context.repo_dir)

            # Skip .git directory
            if '.git' in relative_root.parts:
                continue

            # Check if in include folders (for filtering)
            in_include_folder = True
            if full_include_paths:
                # Check if current path is within any of the included folders
                path_str = str(relative_root)
                if path_str == ".":
                    # Root directory - check if any include_folders are at root level
                    in_include_folder = any(folder.count('/') == 0 for folder in full_include_paths)
                else:
                    # Check if current path starts with any of the included folders
                    in_include_folder = any(
                        path_str.startswith(folder) or path_str == folder
                        for folder in full_include_paths
                    )

            for file in files:
                if file.endswith(('.md', '.mdx')):
                    file_path = Path(root) / file

                    # Count all markdown files in entire repository
                    total_markdown_count += 1

                    # Skip if not in include folders (path filtering)
                    if full_include_paths and not in_include_folder:
                        continue

                    # Count files after path filtering (in include folders)
                    in_include_folders_count += 1

                    # Filter out common non-documentation files (changelog, etc.)
                    if self._should_exclude_document(file_path):
                        continue

                    # Filter out auto-generated API reference pages
                    if self._is_api_reference_page(file_path):
                        api_reference_pages.append(file_path)
                        continue

                    # This is a valid documentation file to analyze
                    md_files.append(file_path)

        # Report filtered API reference pages
        if api_reference_pages:
            print(f"\n📋 Filtered out {len(api_reference_pages)} API reference page(s):")
            for page in api_reference_pages:
                rel_path = page.relative_to(context.repo_dir)
                print(f"   - {rel_path}")

        # Return detailed metrics
        return {
            'files': md_files,
            'total_found': total_markdown_count,
            'in_include_folders': in_include_folders_count,
            'filtered_api_reference': len(api_reference_pages),
            'api_reference_files': [p.name for p in api_reference_pages]
        }

    def _should_exclude_document(self, file_path: Path) -> bool:
        """Check if a document should be excluded from analysis."""
        filename = file_path.name.lower()

        # Exclude common non-API documentation files
        exclude_patterns = [
            'changelog', 'history', 'news', 'authors', 'contributors',
            'license', 'copying', 'install', 'todo', 'issue', 'bug',
            'pull_request', 'pr_template', 'code_of_conduct'
        ]

        return any(pattern in filename for pattern in exclude_patterns)

    def _is_api_reference_page(self, file_path: Path) -> bool:
        """
        Detect if a markdown file is an auto-generated API reference page.

        API reference pages use MkDocs Material ':::' directives to auto-generate
        documentation from Python docstrings. These pages should be skipped because:
        - They extract tons of signatures (including internal methods like __init__)
        - They're auto-generated, not hand-written tutorials
        - They don't contain instructional content to validate

        Detection heuristics:
        1. Title contains "API Reference"
        2. Short file (<50 lines) with multiple ':::' directives (>= 3)
        3. High ratio of ':::' directives to content

        Args:
            file_path: Path to markdown file

        Returns:
            True if this is an API reference page (should skip)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.split('\n')
            line_count = len(lines)

            # Count MkDocs Material API doc directives
            directive_count = sum(1 for line in lines if line.strip().startswith(':::'))

            # Heuristic 1: Title explicitly says "API Reference"
            # Check first 300 chars (covers title and first paragraph)
            if 'API Reference' in content[:300]:
                return True

            # Heuristic 2: Short file with multiple directives
            # (typical pattern: navigation page that just lists classes)
            if line_count < 50 and directive_count >= 3:
                return True

            # Heuristic 3: High directive density (>20% of lines are directives)
            if line_count > 0 and (directive_count / line_count) > 0.2:
                return True

            return False

        except Exception:
            # If we can't read the file, don't exclude it
            return False

    def load_run_context(self, run_id: str) -> RunContext:
        """Load existing run context by ID."""
        return RunContext.load(run_id, self.base_data_dir)

    def cleanup_run(self, run_id: str) -> None:
        """Remove a run directory and all its contents."""
        run_dir = self.base_data_dir / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)

    def list_runs(self) -> List[str]:
        """List all available run IDs."""
        runs = []
        for item in self.base_data_dir.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                runs.append(item.name)
        return runs