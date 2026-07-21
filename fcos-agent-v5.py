#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from xml.sax.saxutils import escape


# ============================================================
# LINUX WAYS FCOS-AGENT V5
# Intelligent Fedora CoreOS Deployment Agent
# Plan,Design and Deployed by Atif Ahmed - Platform Architect
# ============================================================


VERSION = "5.0.0"


# ============================================================
# CONFIGURATION
# ============================================================


@dataclass
class Config:

    vm_name: str = "fcos-agent-v5"

    libvirt_uri: str = "qemu:///system"

    memory_mib: int = 8192

    vcpus: int = 4

    ssh_user: str = "core"

    work_dir: Path = (
        Path.home()
        / ".linuxways"
        / "fcos-agent-v5"
    )

    image_dir: Path = Path(
        "/var/lib/libvirt/images"
    )

    image_path: Path | None = None

    ignition_path: Path | None = None

    state_path: Path | None = None

    replace: bool = False

    verbose: bool = False

    ip_timeout: int = 180

    ssh_timeout: int = 300


# ============================================================
# LOGGER
# ============================================================


class Logger:

    def __init__(self, verbose=False):

        self.verbose = verbose

    def _log(self, level, message):

        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        print(
            f"[{timestamp}] "
            f"[{level}] "
            f"{message}"
        )

    def info(self, message):

        self._log(
            "INFO",
            message
        )

    def success(self, message):

        self._log(
            "+",
            message
        )

    def warning(self, message):

        self._log(
            "!",
            message
        )

    def error(self, message):

        self._log(
            "ERROR",
            message
        )

    def debug(self, message):

        if self.verbose:

            self._log(
                "DEBUG",
                message
            )


# ============================================================
# COMMAND EXECUTOR
# ============================================================


class CommandRunner:

    def __init__(self, logger):

        self.logger = logger

    def run(
        self,
        command,
        check=True,
        timeout=120,
        sudo=False,
    ):

        command = [
            str(x)
            for x in command
        ]

        if sudo and os.geteuid() != 0:

            command.insert(
                0,
                "sudo"
            )

        self.logger.debug(
            "$ "
            + " ".join(command)
        )

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        except subprocess.TimeoutExpired:

            raise RuntimeError(
                "Command timed out after "
                f"{timeout} seconds:\n"
                + " ".join(command)
            )

        if check and result.returncode != 0:

            raise RuntimeError(
                "\n".join(
                    [
                        "Command failed:",
                        " ".join(command),
                        "",
                        "STDOUT:",
                        result.stdout,
                        "",
                        "STDERR:",
                        result.stderr,
                    ]
                )
            )

        return result


# ============================================================
# STATE MANAGER
# ============================================================


class StateManager:

    def __init__(
        self,
        config,
        logger,
    ):

        self.config = config
        self.logger = logger

        self.config.work_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.state_file = (
            self.config.work_dir
            / "state.json"
        )

        self.state = {}

        self.load()

    def load(self):

        if not self.state_file.exists():

            return

        try:

            self.state = json.loads(
                self.state_file.read_text()
            )

            self.logger.info(
                "Previous deployment state found."
            )

        except Exception:

            self.logger.warning(
                "State file is invalid."
            )

    def save(self):

        self.state_file.write_text(
            json.dumps(
                self.state,
                indent=2,
            )
        )

    def set(self, key, value):

        self.state[key] = str(value)

        self.save()

    def get(self, key):

        return self.state.get(key)

    def phase(self, name):

        self.state["phase"] = name

        self.state["updated"] = (
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        self.save()

        self.logger.info(
            f"Deployment phase: {name}"
        )


# ============================================================
# HOST INTELLIGENCE
# ============================================================


class HostManager:

    def __init__(
        self,
        logger,
        command,
    ):

        self.logger = logger
        self.command = command

    def preflight(self):

        self.logger.info(
            "Checking host environment..."
        )

        if Path(
            "/etc/arch-release"
        ).exists():

            self.logger.success(
                "Arch Linux detected."
            )

        else:

            self.logger.warning(
                "Arch Linux was not detected."
            )

        required = [

            "virsh",

            "qemu-img",

            "ssh",

            "ssh-keygen",

        ]

        missing = []

        for binary in required:

            if shutil.which(binary):

                self.logger.debug(
                    f"{binary}: available"
                )

            else:

                missing.append(
                    binary
                )

        if missing:

            raise RuntimeError(
                "Missing required commands: "
                + ", ".join(missing)
            )

        if not Path(
            "/dev/kvm"
        ).exists():

            raise RuntimeError(
                "/dev/kvm is unavailable."
            )

        self.logger.success(
            "KVM acceleration is available."
        )

    def check_libvirt(
        self,
        config,
    ):

        result = self.command.run(
            [
                "virsh",
                "-c",
                config.libvirt_uri,
                "uri",
            ]
        )

        self.logger.success(
            "libvirt URI: "
            + result.stdout.strip()
        )


# ============================================================
# SSH INTELLIGENCE
# ============================================================


class SSHManager:

    def __init__(
        self,
        logger,
    ):

        self.logger = logger

    def discover(self):

        ssh_dir = (
            Path.home()
            / ".ssh"
        )

        ssh_dir.mkdir(
            mode=0o700,
            parents=True,
            exist_ok=True
        )

        preferred = [

            "id_ed25519",

            "id_ecdsa",

            "id_rsa",

        ]

        for name in preferred:

            private = (
                ssh_dir
                / name
            )

            public = (
                ssh_dir
                / f"{name}.pub"
            )

            if (
                private.exists()
                and public.exists()
            ):

                self.logger.success(
                    "SSH identity found:"
                )

                self.logger.success(
                    f"Private: {private}"
                )

                self.logger.success(
                    f"Public:  {public}"
                )

                return private, public

        self.logger.warning(
            "No complete SSH key pair found."
        )

        return self.generate()

    def generate(self):

        ssh_dir = (
            Path.home()
            / ".ssh"
        )

        private = (
            ssh_dir
            / "id_ed25519"
        )

        public = (
            ssh_dir
            / "id_ed25519.pub"
        )

        self.logger.info(
            "Generating Ed25519 SSH identity..."
        )

        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                str(private),
                "-N",
                "",
                "-C",
                "linuxways-fcos-agent-v5",
            ],
            check=True,
        )

        self.logger.success(
            "SSH identity generated."

        )

        return private, public


# ============================================================
# IMAGE INTELLIGENCE
# ============================================================


class ImageManager:

    def __init__(
        self,
        config,
        logger,
        command,
    ):

        self.config = config
        self.logger = logger
        self.command = command

    def local_search(self):

        self.logger.info(
            "Searching for local Fedora CoreOS images..."
        )

        locations = [

            Path.home()
            / "Downloads",

            Path.home()
            / "Downloads"
            / "Fedora-CoreOS",

            Path(
                "/var/lib/libvirt/images"
            ),

            Path(
                "/var/lib/libvirt/boot"
            ),

        ]

        candidates = []

        for location in locations:

            if not location.exists():

                continue

            self.logger.debug(
                f"Searching: {location}"
            )

            try:

                for image in location.rglob(
                    "*.qcow2"
                ):

                    if (
                        "coreos"
                        in image.name.lower()
                        or
                        "fedora"
                        in image.name.lower()
                    ):

                        candidates.append(
                            image
                        )

            except PermissionError:

                self.logger.warning(
                    f"Permission denied: {location}"
                )

        valid = []

        for image in candidates:

            if self.validate(image):

                valid.append(
                    image
                )

        if valid:

            selected = max(
                valid,
                key=lambda x: x.stat().st_mtime
            )

            self.logger.success(
                f"Valid FCOS image found: {selected}"
            )

            return selected

        return None

    def validate(self, image):

        self.logger.debug(
            f"Validating QCOW2: {image}"
        )

        result = self.command.run(
            [
                "qemu-img",
                "check",
                str(image),
            ],
            check=False,
            timeout=180,
        )

        if result.returncode != 0:

            self.logger.warning(
                f"Invalid QCOW2 image: {image}"
            )

            return False

        return True

    def download_latest(self):

        self.logger.info(
            "No valid local FCOS image found."
        )

        self.logger.info(
            "Automatic download requires the "
            "current FCOS artifact metadata."
        )

        raise RuntimeError(
            "No valid local FCOS image was found. "
            "Please provide a valid FCOS QCOW2 image "
            "with --image."
        )

    def obtain(self):

        if self.config.image_path:

            if not self.config.image_path.exists():

                raise RuntimeError(
                    f"Specified image does not exist: "
                    f"{self.config.image_path}"
                )

            if not self.validate(
                self.config.image_path
            ):

                raise RuntimeError(
                    "Specified QCOW2 image is invalid."
                )

            return self.config.image_path

        local = self.local_search()

        if local:

            return local

        return self.download_latest()


# ============================================================
# IGNITION MANAGER
# ============================================================


class IgnitionManager:

    def __init__(
        self,
        config,
        logger,
        public_key,
    ):

        self.config = config
        self.logger = logger
        self.public_key = public_key

    def create(self):

        ignition = {

            "ignition": {

                "version": "3.4.0"

            },

            "passwd": {

                "users": [

                    {

                        "name": "core",

                        "sshAuthorizedKeys": [

                            self.public_key

                        ],

                        "groups": [

                            "wheel"

                        ]

                    }

                ]

            }

        }

        ignition_file = (

            self.config.work_dir
            / "config.ign"

        )

        ignition_file.write_text(
            json.dumps(
                ignition,
                indent=2,
            )
        )

        try:

            json.loads(
                ignition_file.read_text()
            )

        except json.JSONDecodeError:

            raise RuntimeError(
                "Ignition JSON validation failed."
            )

        self.logger.success(
            f"Ignition ready: {ignition_file}"
        )

        return ignition_file


# ============================================================
# STORAGE MANAGER
# ============================================================


class StorageManager:

    def __init__(
        self,
        config,
        logger,
        command,
    ):

        self.config = config
        self.logger = logger
        self.command = command

    def prepare(self, source):

        self.config.image_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        destination = (

            self.config.image_dir
            / f"{self.config.vm_name}.qcow2"

        )

        if destination.exists():

            self.logger.info(
                "Existing deployment disk found."
            )

            if self.command.run(
                [
                    "qemu-img",
                    "check",
                    str(destination),
                ],
                check=False,
            ).returncode == 0:

                self.logger.success(
                    "Existing deployment disk is valid."
                )

                return destination

            self.logger.warning(
                "Existing disk is corrupted."
            )

            self.command.run(
                [
                    "rm",
                    "-f",
                    str(destination),
                ],
                sudo=True,
            )

        self.logger.info(
            "Copying FCOS image into libvirt storage..."
        )

        self.command.run(
            [
                "cp",
                str(source),
                str(destination),
            ],
            sudo=True,
            timeout=1800,
        )

        self.command.run(
            [
                "chmod",
                "0644",
                str(destination),
            ],
            sudo=True,
        )

        self.logger.success(
            f"Deployment disk ready: {destination}"
        )

        return destination


# ============================================================
# NETWORK MANAGER
# ============================================================


class NetworkManager:

    def __init__(
        self,
        config,
        logger,
        command,
    ):

        self.config = config
        self.logger = logger
        self.command = command

    def discover(self):

        result = self.command.run(
            [
                "virsh",
                "-c",
                self.config.libvirt_uri,
                "net-list",
                "--name",
            ]
        )

        networks = [

            x.strip()

            for x in result.stdout.splitlines()

            if x.strip()

        ]

        if "default" in networks:

            self.logger.success(
                "Using libvirt default network."
            )

            return "default"

        if networks:

            self.logger.success(
                f"Using network: {networks[0]}"
            )

            return networks[0]

        raise RuntimeError(
            "No active libvirt network found."
        )


# ============================================================
# VM MANAGER
# ============================================================


class VMManager:

    def __init__(
        self,
        config,
        logger,
        command,
        disk,
        ignition,
        network,
    ):

        self.config = config
        self.logger = logger
        self.command = command
        self.disk = disk
        self.ignition = ignition
        self.network = network

    def exists(self):

        result = self.command.run(
            [
                "virsh",
                "-c",
                self.config.libvirt_uri,
                "dominfo",
                self.config.vm_name,
            ],
            check=False,
        )

        return result.returncode == 0

    def state(self):

        result = self.command.run(
            [
                "virsh",
                "-c",
                self.config.libvirt_uri,
                "domstate",
                self.config.vm_name,
            ],
            check=False,
        )

        return result.stdout.strip()

    def xml_path(self):

        return (
            self.config.work_dir
            / "domain.xml"
        )

    def generate_xml(self):

        xml = f"""<domain type='kvm'
xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>

  <name>{escape(self.config.vm_name)}</name>

  <memory unit='MiB'>{self.config.memory_mib}</memory>

  <currentMemory unit='MiB'>{self.config.memory_mib}</currentMemory>

  <vcpu>{self.config.vcpus}</vcpu>

  <os firmware='efi'>
    <type arch='x86_64' machine='q35'>hvm</type>
  </os>

  <features>
    <acpi/>
    <apic/>
    <vmport state='off'/>
  </features>

  <cpu mode='host-passthrough' check='none'/>

  <clock offset='utc'/>

  <devices>

    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{escape(str(self.disk))}'/>
      <target dev='vda' bus='virtio'/>
    </disk>

    <interface type='network'>
      <source network='{escape(self.network)}'/>
      <model type='virtio'/>
    </interface>

    <serial type='pty'>
      <target type='isa-serial' port='0'/>
    </serial>

    <console type='pty'>
      <target type='serial' port='0'/>
    </console>

    <rng model='virtio'>
      <backend model='random'>/dev/urandom</backend>
    </rng>

  </devices>

  <qemu:commandline>
    <qemu:arg value='-fw_cfg'/>
    <qemu:arg value='name=opt/com.coreos/config,file={escape(str(self.ignition))}'/>
  </qemu:commandline>

</domain>
"""

        path = self.xml_path()

        path.write_text(
            xml
        )

        return path

    def validate_xml(self, path):

        self.logger.info(
            "Validating libvirt XML..."
        )

        result = self.command.run(
            [
                "virsh",
                "-c",
                self.config.libvirt_uri,
                "define",
                "--validate",
                str(path),
            ],
            check=False,
        )

        if result.returncode != 0:

            raise RuntimeError(
                "Libvirt XML validation failed:\n"
                + result.stderr
            )

        self.logger.success(
            "Libvirt XML validation passed."
        )

    def define(self):

        path = self.generate_xml()

        self.validate_xml(
            path
        )

        if self.exists():

            current = self.state()

            if current == "running":

                self.logger.success(
                    "VM is already running."
                )

                return

            if not self.config.replace:

                self.logger.info(
                    "Existing VM found."
                )

                self.logger.info(
                    "Reusing existing VM."
                )

                return

            self.logger.warning(
                "Replacing existing VM."
            )

            self.command.run(
                [
                    "virsh",
                    "-c",
                    self.config.libvirt_uri,
                    "destroy",
                    self.config.vm_name,
                ],
                check=False,
            )

            self.command.run(
                [
                    "virsh",
                    "-c",
                    self.config.libvirt_uri,
                    "undefine",
                    self.config.vm_name,
                    "--nvram",
                ],
                check=False,
            )

        self.command.run(
            [
                "virsh",
                "-c",
                self.config.libvirt_uri,
                "define",
                str(path),
            ]
        )

        self.logger.success(
            "VM defined successfully."
        )

    def start(self):

        if self.state() == "running":

            self.logger.success(
                "VM is already running."
            )

            return

        self.command.run(
            [
                "virsh",
                "-c",
                self.config.libvirt_uri,
                "start",
                self.config.vm_name,
            ]
        )

        self.logger.success(
            "VM started."
        )


# ============================================================
# IP DISCOVERY
# ============================================================


class IPManager:

    def __init__(
        self,
        config,
        logger,
        command,
    ):

        self.config = config
        self.logger = logger
        self.command = command

    def discover(self):

        result = self.command.run(
            [
                "virsh",
                "-c",
                self.config.libvirt_uri,
                "domifaddr",
                self.config.vm_name,
                "--source",
                "lease",
            ],
            check=False,
        )

        for line in result.stdout.splitlines():

            for token in line.split():

                if "/" not in token:

                    continue

                ip = token.split(
                    "/"
                )[0]

                try:

                    socket.inet_aton(
                        ip
                    )

                    return ip

                except OSError:

                    continue

        return None

    def wait(self):

        self.logger.info(
            "Waiting for VM IP address..."
        )

        deadline = (
            time.time()
            + self.config.ip_timeout
        )

        while time.time() < deadline:

            ip = self.discover()

            if ip:

                self.logger.success(
                    f"VM IP discovered: {ip}"
                )

                return ip

            time.sleep(5)

        raise TimeoutError(
            "VM did not receive an IP address."
        )


# ============================================================
# SSH CHECK
# ============================================================


class SSHManagerRemote:

    def __init__(
        self,
        config,
        logger,
        private_key,
    ):

        self.config = config
        self.logger = logger
        self.private_key = private_key

    def test(self, ip):

        result = subprocess.run(
            [
                "ssh",
                "-i",
                str(self.private_key),
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "ConnectTimeout=5",
                f"{self.config.ssh_user}@{ip}",
                "echo FCOS_READY",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        return (
            result.returncode == 0
            and
            "FCOS_READY"
            in result.stdout
        )

    def wait(self, ip):

        self.logger.info(
            "Waiting for SSH service..."
        )

        deadline = (
            time.time()
            + self.config.ssh_timeout
        )

        while time.time() < deadline:

            if self.test(ip):

                self.logger.success(
                    "SSH authentication successful."
                )

                return

            time.sleep(10)

        raise TimeoutError(
            "SSH did not become available."
        )


# ============================================================
# SELF-DIAGNOSTICS
# ============================================================


class Diagnostics:

    def __init__(
        self,
        config,
        logger,
        command,
    ):

        self.config = config
        self.logger = logger
        self.command = command

    def run(self):

        self.logger.warning(
            "Starting automatic diagnostics..."
        )

        checks = [

            (
                "VM state",
                [
                    "virsh",
                    "-c",
                    self.config.libvirt_uri,
                    "domstate",
                    self.config.vm_name,
                ],
            ),

            (
                "VM interfaces",
                [
                    "virsh",
                    "-c",
                    self.config.libvirt_uri,
                    "domiflist",
                    self.config.vm_name,
                ],
            ),

            (
                "VM addresses",
                [
                    "virsh",
                    "-c",
                    self.config.libvirt_uri,
                    "domifaddr",
                    self.config.vm_name,
                ],
            ),

            (
                "DHCP leases",
                [
                    "virsh",
                    "-c",
                    self.config.libvirt_uri,
                    "net-dhcp-leases",
                    "default",
                ],
            ),

        ]

        report = []

        for title, command in checks:

            result = self.command.run(
                command,
                check=False,
            )

            report.append(
                f"\n===== {title} =====\n"
                f"{result.stdout}\n"
                f"{result.stderr}"
            )

        report_file = (
            self.config.work_dir
            / "diagnostic-report.txt"
        )

        report_file.write_text(
            "\n".join(report)
        )

        self.logger.warning(
            f"Diagnostic report saved: {report_file}"
        )


# ============================================================
# MAIN AGENT
# ============================================================


class FCOSAgentV5:

    def __init__(
        self,
        config,
        logger,
    ):

        self.config = config

        self.logger = logger

        self.command = (
            CommandRunner(
                logger
            )
        )

        self.state = (
            StateManager(
                config,
                logger
            )
        )

    def deploy(self):

        try:

            self.state.phase(
                "PREFLIGHT"
            )

            host = HostManager(
                self.logger,
                self.command,
            )

            host.preflight()

            host.check_libvirt(
                self.config
            )

            self.state.phase(
                "SSH_READY"
            )

            ssh = SSHManager(
                self.logger
            )

            private_key, public_key = (
                ssh.discover()
            )

            self.state.set(
                "private_key",
                private_key
            )

            self.state.set(
                "public_key",
                public_key
            )

            self.state.phase(
                "IMAGE_READY"
            )

            image = ImageManager(
                self.config,
                self.logger,
                self.command,
            ).obtain()

            self.state.set(
                "source_image",
                image
            )

            self.state.phase(
                "IGNITION_READY"
            )

            ignition = IgnitionManager(
                self.config,
                self.logger,
                public_key.read_text().strip(),
            ).create()

            self.state.set(
                "ignition",
                ignition
            )

            self.state.phase(
                "STORAGE_READY"
            )

            disk = StorageManager(
                self.config,
                self.logger,
                self.command,
            ).prepare(
                image
            )

            self.state.set(
                "disk",
                disk
            )

            self.state.phase(
                "NETWORK_READY"
            )

            network = NetworkManager(
                self.config,
                self.logger,
                self.command,
            ).discover()

            self.state.set(
                "network",
                network
            )

            self.state.phase(
                "VM_READY"
            )

            vm = VMManager(
                self.config,
                self.logger,
                self.command,
                disk,
                ignition,
                network,
            )

            vm.define()

            self.state.phase(
                "VM_RUNNING"
            )

            vm.start()

            self.state.phase(
                "IP_READY"
            )

            ip = IPManager(
                self.config,
                self.logger,
                self.command,
            ).wait()

            self.state.set(
                "ip",
                ip
            )

            self.state.phase(
                "SSH_READY"
            )

            SSHManagerRemote(
                self.config,
                self.logger,
                private_key,
            ).wait(
                ip
            )

            self.state.phase(
                "COMPLETE"
            )

            self.logger.success(
                "========================================"
            )

            self.logger.success(
                "FEDORA COREOS DEPLOYMENT SUCCESSFUL"
            )

            self.logger.success(
                f"VM: {self.config.vm_name}"
            )

            self.logger.success(
                f"IP: {ip}"
            )

            self.logger.success(
                f"SSH: ssh -i {private_key} "
                f"core@{ip}"
            )

            self.logger.success(
                "========================================"
            )

        except Exception as error:

            self.logger.error(
                str(error)
            )

            Diagnostics(
                self.config,
                self.logger,
                self.command,
            ).run()

            self.logger.error(
                "Deployment failed with diagnostics."
            )

            raise


# ============================================================
# CLI
# ============================================================


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Linux Ways FCOS-Agent V5"
        )
    )

    parser.add_argument(
        "--vm-name",
        default="fcos-agent-v5",
    )

    parser.add_argument(
        "--image",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--replace",
        action="store_true",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
    )

    args = parser.parse_args()

    config = Config(
        vm_name=args.vm_name,
        image_path=args.image,
        replace=args.replace,
        verbose=args.verbose,
    )

    logger = Logger(
        verbose=args.verbose
    )

    agent = FCOSAgentV5(
        config,
        logger,
    )

    try:

        agent.deploy()

    except KeyboardInterrupt:

        logger.warning(
            "Deployment interrupted by user."
        )

        sys.exit(130)

    except Exception:

        sys.exit(1)


if __name__ == "__main__":

    main()
