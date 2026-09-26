"""Harbor 0.23.0 Docker boundary: no host mounts; fail-closed collection."""
import json
import hashlib
import shlex
from importlib.metadata import version
from pathlib import Path

from harbor.environments.docker.docker import DockerEnvironment


class ChartREnvironment(DockerEnvironment):
    def __init__(self, *args, **kwargs):
        if version("harbor") != "0.23.0":
            raise RuntimeError("ChartR requires the inspected Harbor 0.23.0 interface")
        kwargs["mounts"] = []
        self._main_stopped = False
        super().__init__(*args, **kwargs)

    @property
    def capabilities(self):
        return super().capabilities.model_copy(update={"mounted": False})

    async def start(self, force_build=False):
        await super().start(force_build=force_build)
        await self.ensure_dirs(["/logs/agent", "/logs/verifier", "/logs/artifacts"], chmod=True)
        result = await self._run_docker_compose_command(["ps", "--format", "json"])
        containers = [json.loads(line) for line in result.stdout.splitlines() if line]
        if len(containers) == 1 and isinstance(containers[0], list):
            containers = containers[0]
        # Query only mount metadata, never environment variables (which may contain secrets).
        import asyncio
        for container in containers:
            process = await asyncio.create_subprocess_exec(
                "docker", "inspect", "--format", "{{json .Mounts}}", container["ID"],
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            if process.returncode or any(m["Type"] == "bind" for m in json.loads(stdout)):
                raise RuntimeError("ChartR containers must not have host bind mounts")
        controller = self.trial_paths.trial_dir / "controller"
        controller.mkdir(exist_ok=True)
        if (self.environment_dir / "service/fixture.json").exists():
            result = await super().service_exec(
                "python /app/control.py attest " + shlex.quote(str(self.context_id)), service="clinic", timeout_sec=30)
            if result.return_code:
                raise RuntimeError("Clinic startup attestation failed")
            attestation = json.loads(result.stdout)
            baseline = json.loads((self.environment_dir.parent / "tests/baseline.json").read_text())
            if attestation["initial_digest"] != baseline["initial_digest"]:
                raise RuntimeError("Clinic initial digest differs from private baseline")
            (controller / "attestation.json").write_text(json.dumps(attestation, indent=2))
            task = self.environment_dir.parent
            files = {str(p.relative_to(task)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in task.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
            (controller / "run-manifest.json").write_text(json.dumps({
                "harbor": version("harbor"), "anthropic": version("anthropic"),
                "provider": "chartr_environment:ChartREnvironment", "task_files_sha256": files,
                "trial_id": str(self.context_id), "bind_mounts": False,
                "container_images": {c["Service"]: c["Image"] for c in containers},
                "provider_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            }, indent=2))
        elif (self.environment_dir / "baseline.json").exists():
            # Private verifier only; never materialized in the agent container.
            await self.ensure_dirs(["/evidence"], chmod=True)
            await self.upload_file(controller / "attestation.json", "/evidence/attestation.json")
            termination = controller / "anthropic/termination.json"
            if termination.exists():
                await self.upload_file(termination, "/evidence/termination.json")

    async def stop_service(self, service):
        await super().stop_service(service)
        if service == "main":
            running = await self._run_docker_compose_command(
                ["ps", "--status", "running", "--services"]
            )
            if "main" in running.stdout.splitlines():
                raise RuntimeError("Agent container still running; refusing collection")
            self._main_stopped = True

    async def service_exec(self, command, *, service=None, **kwargs):
        if service and service != "main" and not self._main_stopped:
            # Harbor's exception-recovery path does not stop main before hooks.
            # Enforce the same ordering even for cancellation or agent failures.
            await self.stop_service("main")
        return await super().service_exec(command, service=service, **kwargs)

    async def service_download_file(self, source_path, target_path, *, service=None):
        if service == "clinic" and source_path == "/evidence/snapshot.json":
            # Docker cp on this Docker Desktop version cannot see this tmpfs file.
            # Read through the trusted sidecar exec channel, never the agent shell.
            result = await self.service_exec("cat /evidence/snapshot.json", service="clinic", timeout_sec=30)
            if result.return_code:
                raise RuntimeError("Trusted clinic snapshot collection failed")
            snapshot = json.loads(result.stdout)
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(snapshot, indent=2))
            return
        await super().service_download_file(source_path, target_path, service=service)
