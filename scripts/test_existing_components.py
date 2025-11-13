#!/usr/bin/env python3
"""
Test script to verify existing components work:
1. RepositoryManager - Clone a repo
2. WalkthroughGenerator - Generate a walkthrough from a doc

This validates that we can reuse the example-codes infrastructure.
"""

import sys
import asyncio
from pathlib import Path

# Add example-codes to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "example-codes"))

from repository.manager import RepositoryManager
from walkthrough_generate_agent import WalkthroughGenerateAgent


async def test_repository_manager():
    """Test cloning a small repository."""
    print("\n" + "="*80)
    print("TEST 1: Repository Manager")
    print("="*80 + "\n")

    # Use a small, fast repo for testing
    test_repo_url = "https://github.com/vercel/next.js"
    test_branch = "canary"
    test_library = "Next.js"
    test_version = "14.0"

    # Setup test data directory
    test_data_dir = project_root / "test_data"
    test_data_dir.mkdir(exist_ok=True)

    print(f"📦 Testing RepositoryManager...")
    print(f"   Repo: {test_repo_url}")
    print(f"   Branch: {test_branch}")
    print(f"   Library: {test_library} v{test_version}\n")

    try:
        # Initialize manager
        repo_manager = RepositoryManager(base_data_dir=test_data_dir)

        # Clone repository (shallow clone for speed)
        print("🔄 Cloning repository...")
        context = repo_manager.clone_repository(
            repo_url=test_repo_url,
            branch=test_branch,
            library_name=test_library,
            library_version=test_version,
            docs_path="docs",
            include_folders=["01-getting-started"]
        )

        print(f"✅ Repository cloned successfully!")
        print(f"   Run ID: {context.run_id}")
        print(f"   Repo path: {context.repo_dir}")
        print(f"   Status: {context.status}")

        # Find markdown files
        print("\n📄 Finding markdown files...")
        md_result = repo_manager.find_markdown_files(
            context,
            include_folders=["docs/01-getting-started"]
        )

        print(f"✅ Found {len(md_result['files'])} documentation files")
        print(f"   Total markdown in repo: {md_result['total_found']}")
        print(f"   In include folders: {md_result['in_include_folders']}")
        print(f"   Filtered API references: {md_result['filtered_api_reference']}")

        if md_result['files']:
            print("\n   Sample files:")
            for i, f in enumerate(md_result['files'][:3], 1):
                rel_path = f.relative_to(context.repo_dir)
                print(f"   {i}. {rel_path}")

        return context, md_result['files']

    except Exception as e:
        print(f"❌ Repository Manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return None, []


async def test_walkthrough_generator(repo_context, doc_files):
    """Test generating a walkthrough from a doc."""
    print("\n" + "="*80)
    print("TEST 2: Walkthrough Generator")
    print("="*80 + "\n")

    if not doc_files:
        print("⚠️  No docs found, skipping walkthrough generation test")
        return None

    # Pick the first doc
    doc_path = doc_files[0]
    rel_path = doc_path.relative_to(repo_context.repo_dir)

    print(f"📝 Testing WalkthroughGenerator...")
    print(f"   Doc: {rel_path}")
    print(f"   Library: {repo_context.library_name} v{repo_context.library_version}\n")

    try:
        # Setup output directory
        output_dir = project_root / "test_data" / "walkthroughs"
        output_dir.mkdir(exist_ok=True, parents=True)

        # Initialize generator
        generator = WalkthroughGenerateAgent(
            output_folder=output_dir,
            library_name=repo_context.library_name,
            library_version=repo_context.library_version
        )

        print("🔄 Generating walkthrough (this may take 1-2 minutes)...")
        walkthrough = await generator.generate_walkthrough(
            doc_path=doc_path,
            walkthrough_id=f"test_{doc_path.stem}"
        )

        print(f"\n✅ Walkthrough generated successfully!")
        print(f"   Title: {walkthrough.walkthrough.title}")
        print(f"   Steps: {len(walkthrough.steps)}")
        print(f"   Duration: ~{walkthrough.walkthrough.estimatedDurationMinutes} minutes")
        print(f"   Tags: {', '.join(walkthrough.walkthrough.tags)}")

        if walkthrough.steps:
            print("\n   Sample steps:")
            for i, step in enumerate(walkthrough.steps[:3], 1):
                print(f"   {i}. {step.title}")
                ops = step.contentFields.operationsForAgent
                if ops:
                    first_line = ops.split('\n')[0][:60]
                    print(f"      Operations: {first_line}...")

        return walkthrough

    except Exception as e:
        print(f"❌ Walkthrough Generator test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run all tests."""
    print("\n🧪 Testing Existing Components")
    print("="*80)
    print("\nThis will:")
    print("1. Clone a test repository (Next.js)")
    print("2. Find documentation files")
    print("3. Generate a walkthrough from one doc")
    print("\nNote: This requires ANTHROPIC_API_KEY to be set!\n")

    # Check API key
    import os
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY not set!")
        print("   Export it first: export ANTHROPIC_API_KEY=your-key-here")
        return 1

    # Test 1: Repository Manager
    repo_context, doc_files = await test_repository_manager()

    if not repo_context:
        print("\n❌ Repository Manager test failed - stopping here")
        return 1

    # Test 2: Walkthrough Generator
    walkthrough = await test_walkthrough_generator(repo_context, doc_files)

    if not walkthrough:
        print("\n⚠️  Walkthrough Generator test had issues")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ Repository Manager: Working")
    print(f"{'✅' if walkthrough else '⚠️ '} Walkthrough Generator: {'Working' if walkthrough else 'Had issues'}")

    print("\n📁 Test data saved to: test_data/")
    print("   - Repository: test_data/{run_id}/repository/")
    print("   - Walkthroughs: test_data/walkthroughs/")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
