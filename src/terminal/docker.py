import asyncio
import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class ResourceLimits:
    max_processes: int = 10
    max_memory_mb: int = 1024
    max_cpu_percent: float = 25.0
    max_disk_mb: int = 1024
    max_file_size_mb: int = 50


@dataclass
class ProcessInfo:
    pid: int
    command: str
    cpu_percent: float
    memory_mb: float
    start_time: datetime


class DockerService:
    def __init__(self, container_name: str = "hzsh_linux"):
        self.container_name = container_name
        self.user_id_map = {}
        self.limits = ResourceLimits()
        self.user_processes = {}

    def get_uid(self, discord_id: str) -> int:
        if discord_id not in self.user_id_map:
            hash_val = int(hashlib.sha256(discord_id.encode()).hexdigest()[:8], 16)
            self.user_id_map[discord_id] = (hash_val % 2147483147) + 1000
        return self.user_id_map[discord_id]

    async def check_health(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self.container_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and "true" in result.stdout
        except Exception:
            return False

    async def get_user_processes(self, discord_id: str) -> list[ProcessInfo]:
        """get all processes for user"""
        uid = self.get_uid(discord_id)

        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container_name,
                    "ps",
                    "-u",
                    str(uid),
                    "-o",
                    "pid,comm,%cpu,%mem,etime",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return []

            processes = []
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        processes.append(
                            ProcessInfo(
                                pid=int(parts[0]),
                                command=parts[1],
                                cpu_percent=float(parts[2]),
                                memory_mb=float(parts[3]) * 10,
                                start_time=datetime.utcnow(),
                            )
                        )
                    except ValueError:
                        continue

            return processes
        except Exception:
            return []

    async def check_resource_limits(
        self, discord_id: str
    ) -> Tuple[bool, Optional[str]]:
        """check if within resource limits"""
        processes = await self.get_user_processes(discord_id)

        if len(processes) >= self.limits.max_processes:
            return False, f"process limit reached ({self.limits.max_processes})"

        total_cpu = sum(p.cpu_percent for p in processes)
        if total_cpu > self.limits.max_cpu_percent:
            return (
                False,
                f"cpu limit exceeded ({total_cpu:.1f}% > {self.limits.max_cpu_percent}%)",
            )

        total_mem = sum(p.memory_mb for p in processes)
        if total_mem > self.limits.max_memory_mb:
            return (
                False,
                f"memory limit exceeded ({total_mem:.0f}mb > {self.limits.max_memory_mb}mb)",
            )

        disk_usage = await self.get_user_quota(
            discord_id.split("-")[0] if "-" in discord_id else discord_id
        )
        if disk_usage:
            try:
                usage_mb = float(disk_usage.replace("M", "").replace("G", "000"))
                if usage_mb > self.limits.max_disk_mb:
                    return (
                        False,
                        f"disk limit exceeded ({usage_mb:.0f}mb > {self.limits.max_disk_mb}mb)",
                    )
            except ValueError:
                pass

        return True, None

    async def kill_user_process(self, discord_id: str, pid: int) -> bool:
        """kill a process"""
        self.get_uid(discord_id)

        try:
            result = subprocess.run(
                ["docker", "exec", self.container_name, "kill", "-9", str(pid)],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def kill_all_user_processes(self, discord_id: str) -> int:
        """kill all processes for user"""
        uid = self.get_uid(discord_id)

        try:
            subprocess.run(
                ["docker", "exec", self.container_name, "pkill", "-9", "-u", str(uid)],
                capture_output=True,
                timeout=5,
            )

            processes = await self.get_user_processes(discord_id)
            return len(processes)
        except Exception:
            return 0

    async def exec_command(
        self,
        command: str,
        username: Optional[str] = None,
        discord_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        timeout: float = 30.0,
        check_limits: bool = True,
    ) -> Tuple[str, int]:
        """execute command in the container"""

        if check_limits and discord_id:
            allowed, reason = await self.check_resource_limits(discord_id)
            if not allowed:
                return f"resource limit exceeded: {reason}", -1

        cmd_args = ["docker", "exec"]

        if username and discord_id:
            uid = self.get_uid(discord_id)
            cmd_args.extend(["-u", str(uid)])

        if working_dir:
            cmd_args.extend(["-w", working_dir])

        cmd_args.extend([self.container_name, "bash", "-c", command])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")
            result = output + error

            return result.strip() if result else "", process.returncode or 0

        except asyncio.TimeoutError:
            return f"command timed out after {timeout}s", -1
        except Exception as e:
            return f"error executing command: {str(e)}", -1

    async def ensure_user_exists(
        self, username: str, discord_id: str, home_dir: Path
    ) -> bool:
        """ensure user exists with quotas"""
        uid = self.get_uid(discord_id)

        user_home = home_dir / username
        if not user_home.exists():
            user_home.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ["docker", "exec", self.container_name, "id", "-u", str(uid)],
            capture_output=True,
        )

        if result.returncode != 0:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container_name,
                    "useradd",
                    "-u",
                    str(uid),
                    "-m",
                    "-s",
                    "/bin/bash",
                    username,
                ],
                capture_output=True,
            )

        subprocess.run(
            [
                "docker",
                "exec",
                self.container_name,
                "chown",
                "-R",
                f"{uid}:{uid}",
                f"/home/{username}",
            ],
            capture_output=True,
        )

        return True

    async def get_disk_usage(self, path: str = "/home") -> Optional[str]:
        """get disk usage"""
        try:
            result = subprocess.run(
                ["docker", "exec", self.container_name, "df", "-h", path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        return parts[4]
        except Exception:
            pass
        return None

    async def get_user_quota(self, username: str) -> Optional[str]:
        """get disk quota"""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container_name,
                    "du",
                    "-sh",
                    f"/home/{username}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return result.stdout.split()[0]
        except Exception:
            pass
        return None

    async def get_container_info(self, info_type: str) -> str:
        """get container info"""
        commands_map = {
            "os": "cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'",
            "kernel": "uname -r",
            "host": "hostname",
            "uptime": "uptime -p",
            "cpu": "lscpu | grep 'Model name' | cut -d':' -f2 | xargs",
            "memory": "free -h | awk '/^Mem:/ {print $3 \" / \" $2}'",
            "disk": "df -h / | awk 'NR==2 {print $3 \" / \" $2}'",
        }

        cmd = commands_map.get(info_type)
        if not cmd:
            return "unknown"

        output, exit_code = await self.exec_command(
            cmd, timeout=5.0, check_limits=False
        )
        return output if exit_code == 0 else "unavailable"

    async def get_stats(self) -> dict:
        """get docker stats"""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "stats",
                self.container_name,
                "--no-stream",
                "--format",
                "{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5.0)
            stats = stdout.decode("utf-8", errors="replace").strip().split("|")

            return {
                "cpu_usage": stats[0] if len(stats) > 0 else "unknown",
                "mem_usage": stats[1] if len(stats) > 1 else "unknown",
                "net_io": stats[2] if len(stats) > 2 else "unknown",
            }
        except Exception:
            return {
                "cpu_usage": "unavailable",
                "mem_usage": "unavailable",
                "net_io": "unavailable",
            }

    async def list_users(self) -> list:
        """list all users"""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    self.container_name,
                    "bash",
                    "-c",
                    "getent passwd | awk -F: '$3 >= 1000 {print $1}'",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                return [u for u in result.stdout.strip().split("\n") if u]
            return []
        except Exception:
            return []


_docker_service = None


def get_docker_service() -> DockerService:
    """get docker service singleton"""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
