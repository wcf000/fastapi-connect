docker-compose -f app/core/prometheus/docker/docker-compose.prometheus.yml -f app/core/telemetry/docker/docker-compose.otel.local.yml -f app/core/grafana/docker/docker-compose.grafana.yml -f app/core/valkey_core/docker/docker-compose.prod.yml -f app/core/pulsar/docker/docker-compose.pulsar.yml down
# Remove volumes only if needed - be careful with this in production!
docker volume rm docker_bookie-data docker_pulsar-zookeeper-data 2>/dev/null || true
docker network remove app-network
docker network create app-network
docker-compose -f app/core/prometheus/docker/docker-compose.prometheus.yml -f app/core/telemetry/docker/docker-compose.otel.local.yml -f app/core/grafana/docker/docker-compose.grafana.yml -f app/core/valkey_core/docker/docker-compose.prod.yml -f app/core/pulsar/docker/docker-compose.pulsar.yml up -d