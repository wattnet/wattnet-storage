# wattnet Metrics Storage Backend

## Docker Compose Configuration Documentation

This documentation provides an overview of the services defined in the `docker-compose.yml` file, including VictoriaMetrics, Grafana. These services are interconnected to provide monitoring and storage solutions.

### Services Overview

#### 1. **VictoriaMetrics**

VictoriaMetrics is a fast, cost-effective, and scalable time-series database. It is designed to handle large amounts of metrics data efficiently.

##### Configuration:

-   **Image**: `victoriametrics/victoria-metrics:latest`
-   **Container Name**: `victoriametrics`

##### Port:

-   9090

---

#### 2. **Grafana**

Grafana is an open-source analytics and monitoring platform that integrates with various data sources, including VictoriaMetrics (Prometheus Type Datasource).

##### Configuration:

-   **Image**: `grafana/grafana:latest`
-   **Container Name**: `grafana`
-   **Volumes**:
    -   `grafana_data:/var/lib/grafana:rw`: Persists Grafana data.
    -   `./config/grafana-datasources.yaml:/etc/grafana/provisioning/datasources/provisioning-datasources.yaml:ro`: Mounts Grafana data source configuration.
    -   `./config/grafana-dashboards.yaml:/etc/grafana/provisioning/dashboards/provisioning-dashboards.yaml:ro`: Mounts the dashboard configuration.
    -   `./config/dashboards:/var/lib/grafana/dashboards:ro`: Mounts custom dashboards.
-   **Environment**:
    -   `GF_SECURITY_ADMIN_PASSWORD=admin`: Sets the admin password for Grafana.
-   **Network Mode**: `host` (Port: 3000)
-   **Depends On**:
    -   `mimir`: Grafana depends on Mimir for metrics storage.

##### Port:

-   3000

---

## Volumes

The following volumes are defined to persist data across container restarts:

-   `victoria_data`: Persists VictoriaMetrics data.
-   `grafana_data`: Persists Grafana data.

---

## Network Configuration

-   All services use `network_mode: host` to bind the services to the host's network stack. This allows the services to use the same IP as the host machine, simplifying access to the exposed ports.

---

## Dependencies

-   **Grafana** depends on **VictoriaMetrics** for querying and visualizing metrics data.

These dependencies ensure that all services work together seamlessly, providing a complete monitoring and storage solution.

---

## Ports Summary

| Service         | Port |
| --------------- | ---- |
| VictoriaMetrics | 8428 |
| Grafana UI      | 3000 |

---

## Services Configuration

### VictoriaMetrics

VictoriaMetrics is configured to run in a single-node mode. Data persistance is handled through the `victoria_data` volume, which is mounted to `/storage` in the container. Metrics retention is set to 100 year.

### Grafana

Grafana mimir configuration is provided in the `grafana-datasources.yaml` file. The configuration specifies the data source for Grafana to connect to VictoriaMetrics.

Also, the dashboard configuration is provided in the `grafana-dashboards.yaml` file. The configuration specifies the location of the custom dashboards to be loaded by Grafana.

---

## Dashboards
