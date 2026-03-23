FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg nodejs npm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dietmcp
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir ".[dev]" tiktoken

# Install MCP filesystem server
RUN npm install -g @modelcontextprotocol/server-filesystem

# Copy benchmark script and config
COPY benchmark/ benchmark/

# Create test data
RUN mkdir -p /tmp/testdata && \
    echo "Hello world" > /tmp/testdata/small.txt && \
    python -c "print('x' * 2000)" > /tmp/testdata/medium.txt && \
    python -c "print('x' * 50000)" > /tmp/testdata/large.txt && \
    python -c "import os; [open(f'/tmp/testdata/file_{i:03d}.txt','w').write(f'content {i}') for i in range(500)]"

# Create config
RUN mkdir -p /root/.config/dietmcp && \
    echo '{"mcpServers":{"filesystem":{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/tmp/testdata"]}},"defaults":{"cacheTtlSeconds":3600,"outputFormat":"summary","maxResponseSize":50000}}' > /root/.config/dietmcp/servers.json

CMD ["python", "benchmark/run_benchmark.py"]
