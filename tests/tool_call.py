"""Calls a tool handler the way pipecat does, with a stand-in for FunctionCallParams."""

from types import SimpleNamespace
from typing import Any

from hr_screener.agent import prompt_text
from hr_screener.agent.tools import ToolDeps, build_tools


class FakeLLM:
    def __init__(self) -> None:
        self.pushed: list[Any] = []

    async def push_frame(self, frame: Any) -> None:
        self.pushed.append(frame)


class Call:
    """Captures what a tool sends back to the model."""

    def __init__(self, deps: ToolDeps) -> None:
        self.handlers = build_tools(deps.mode)[1]
        self.results: list[dict[str, Any]] = []
        self.llm = FakeLLM()
        self.deps = deps

    async def run(self, tool: str, **arguments: Any) -> None:
        """Call a tool by its registered name. `tool` and the argument names are canonical;
        they are mapped to the registered ones."""
        text = prompt_text.TOOLS[tool]

        async def result_callback(result: dict[str, Any], *, properties: Any = None) -> None:
            self.results.append(result)

        params: Any = SimpleNamespace(
            app_resources=self.deps,
            arguments={text.params[k].name: v for k, v in arguments.items()},
            result_callback=result_callback,
            llm=self.llm,
        )
        await self.handlers[text.name](params)

    @property
    def result(self) -> dict[str, Any]:
        return self.results[-1]
