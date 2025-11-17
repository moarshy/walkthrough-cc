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
    lsof \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (required for latest npm and Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    claude-agent-sdk \
    python-dotenv \
    pydantic \
    pyyaml

# Copy cc_experiment_runner package
COPY src/cc_experiment_runner /app/cc_experiment_runner

# Copy in-container agent script
COPY scripts/run_agent_in_container.py /app/run_agent_in_container.py

# Set working directory
WORKDIR /workspace/repo

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command (will be overridden)
CMD ["/bin/bash"]
