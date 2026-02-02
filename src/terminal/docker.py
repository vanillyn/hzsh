import asyncio
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class DockerService:
    def __init__(self, container_name: str = "hzsh_linux"):
        self.container_name = container_name
        self.user_id_map = {}

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

    async def exec_command(
        self,
        command: str,
        username: Optional[str] = None,
        discord_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Tuple[str, int]:
        """execute command in container, return (output, exit_code)"""
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
        """ensure user exists in container and has home directory"""
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
        """get disk usage for a path"""
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
        """get disk quota for specific user"""
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
        """get various container information"""
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

        output, exit_code = await self.exec_command(cmd, timeout=5.0)
        return output if exit_code == 0 else "unavailable"

    async def get_stats(self) -> dict:
        """get docker stats for container"""
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
        """list all users in container (uid >= 1000)"""
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
    """get or create the global docker service instance"""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
