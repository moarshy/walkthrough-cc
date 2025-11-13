FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (required for latest npm and Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv - fast Python package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create virtual environment with uv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV VIRTUAL_ENV="/opt/venv"

# Install Python dependencies with uv
RUN uv pip install --no-cache \
    pydantic>=2.0.0 \
    python-dotenv>=1.0.0 \
    anthropic>=0.30.0 \
    claude-agent-sdk

# Setup workspace directories
RUN mkdir -p /workspace/repo \
    && mkdir -p /workspace/docs \
    && mkdir -p /workspace/logs \
    && mkdir -p /agent_wrapper

# Copy agent wrapper and hooks
COPY src/agent_wrapper.py /agent_wrapper/run_agent.py
COPY example-codes/hooks /agent_wrapper/hooks
COPY example-codes/schemas.py /agent_wrapper/schemas.py

# Set working directory
WORKDIR /workspace/repo

# Set environment variables
ENV NODE_PATH=/usr/local/lib/node_modules
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:${PATH}"

# Default command (will be overridden)
CMD ["/bin/bash"]
