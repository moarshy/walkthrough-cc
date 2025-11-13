FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    git \
    curl \
    wget \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv - fast Python package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# Update npm to latest
RUN npm install -g npm@latest

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
    anthropic>=0.30.0

# Setup workspace directories
RUN mkdir -p /workspace/repo \
    && mkdir -p /workspace/docs \
    && mkdir -p /workspace/logs \
    && mkdir -p /agent_wrapper

# Copy agent wrapper
COPY src/agent_wrapper.py /agent_wrapper/run_agent.py

# Copy hooks for reuse
RUN mkdir -p /agent_wrapper/hooks
# Note: If needed, copy hooks from example-codes here

# Set working directory
WORKDIR /workspace/repo

# Set environment variables
ENV NODE_PATH=/usr/local/lib/node_modules
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:${PATH}"

# Default command (will be overridden)
CMD ["/bin/bash"]
