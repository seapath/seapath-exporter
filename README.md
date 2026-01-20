# insatomcat-exporter

[![Docker Hub](https://img.shields.io/docker/v/insatomcat/insatomcat-exporter?sort=semver)](https://hub.docker.com/r/insatomcat/insatomcat-exporter)
[![Docker Pulls](https://img.shields.io/docker/pulls/insatomcat/insatomcat-exporter)](https://hub.docker.com/r/insatomcat/insatomcat-exporter)

A comprehensive Prometheus exporter for monitoring various infrastructure components that lack proper metrics exposure in existing exporters.

## 🎯 Purpose

This exporter fills the gaps left by standard exporters (libvirt-exporter, ceph-exporter, etc.) by providing additional metrics that are needed for production monitoring but aren't available elsewhere.

Rather than creating multiple small exporters for each missing metric, this project consolidates all the "missing pieces" needed for complete infrastructure monitoring.

## 📊 Current Metrics

### Vhost Thread Monitoring (libvirt/KVM)

Monitors CPU usage of vhost threads for QEMU/KVM virtual machines.

**Metric:**
```
virsh_vhost_cpu_time_seconds{domain="vm-name", thread="vhost-12345"} 123.45
```

- **Labels:**
  - `domain`: VM domain name
  - `thread`: vhost thread identifier
- **Type:** Gauge
- **Unit:** Seconds (cumulative CPU time)

## 🚀 Planned Metrics

- Additional libvirt metrics not covered by prometheus-libvirt-exporter
- Ceph metrics missing from ceph-exporter
- Pacemaker cluster metrics
- Debian RT (Real-Time) kernel metrics
- Other infrastructure metrics as needed

This list is actively developed based on real production monitoring needs.

## 📦 Installation

### Docker Hub

```bash
docker pull insatomcat/insatomcat-exporter:latest
```

### Quick Start with Podman

```bash
podman run -d \
  --name insatomcat-exporter \
  --restart unless-stopped \
  -p 9184:9184 \
  -v /var/run/libvirt/libvirt-sock-ro:/var/run/libvirt/libvirt-sock-ro:ro \
  -v /var/run/libvirt/qemu:/var/run/libvirt/qemu:ro \
  --pid=host \
  docker.io/insatomcat/insatomcat-exporter:latest
```

### Quick Start with Docker

```bash
docker run -d \
  --name insatomcat-exporter \
  --restart unless-stopped \
  -p 9184:9184 \
  -v /var/run/libvirt/libvirt-sock-ro:/var/run/libvirt/libvirt-sock-ro:ro \
  -v /var/run/libvirt/qemu:/var/run/libvirt/qemu:ro \
  --pid=host \
  insatomcat/insatomcat-exporter:latest
```

### Systemd with Podman Quadlet (Recommended)

Create `/etc/containers/systemd/insatomcat-exporter.container`:

```ini
[Unit]
Description=Prometheus insatomcat Exporter
After=network-online.target libvirtd.service
Wants=network-online.target

[Container]
Image=docker.io/insatomcat/insatomcat-exporter:latest
PublishPort=9184:9184
Volume=/var/run/libvirt/libvirt-sock-ro:/var/run/libvirt/libvirt-sock-ro:ro
Volume=/var/run/libvirt/qemu:/var/run/libvirt/qemu:ro
PodmanArgs=--pid=host
SecurityLabelDisable=true

[Service]
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now insatomcat-exporter.service
```

### docker-compose

```yaml
version: '3.8'

services:
  insatomcat-exporter:
    image: insatomcat/insatomcat-exporter:latest
    container_name: insatomcat-exporter
    restart: unless-stopped
    ports:
      - "9184:9184"
    volumes:
      - /var/run/libvirt/libvirt-sock:/var/run/libvirt/libvirt-sock:ro
      - /var/run/libvirt/qemu:/var/run/libvirt/qemu:ro
    pid: host
```

## 🔧 Configuration

### Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'insatomcat-exporter'
    static_configs:
      - targets: ['localhost:9184']
    scrape_interval: 30s
```

### Environment Variables

Currently no environment variables are needed. Configuration will be added as new metrics are implemented.

## ✅ Verification

Check that the exporter is running:

```bash
curl http://localhost:9184/metrics
```

Expected output (when VMs are running):

```
# HELP virsh_vhost_cpu_time_seconds CPU time (user+system) of vhost threads on the host related to this domain, in seconds
# TYPE virsh_vhost_cpu_time_seconds gauge
virsh_vhost_cpu_time_seconds{domain="vm1",thread="vhost-12345"} 123.45
virsh_vhost_cpu_time_seconds{domain="vm2",thread="vhost-67890"} 67.89
```

## 🏗️ Building from Source

### Prerequisites

- Python 3.11+
- libvirt development libraries
- Podman or Docker

### Build the Container

```bash
# Clone the repository
git clone https://github.com/insatomcat/insatomcat-exporter.git
cd insatomcat-exporter

# Build with Podman
podman build -t insatomcat/insatomcat-exporter:latest .

# Or with Docker
docker build -t insatomcat/insatomcat-exporter:latest .
```

### Run Locally (without container)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the exporter
python insatomcat_exporter.py
```

## 📋 Requirements

### Current Requirements (vhost metrics)

- Host with libvirt/QEMU installed
- Access to libvirt socket (`/var/run/libvirt/libvirt-sock-ro`)
- Access to QEMU PID files (`/var/run/libvirt/qemu`)
- Host PID namespace access (`--pid=host`)

### System Dependencies

- `libvirt-dev` / `libvirt-devel`
- `python3-dev` / `python3-devel`
- `gcc`
- `pkg-config`

## 🐛 Troubleshooting

### No metrics appearing

1. Check that VMs are running:
   ```bash
   virsh list
   ```

2. Check exporter logs:
   ```bash
   # Podman
   podman logs insatomcat-exporter
   
   # Systemd
   sudo journalctl -u insatomcat-exporter.service -f
   ```

3. Verify the container can access libvirt:
   ```bash
   podman exec insatomcat-exporter python3 -c "import libvirt; print(libvirt.open('qemu:///system').listDomainsID())"
   ```

### Permission denied errors

Ensure the container has:
- Access to libvirt socket (check file permissions)
- Host PID namespace (`--pid=host`)
- SELinux labels if applicable (`SecurityLabelDisable=true` in Quadlet)

## 📈 Use Cases

**Current:**
- Monitor CPU usage of vhost threads for KVM virtual machines
- Track performance of virtio-net network interfaces
- Identify VMs with high vhost CPU consumption
- Create alerts when vhost thread CPU usage exceeds thresholds

**Upcoming:**
- Monitor specific libvirt domain states and performance metrics
- Track Ceph cluster health metrics not exposed by standard exporters
- Monitor Pacemaker cluster resource states
- Track Debian RT kernel performance metrics

## 🤝 Contributing

Contributions are welcome! If you need a specific metric that's missing from standard exporters:

1. Open an issue describing the metric and use case
2. Submit a pull request with the implementation
3. Update documentation and tests

### Development Guidelines

- Follow existing code structure
- Add metrics that complement (not duplicate) existing exporters
- Include clear documentation and examples
- Test in a real environment before submitting

## 📜 License

GPL v3

## 🔗 Links

- [Docker Hub](https://hub.docker.com/r/insatomcat/insatomcat-exporter)
- [Report Issues](https://github.com/insatomcat/insatomcat-exporter/issues)

## 📞 Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check existing documentation
- Review closed issues for solutions

## 🙏 Acknowledgments

This exporter complements existing excellent exporters:
- [prometheus-libvirt-exporter](https://github.com/inovex/prometheus-libvirt-exporter)
- [ceph-exporter](https://docs.ceph.com/en/latest/mgr/prometheus/)
- Other Prometheus exporters in the ecosystem

---

**Philosophy:** One exporter for all the missing pieces, not one exporter per missing piece.
