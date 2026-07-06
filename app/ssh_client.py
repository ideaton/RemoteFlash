"""
RemoteFlash — pure-Python SSH/SFTP client (paramiko).

No external C/Perl/OpenSSL dependencies. Handles connection, remote command
execution, SFTP transfers, device discovery and remote port labels.
"""

import json
import socket
import time
from pathlib import Path
from typing import List, Optional, Tuple

import paramiko

from models import AuthMethod, ConnectionProfile


class SSHClient:
    """Pure-Python SSH client wrapper using paramiko"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None

    def connect(self, profile: ConnectionProfile) -> bool:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if profile.auth_method == AuthMethod.Password.value:
                self.client.connect(
                    hostname=profile.ip,
                    port=profile.port,
                    username=profile.username,
                    password=profile.password,
                    timeout=self.timeout,
                )
            elif profile.auth_method == AuthMethod.RsaKey.value:
                if not profile.rsa_key_path or not Path(profile.rsa_key_path).exists():
                    raise FileNotFoundError(f"RSA key not found: {profile.rsa_key_path}")

                key_path = profile.rsa_key_path
                if key_path.lower().endswith('.ppk'):
                    key_path = self._handle_ppk_key(key_path)

                self.client.connect(
                    hostname=profile.ip,
                    port=profile.port,
                    username=profile.username,
                    key_filename=key_path,
                    timeout=self.timeout,
                )
            else:
                raise ValueError(f"Unsupported auth method: {profile.auth_method}")

            return True
        except Exception as e:
            raise ConnectionError(f"SSH connection failed: {e}")

    def exec_command(self, command: str) -> Tuple[str, str, int]:
        if not self.client:
            raise RuntimeError("Not connected")
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            return out, err, exit_status
        except Exception as e:
            raise RuntimeError(f"Command execution failed: {e}")

    def sftp_upload(self, local_path: Path, remote_path: str) -> bool:
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()
            self.sftp.put(str(local_path), remote_path)
            return True
        except Exception as e:
            raise RuntimeError(f"SFTP upload failed: {e}")

    def sftp_download(self, remote_path: str, local_path: Path) -> bool:
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()
            self.sftp.get(remote_path, str(local_path))
            return True
        except Exception as e:
            raise RuntimeError(f"SFTP download failed: {e}")

    def disconnect(self):
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None

    def ping_host(self, host: str, timeout: int = 3) -> Optional[float]:
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, 22))
            sock.close()
            elapsed = (time.time() - start) * 1000
            return elapsed
        except Exception:
            return None

    def list_available_ports(self) -> List[dict]:
        """List available serial ports on remote device with descriptions"""
        if not self.client:
            raise RuntimeError("Not connected")
        try:
            # Get list of serial ports
            out, _, _ = self.exec_command("ls -1 /dev/tty* 2>/dev/null | grep -E '(ttyUSB|ttyACM|ttyS|COM)'")
            ports_list = [p.strip() for p in out.split("\n") if p.strip()]

            if not ports_list:
                return []

            # Enrich with descriptions from sysfs
            ports_with_info = []
            for port in ports_list:
                port_info = {
                    "path": port,
                    "name": port.split("/")[-1],  # ttyUSB0, ttyACM0, etc.
                    "description": "",
                    "type": "serial"
                }

                # Try to get description from different sources
                # Method 1: Try to read product/manufacturer from sysfs (Linux)
                if "ttyUSB" in port or "ttyACM" in port:
                    # Extract port number
                    port_num = ''.join(c for c in port if c.isdigit())

                    # Try udev/sysfs for USB device info
                    cmds = [
                        f"cat /sys/class/tty/{port.split('/')[-1]}/device/../product 2>/dev/null",
                        f"cat /sys/class/tty/{port.split('/')[-1]}/device/../manufacturer 2>/dev/null",
                        f"lsusb 2>/dev/null | grep -i usb | head -1",
                    ]

                    descriptions = []
                    for cmd in cmds:
                        try:
                            out_desc, _, _ = self.exec_command(cmd)
                            if out_desc.strip():
                                descriptions.append(out_desc.strip())
                        except:
                            pass

                    if descriptions:
                        port_info["description"] = " - ".join(descriptions[:2])

                ports_with_info.append(port_info)

            return ports_with_info
        except Exception:
            return []

    def list_available_programmers(self) -> List[dict]:
        """List available USBasp programmers connected via USB"""
        if not self.client:
            raise RuntimeError("Not connected")
        try:
            # USBasp vendor:product ID is 16c0:05dc
            out, _, _ = self.exec_command("lsusb -d 16c0:05dc 2>/dev/null")

            if not out.strip():
                return []

            programmers = []
            for line in out.split("\n"):
                if not line.strip():
                    continue
                # Parse lsusb output: "Bus 001 Device 005: ID 16c0:05dc Van Ooijen Technische Informatica USBasp"
                parts = line.split()
                if len(parts) >= 4:
                    bus = parts[1]
                    device = parts[3].rstrip(":")

                    prog_info = {
                        "path": f"usb:{bus}:{device}",
                        "name": f"USBasp (Bus {bus}, Device {device})",
                        "description": "Atmel USBasp Programmer",
                        "type": "usbasp",
                        "bus": bus,
                        "device": device
                    }
                    programmers.append(prog_info)

            return programmers
        except Exception:
            return []

    def load_port_labels(self, remote_label_file: str) -> dict:
        """Load port labels from remote file"""
        if not self.client:
            return {}
        try:
            out, _, code = self.exec_command(f"cat {remote_label_file} 2>/dev/null")
            if code == 0 and out.strip():
                return json.loads(out)
        except Exception:
            pass
        return {}

    def save_port_labels(self, labels: dict, remote_label_file: str) -> bool:
        """Save port labels to remote file"""
        if not self.client:
            return False
        try:
            import tempfile
            temp_file = Path(tempfile.gettempdir()) / "port_labels.json"
            with open(temp_file, "w") as f:
                json.dump(labels, f, indent=2)

            # Create directory if needed
            remote_dir = str(Path(remote_label_file).parent)
            self.exec_command(f"mkdir -p {remote_dir}")

            # Upload file
            self.sftp_upload(temp_file, remote_label_file)
            temp_file.unlink()
            return True
        except Exception:
            return False

    def _handle_ppk_key(self, ppk_path: str) -> str:
        ppk_file = Path(ppk_path)
        if not ppk_file.exists():
            raise FileNotFoundError(f"PPK key file not found: {ppk_path}")

        try:
            import subprocess
            import tempfile
            import shutil

            puttygen_path = shutil.which("puttygen")
            if puttygen_path:
                temp_dir = Path(tempfile.gettempdir())
                openssh_key = temp_dir / f"{ppk_file.stem}_openssh.pem"
                commands = [
                    [puttygen_path, str(ppk_path), "-o", str(openssh_key)],
                    [puttygen_path, "-O", "private-openssh", "-o", str(openssh_key), str(ppk_path)],
                ]
                for cmd in commands:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0 and openssh_key.exists():
                            return str(openssh_key)
                    except Exception:
                        continue
        except Exception:
            pass

        raise RuntimeError(
            "PPK format detected but conversion failed.\n\n"
            "Convert to OpenSSH format using PuTTYgen:\n"
            "Conversions → Export OpenSSH key → save as .pem"
        )
