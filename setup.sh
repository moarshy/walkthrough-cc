#!/bin/bash
# Quick setup script for vanilla-cc-walkthrough-cc experiment

set -e

echo "🚀 Setting up vanilla-cc-walkthrough-cc experiment"
echo "=================================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "✅ uv already installed"
fi

# Sync dependencies
echo ""
echo "📦 Installing Python dependencies with uv..."
uv sync

# Check Docker
echo ""
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
else
    echo "✅ Docker is installed"
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker."
    exit 1
else
    echo "✅ Docker is running"
fi

# Build Docker image
echo ""
echo "🐳 Building Docker image..."
docker build -t cc-experiment:latest .

# Check API key
echo ""
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set"
    echo "   Export it: export ANTHROPIC_API_KEY=your-key-here"
else
    echo "✅ ANTHROPIC_API_KEY is set"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Run experiment with:"
echo "  python run_experiment.py"
echo ""
echo "Or run specific task:"
echo "  python run_experiment.py --task-ids nextjs-getting-started"
