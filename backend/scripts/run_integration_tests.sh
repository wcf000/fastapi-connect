#!/bin/bash
set -e

# Wait for Pulsar broker to be fully ready
echo "Waiting for Pulsar broker to be ready..."
max_retries=30
retry_count=0
while ! curl -s http://broker:8080/admin/v2/brokers/health > /dev/null 2>&1; do
  retry_count=$((retry_count+1))
  if [ $retry_count -gt $max_retries ]; then
    echo "Error: Pulsar broker is not ready after $max_retries attempts. Exiting."
    exit 1
  fi
  echo "Waiting for Pulsar broker to be ready... (Attempt $retry_count/$max_retries)"
  sleep 2
done

echo "Pulsar broker is ready! Running tests..."

# Run the Pulsar integration tests
python -m pytest tests/pulsar/_tests -v

# Return the test exit code
exit $?
