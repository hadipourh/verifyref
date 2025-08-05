# Unified Dockerfile for VerifyRef
# Using GROBID's official Docker image as baseline

FROM lfoppiano/grobid:0.8.2

# Switch to root user to install Python and dependencies
USER root

# Install Python and other dependencies
RUN apt-get update && \
    apt-get -y --no-install-recommends install \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Create symlink for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set up VerifyRef in /app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy VerifyRef application
COPY . .

# Create startup script directly in Dockerfile
RUN echo '#!/bin/bash\n\
set -e\n\
echo "🚀 Starting VerifyRef container..."\n\
echo "📚 GROBID service is starting in the background..."\n\
/opt/grobid/grobid-service/bin/grobid-service > /dev/null 2>&1 &\n\
echo "⏳ Waiting for GROBID to start..."\n\
for i in {1..30}; do\n\
    if curl -s http://localhost:8070/api/isalive | grep -q "true"; then\n\
        echo "✅ GROBID is ready!"\n\
        break\n\
    fi\n\
    if [ $i -eq 30 ]; then\n\
        echo "❌ GROBID failed to start within 30 seconds"\n\
        exit 1\n\
    fi\n\
    sleep 1\n\
    echo -n "."\n\
done\n\
echo ""\n\
echo "🔧 VerifyRef is ready to use!"\n\
echo "📁 Your files are mounted at: /app/workspace"\n\
echo "💾 Quick commands: verifyref --cite \"query\" or verifyref paper.pdf"\n\
echo ""\n\
if [ $# -gt 0 ]; then\n\
    exec "$@"\n\
else\n\
    cd /app/workspace\n\
    exec /bin/bash\n\
fi' > /usr/local/bin/docker-entrypoint.sh && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# Create directories for input/output
RUN mkdir -p /app/input /app/output

# Create a convenient verifyref command alias
RUN echo '#!/bin/bash\npython /app/verifyref.py "$@"' > /usr/local/bin/verifyref && \
    chmod +x /usr/local/bin/verifyref

# Set environment variables
ENV GROBID_URL=http://localhost:8070
ENV PYTHONPATH=/app

# Return to GROBID's working directory to maintain compatibility
WORKDIR /opt/grobid

# Expose port for GROBID service
EXPOSE 8070

# Use custom entrypoint that starts GROBID automatically
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command: start interactive bash
CMD ["/bin/bash"]
