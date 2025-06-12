# Use official Redis Alpine image
FROM redis:7.2-alpine

# Set environment variables with defaults (override in compose/.env for prod)
ENV REDIS_PASSWORD=redis_password
ENV REDIS_PORT=6379
ENV REDIS_DATABASES=16

# Create data directory
RUN mkdir -p /data

# Optional: Copy redis.conf for SSL/TLS support (if present)
# COPY redis.conf /usr/local/etc/redis/redis.conf

# Expose standard and optional TLS ports
EXPOSE ${REDIS_PORT}
EXPOSE ${REDIS_TLS_PORT:-6380}

# Set health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD redis-cli ping || exit 1

# Start Redis with production-ready settings
CMD ["redis-server", \
    "--appendonly", "yes", \
    "--requirepass", "${REDIS_PASSWORD}", \
    "--maxmemory", "256mb", \
    "--maxmemory-policy", "allkeys-lru", \
    "--port", "${REDIS_PORT}", \
    "--databases", "${REDIS_DATABASES}"]

# Notes:
# - SSL/TLS is not enabled by default. To enable, mount your certs to /certs and use the provided redis.conf.
# - Uncomment COPY redis.conf and set CMD to use the config as needed.
# - See https://redis.io/docs/manual/security/encryption/ for advanced SSL usage and tuning.
