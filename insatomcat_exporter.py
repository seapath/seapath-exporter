from prometheus_client import start_http_server, Gauge, REGISTRY, generate_latest
from http.server import BaseHTTPRequestHandler, HTTPServer
import libvirt
import psutil
import xml.etree.ElementTree as ET

vhost_cpu_time_gauge = Gauge(
    'virsh_vhost_cpu_time_seconds',
    'CPU time (user+system) of vhost threads on the host related to this domain, in seconds',
    ['domain', 'thread']
)

KB_TO_BYTES = 1024

def get_qemu_pid(domain):
    # domain.getMetadata or domain.XMLDesc
    xml = domain.XMLDesc()
    tree = ET.fromstring(xml)
    # The PID is under <domain><process id='PID'/>
    pid = None
    proc = tree.find("./process")
    if proc is not None and 'pid' in proc.attrib:
        pid = int(proc.attrib['pid'])
    else:
        # fallback: read from /var/run/libvirt/qemu/<name>.pid
        import os
        pidfile = f"/var/run/libvirt/qemu/{domain.name()}.pid"
        if os.path.exists(pidfile):
            with open(pidfile) as f:
                pid = int(f.read().strip())
    return pid

def collect_qemu_stats(domain):
    try:
        pid = get_qemu_pid(domain)
        if not pid:
            return
        proc = psutil.Process(pid)
        try:
            for thr in proc.threads():  # thr.id, thr.user_time, thr.system_time
                tid = thr.id
                thr_cpu_s = float(thr.user_time + thr.system_time)
                comm = ''
                try:
                    with open(f"/proc/{pid}/task/{tid}/comm", 'rt') as cf:
                        comm = cf.read().strip()
                except Exception:
                    # best-effort; continue without name if we can't read it
                    comm = ''
                if 'vhost' in comm:
                    vhost_cpu_time_gauge.labels(domain=domain.name(), thread=comm+'-'+str(tid) or str(tid)).set(thr_cpu_s)
        except Exception:
            # best-effort, ignore thread-inspect failures
            pass

    except Exception as e:
        print(f"Error collecting qemu stats for {domain.name()}: {e}")

def remove_stale_gauge_series(current_domains):
    """Remove label sets that no longer exist."""
    try:
        all_gauges = [v for v in globals().values() if isinstance(v, Gauge)]
        for gauge in all_gauges:
            if not gauge._labelnames:  # skip unlabeled gauges
                continue
            for label_values in list(gauge._metrics.keys()):
                labels_dict = dict(zip(gauge._labelnames, label_values))
                if 'domain' in labels_dict and labels_dict['domain'] not in current_domains:
                    # must pass positional args in labelname order
                    values_in_order = tuple(labels_dict[name] for name in gauge._labelnames)
                    gauge.remove(*values_in_order)
    except Exception as e:
        print(f"Error removing stale gauges: {e}")

def collect_all_stats():
    """Collect stats for all running domains on-demand."""
    try:
        conn = libvirt.open('qemu:///system')
        if conn is None:
            print("Failed to open connection to hypervisor")
            return
        domain_ids = conn.listDomainsID()  # running domains only
        current_domains = []
        for dom_id in domain_ids:
            domain = conn.lookupByID(dom_id)
            current_domains.append(domain.name())
            collect_qemu_stats(domain)
        remove_stale_gauge_series(current_domains)
        conn.close()
    except Exception as e:
        print(f"Error listing domains: {e}")

# --- HTTP handler ---
class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            collect_all_stats()
            self.send_response(200)
            self.send_header("Content-type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(generate_latest(REGISTRY))

# --- Main server ---
if __name__ == '__main__':
    server_address = ('', 9184)
    httpd = HTTPServer(server_address, MetricsHandler)
    print("virsh exporter running on :9184/metrics")
    httpd.serve_forever()
