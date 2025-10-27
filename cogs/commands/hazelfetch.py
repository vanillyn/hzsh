
from discord.ext import commands
import asyncio

class Hazelfetch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.container_name = "hzsh_linux"
    
    async def get_container_info(self, info_type):
        commands_map = {
            "os": "cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'",
            "kernel": "uname -r",
            "host": "hostname",
            "uptime": "uptime -p",
            "cpu": "lscpu | grep 'Model name' | cut -d':' -f2 | xargs",
            "memory": "free -h | awk '/^Mem:/ {print $3 \" / \" $2}'",
            "disk": "df -h / | awk 'NR==2 {print $3 \" / \" $2}'",
            "user": "whoami",
        }
        
        cmd = commands_map.get(info_type)
        if not cmd:
            return "unknown"
        
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "exec", self.container_name,
                "bash", "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=5.0
            )
            
            return stdout.decode('utf-8', errors='replace').strip()
            
        except Exception:
            return "unavailable"
    
    async def get_docker_stats(self):
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "stats", self.container_name,
                "--no-stream", "--format",
                "{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=5.0
            )
            
            stats = stdout.decode('utf-8', errors='replace').strip().split('|')
            return {
                "cpu_usage": stats[0] if len(stats) > 0 else "unknown",
                "mem_usage": stats[1] if len(stats) > 1 else "unknown",
                "net_io": stats[2] if len(stats) > 2 else "unknown"
            }
        except Exception:
            return {
                "cpu_usage": "unavailable",
                "mem_usage": "unavailable",
                "net_io": "unavailable"
            }
    
    @commands.command()
    async def hazelfetch(self, ctx, *flags):
        valid_flags = {
            "--os", "--kernel", "--host", "--uptime", 
            "--cpu", "--memory", "--disk", "--user",
            "--stats", "--all"
        }
        
        flags_set = set(flags)
        
        if "--all" in flags_set or not flags_set:
            flags_set = {"--os", "--kernel", "--host", "--uptime", "--cpu", "--memory", "--disk", "--stats"}
        
        invalid = flags_set - valid_flags
        if invalid:
            await ctx.send(f"unknown flags: {', '.join(invalid)}")
            return
        
        async with ctx.typing():
            info = {}
            
            if "--os" in flags_set:
                info["os"] = await self.get_container_info("os")
            if "--kernel" in flags_set:
                info["kernel"] = await self.get_container_info("kernel")
            if "--host" in flags_set:
                info["host"] = await self.get_container_info("host")
            if "--uptime" in flags_set:
                info["uptime"] = await self.get_container_info("uptime")
            if "--cpu" in flags_set:
                info["cpu"] = await self.get_container_info("cpu")
            if "--memory" in flags_set:
                info["memory"] = await self.get_container_info("memory")
            if "--disk" in flags_set:
                info["disk"] = await self.get_container_info("disk")
            if "--user" in flags_set:
                info["user"] = await self.get_container_info("user")
            if "--stats" in flags_set:
                stats = await self.get_docker_stats()
                info["cpu_usage"] = stats["cpu_usage"]
                info["mem_usage"] = stats["mem_usage"]
                info["net_io"] = stats["net_io"]
        
        username = ctx.author.name
        hostname = info.get("host", "hazelrun")
        title = f"{username}@{hostname}"
        separator = "-" * len(title)
        
        lines = [
            "```ansi",
            f"\x1b[1;35m{title}\x1b[0m",
            f"\x1b[1;35m{separator}\x1b[0m"
        ]
        
        if "os" in info:
            lines.append(f"\x1b[1;36mos\x1b[0m: {info['os']}")
        if "kernel" in info:
            lines.append(f"\x1b[1;36mkernel\x1b[0m: {info['kernel']}")
        if "host" in info:
            lines.append(f"\x1b[1;36mhost\x1b[0m: {info['host']}")
        if "uptime" in info:
            lines.append(f"\x1b[1;36muptime\x1b[0m: {info['uptime']}")
        if "cpu" in info:
            lines.append(f"\x1b[1;36mcpu\x1b[0m: {info['cpu']}")
        if "memory" in info:
            lines.append(f"\x1b[1;36mmemory\x1b[0m: {info['memory']}")
        if "disk" in info:
            lines.append(f"\x1b[1;36mdisk\x1b[0m: {info['disk']}")
        if "cpu_usage" in info:
            lines.append(f"\x1b[1;36mcpu usage\x1b[0m: {info['cpu_usage']}")
        if "mem_usage" in info:
            lines.append(f"\x1b[1;36mmem usage\x1b[0m: {info['mem_usage']}")
        if "net_io" in info:
            lines.append(f"\x1b[1;36mnet i/o\x1b[0m: {info['net_io']}")
        
        lines.append("```")
        
        await ctx.send("\n".join(lines))

async def setup(bot):
    await bot.add_cog(Hazelfetch(bot))