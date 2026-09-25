#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prometheus exporter for the metrics missing from the standard exporters."""

import logging
import os
import ssl
import xml.etree.ElementTree as ET

import libvirt
import psutil
from prometheus_client import REGISTRY, start_http_server
from prometheus_client.core import GaugeMetricFamily

LOG = logging.getLogger("seapath_exporter")

DEFAULT_LIBVIRT_URI = "qemu:///system"
DEFAULT_QEMU_PID_DIR = "/var/run/libvirt/qemu"
DEFAULT_LISTEN_ADDRESS = "0.0.0.0"
DEFAULT_LISTEN_PORT = "9184"

TLS_VERSIONS = {
    "1.2": ssl.TLSVersion.TLSv1_2,
    "1.3": ssl.TLSVersion.TLSv1_3,
}


def env(name, default=None):
    """Return an environment variable, treating an empty value as unset."""
    return os.environ.get(name, "").strip() or default


class VhostCPUCollector:
    """Expose the CPU time of the vhost threads backing each libvirt domain.

    libvirt does not account for those kernel threads in the domain CPU
    statistics, so they are read from the host process table instead.

    Metrics are rebuilt on every scrape, so the series of a domain that is no
    longer running simply stops being exposed.
    """

    def __init__(self, uri, qemu_pid_dir):
        self._uri = uri
        self._qemu_pid_dir = qemu_pid_dir

    def collect(self):
        vhost_cpu = GaugeMetricFamily(
            "virsh_vhost_cpu_time_seconds",
            "CPU time (user+system) of vhost threads on the host related to "
            "this domain, in seconds",
            labels=["domain", "thread"],
        )
        libvirt_up = GaugeMetricFamily(
            "virsh_exporter_libvirt_up",
            "Whether the last scrape managed to query libvirt",
        )

        try:
            domains = self._domain_pids()
        except libvirt.libvirtError as error:
            # Without this the scrape would silently succeed with no series at
            # all, which is indistinguishable from a host running no VM.
            LOG.warning("cannot query libvirt on %s: %s", self._uri, error)
            libvirt_up.add_metric([], 0)
            yield libvirt_up
            yield vhost_cpu
            return

        libvirt_up.add_metric([], 1)
        for name, pid in domains:
            for thread, cpu_seconds in self._vhost_threads(pid):
                vhost_cpu.add_metric([name, thread], cpu_seconds)

        yield libvirt_up
        yield vhost_cpu

    def _domain_pids(self):
        """Return the (domain name, QEMU pid) pairs of the running domains."""
        conn = libvirt.open(self._uri)
        try:
            domains = []
            for domain_id in conn.listDomainsID():
                try:
                    domain = conn.lookupByID(domain_id)
                    name = domain.name()
                except libvirt.libvirtError as error:
                    LOG.debug("domain %s vanished mid-scrape: %s", domain_id, error)
                    continue
                pid = self._qemu_pid(domain, name)
                if pid is None:
                    LOG.debug("no QEMU pid found for domain %s", name)
                    continue
                domains.append((name, pid))
            return domains
        finally:
            conn.close()

    def _qemu_pid(self, domain, name):
        try:
            process = ET.fromstring(domain.XMLDesc()).find("./process")
        except (libvirt.libvirtError, ET.ParseError) as error:
            LOG.debug("cannot read the XML of domain %s: %s", name, error)
            process = None
        if process is not None and "pid" in process.attrib:
            return int(process.attrib["pid"])

        pidfile = os.path.join(self._qemu_pid_dir, f"{name}.pid")
        try:
            with open(pidfile, "rt") as handle:
                return int(handle.read().strip())
        except (OSError, ValueError) as error:
            LOG.debug("cannot read %s: %s", pidfile, error)
            return None

    def _vhost_threads(self, pid):
        try:
            threads = psutil.Process(pid).threads()
        except psutil.Error as error:
            LOG.debug("cannot inspect pid %s: %s", pid, error)
            return
        for thread in threads:
            comm = self._thread_comm(pid, thread.id)
            if "vhost" not in comm:
                continue
            yield f"{comm}-{thread.id}", float(thread.user_time + thread.system_time)

    @staticmethod
    def _thread_comm(pid, tid):
        try:
            with open(f"/proc/{pid}/task/{tid}/comm", "rt") as handle:
                return handle.read().strip()
        except OSError:
            # Best effort: the thread may have exited since we listed it.
            return ""


def tls_options():
    """Build the TLS keyword arguments of start_http_server from the environment."""
    certfile = env("TLS_CERT_FILE")
    keyfile = env("TLS_KEY_FILE")
    if not certfile and not keyfile:
        return {}
    if not certfile or not keyfile:
        raise SystemExit("TLS_CERT_FILE and TLS_KEY_FILE must be set together")

    minimum = env("TLS_MIN_VERSION", "1.3")
    if minimum not in TLS_VERSIONS:
        raise SystemExit(
            "TLS_MIN_VERSION must be one of " + ", ".join(sorted(TLS_VERSIONS))
        )

    options = {
        "certfile": certfile,
        "keyfile": keyfile,
        "tls_min_version": TLS_VERSIONS[minimum],
    }

    client_ca = env("TLS_CLIENT_CA_FILE")
    if client_ca:
        options["client_cafile"] = client_ca
        options["client_auth_required"] = True
    return options


def main():
    logging.basicConfig(
        level=env("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # libvirt writes its own copy of every error on stderr, on top of the
    # exceptions it raises and that we already log ourselves.
    libvirt.registerErrorHandler(lambda ctx, error: None, None)

    address = env("LISTEN_ADDRESS", DEFAULT_LISTEN_ADDRESS)
    port = int(env("LISTEN_PORT", DEFAULT_LISTEN_PORT))
    options = tls_options()

    REGISTRY.register(
        VhostCPUCollector(
            env("LIBVIRT_URI", DEFAULT_LIBVIRT_URI),
            env("QEMU_PID_DIR", DEFAULT_QEMU_PID_DIR),
        )
    )

    _, thread = start_http_server(port, address, **options)
    LOG.info(
        "serving metrics on %s://%s:%s/metrics%s",
        "https" if options else "http",
        address,
        port,
        " (client certificate required)" if options.get("client_auth_required") else "",
    )
    thread.join()


if __name__ == "__main__":
    main()
