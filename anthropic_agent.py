import os
import anthropic

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class AnthropicAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "anthropic-direct"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        pass

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"]
        )

        messages = [
            {
                "role": "user",
                "content": instruction,
            }
        ]

        tools = [
            {
                "name": "bash",
                "description": (
                    "Run a bash command inside the task environment. "
                    "Use this to inspect files, execute commands, and solve the task."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The bash command to execute.",
                        }
                    },
                    "required": ["command"],
                },
            }
        ]

        for _ in range(20):
            response = client.messages.create(
                model="claude-opus-5",
                max_tokens=2048,
                tools=tools,
                messages=messages,
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                }
            )

            tool_uses = [
                block
                for block in response.content
                if block.type == "tool_use"
            ]

            if not tool_uses:
                break

            tool_results = []

            for tool_use in tool_uses:
                if tool_use.name != "bash":
                    continue

                command = tool_use.input["command"]

                result = await environment.exec(
                    command=command
                )

                output = (
                    f"stdout:\n{result.stdout}\n\n"
                    f"stderr:\n{result.stderr}\n\n"
                    f"exit_code: {result.return_code}"
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": output,
                    }
                )

            messages.append(
                {
                    "role": "user",
                    "content": tool_results,
                }
            )
