"""The fixed Full-Duplex-Bench agent: one prompt and one tool set shared by EVERY variant.

The bench assesses the system design (VAD, turn detection, interruption handling, and later
a "system-one" model after STT), not the prompt or the tools. So both are a versioned
constant. Change them only together with a BENCH_AGENT_VERSION bump, and compare runs only
when `bench_agent_fingerprint()` matches. A variant may append text via
`BenchAgent.extra_instructions` (declared in `variants.py` and recorded in the manifest).

The prompt must not contain turn-taking or overlap-handling instructions; those are design
choices that belong to variants (tests enforce a keyword blacklist).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pipecat.adapters.llm.schemas.direct_function import DirectFunctionWrapper
from pipecat.services.llm_service import FunctionCallParams

BENCH_AGENT_VERSION = "1"

BENCH_SYSTEM_PROMPT = """\
You are a friendly voice assistant that people talk to at home and on the phone. You can \
control their devices, manage timers, reminders and alarms, read and add calendar events, \
send and read messages and email, play music and podcasts, take notes, and look up facts such \
as weather, sports scores, stocks, news, order status, traffic and device battery levels. \
You can also just chat.

# Voice rules
Your words are spoken aloud by a text-to-speech engine, so write only what sounds natural \
when spoken. Use plain spoken sentences. No markdown, bullet points, numbered lists, emojis \
or special symbols. Say numbers, dates and times the way a person would say them.

# Length
Answer at the length the request calls for. For commands, confirmations and quick facts, \
reply in one or two short sentences. When the person asks you to explain, describe, compare \
or recommend something, give a fuller spoken explanation of roughly five to eight sentences \
that flows naturally from one point to the next.

# Tools
Use a tool for any action (devices, timers, calendar, messages, media, notes) and for any \
personal or live information (weather, scores, orders, battery levels, unread email). Never \
pretend to have done something without calling the tool. After the tool returns, confirm \
briefly what was done or report what you found. If a tool reports a problem, say so plainly.

# Conversation
Be warm and natural. If the person makes small talk, reply like a friendly person would. \
If a request is unclear, ask one short clarifying question."""


# Direct functions; typed loosely because LLMContext's tools parameter is a wide union.
ToolFn = Any


def make_bench_tools(latency_secs: float = 0.3) -> list[ToolFn]:
    """Mock tools: deterministic canned JSON after a fixed simulated latency. No network,
    no Redis, no app_resources. The schemas do not depend on `latency_secs`."""

    async def _done(params: FunctionCallParams, result: dict[str, Any]) -> None:
        await asyncio.sleep(latency_secs)
        await params.result_callback(result)

    async def control_device(
        params: FunctionCallParams, device: str, action: str, value: str | None = None
    ):
        """Control a smart-home device or a phone setting: lights, lamps, thermostat, TV,
        speakers, locks, the garage door, dark mode, do-not-disturb, wifi.

        Args:
            device: The device or setting, e.g. "study lamp", "garage door", "dark mode".
            action: What to do: on, off, open, close, lock, unlock, set.
            value: Optional value for "set", e.g. "70 percent" or "21 degrees".
        """
        await _done(
            params,
            {"status": "ok", "device": device, "action": action, "value": value, "state": action},
        )

    async def manage_timers(
        params: FunctionCallParams,
        action: str,
        kind: str = "timer",
        when: str | None = None,
        label: str | None = None,
    ):
        """Set, list or cancel timers, alarms and reminders.

        Args:
            action: One of set, list, cancel, cancel_all.
            kind: One of timer, alarm, reminder.
            when: For set: a duration ("10 minutes") or a time ("7 am tomorrow").
            label: Optional label, e.g. "pasta" or "call the dentist".
        """
        if action == "list":
            result: dict[str, Any] = {
                "status": "ok",
                "active": [
                    {"kind": "timer", "label": "pasta", "remaining": "6 minutes"},
                    {"kind": "alarm", "label": "wake up", "time": "7:00 AM"},
                ],
            }
        elif action in ("cancel", "cancel_all"):
            result = {"status": "ok", "cancelled": 2 if action == "cancel_all" else 1, "kind": kind}
        else:
            result = {"status": "ok", "kind": kind, "when": when, "label": label, "id": "t-101"}
        await _done(params, result)

    async def calendar(
        params: FunctionCallParams,
        action: str,
        day: str | None = None,
        title: str | None = None,
        time: str | None = None,
        recurrence: str | None = None,
    ):
        """Read or add calendar events.

        Args:
            action: One of read, add.
            day: The day to read or add to, e.g. "today", "Friday", "next Wednesday".
            title: For add: the event title.
            time: For add: the start time, e.g. "10 am".
            recurrence: For add: optional, e.g. "every Wednesday".
        """
        if action == "add":
            result: dict[str, Any] = {
                "status": "ok",
                "added": {"title": title, "day": day, "time": time, "recurrence": recurrence},
            }
        else:
            result = {
                "status": "ok",
                "day": day or "today",
                "events": [
                    {"time": "9:30 AM", "title": "Team standup"},
                    {"time": "1:00 PM", "title": "Lunch with Sam"},
                    {"time": "4:00 PM", "title": "Dentist"},
                ],
            }
        await _done(params, result)

    async def send_message(
        params: FunctionCallParams, recipient: str, text: str, channel: str = "text"
    ):
        """Send a text message or email.

        Args:
            recipient: Who to send it to, e.g. "Alex".
            text: The message body.
            channel: Either text or email.
        """
        await _done(
            params,
            {"status": "sent", "recipient": recipient, "channel": channel, "chars": len(text)},
        )

    async def read_messages(params: FunctionCallParams, source: str = "email", limit: int = 3):
        """Read the user's unread messages or email.

        Args:
            source: Either email or text.
            limit: Maximum number of messages to return.
        """
        messages = [
            {"from": "Priya", "subject": "Lunch Thursday?", "preview": "Are you free at noon?"},
            {"from": "Bank", "subject": "Statement ready", "preview": "Your October statement."},
            {"from": "Sam", "subject": "Slides", "preview": "Sent the final slides, take a look."},
            {"from": "Mum", "subject": "Sunday", "preview": "Dinner at six on Sunday."},
        ]
        await _done(
            params,
            {
                "status": "ok",
                "source": source,
                "unread": len(messages),
                "messages": messages[:limit],
            },
        )

    async def play_media(
        params: FunctionCallParams, query: str, media_type: str = "music", action: str = "play"
    ):
        """Play, pause or skip music, podcasts and audiobooks.

        Args:
            query: What to play, e.g. "jazz", "the latest episode of Hardcore History".
            media_type: One of music, podcast, audiobook.
            action: One of play, pause, resume, next, stop.
        """
        await _done(
            params,
            {"status": "ok", "action": action, "now_playing": query, "media_type": media_type},
        )

    async def add_note(params: FunctionCallParams, text: str, list_name: str | None = None):
        """Save a note or add an item to a list such as groceries.

        Args:
            text: The note text or list item.
            list_name: Optional list name, e.g. "groceries".
        """
        await _done(params, {"status": "saved", "list": list_name or "notes", "text": text})

    async def lookup_info(params: FunctionCallParams, topic: str, query: str):
        """Look up live information.

        Args:
            topic: One of weather, sports, stocks, news, order_status, device_battery, traffic.
            query: What to look up, e.g. "Lakers game last night", "my Amazon order",
                "headphones", "commute to work".
        """
        canned: dict[str, dict[str, Any]] = {
            "weather": {"summary": "Partly cloudy", "high_c": 18, "low_c": 9, "rain_chance": "10%"},
            "sports": {"result": "Lakers 112, Nuggets 108", "final": True, "date": "last night"},
            "stocks": {"symbol": "the requested stock", "price_usd": 187.42, "change": "+0.8%"},
            "news": {"headlines": ["Markets edge higher", "New transit line opens downtown"]},
            "order_status": {"status": "shipped", "carrier": "UPS", "arrives": "Thursday"},
            "device_battery": {"battery_percent": 64, "charging": False},
            "traffic": {"delay_minutes": 12, "summary": "Moderate traffic, one slow stretch"},
        }
        data = canned.get(topic)
        if data is None:
            await _done(params, {"status": "not_found", "topic": topic, "query": query})
            return
        await _done(params, {"status": "ok", "topic": topic, "query": query, **data})

    return [
        control_device,
        manage_timers,
        calendar,
        send_message,
        read_messages,
        play_media,
        add_note,
        lookup_info,
    ]


def tool_schemas(tools: list[ToolFn]) -> list[dict[str, Any]]:
    out = []
    for fn in tools:
        s = DirectFunctionWrapper(fn).to_function_schema()
        out.append(
            {
                "name": s.name,
                "description": s.description,
                "properties": s.properties,
                "required": s.required,
            }
        )
    return out


def tool_names(tools: list[ToolFn] | None = None) -> list[str]:
    return [s["name"] for s in tool_schemas(tools or make_bench_tools())]


def bench_agent_fingerprint() -> str:
    """Short sha256 over the prompt, tool schemas and version."""
    payload = json.dumps(
        {
            "version": BENCH_AGENT_VERSION,
            "prompt": BENCH_SYSTEM_PROMPT,
            "tools": tool_schemas(make_bench_tools()),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


@dataclass
class BenchAgent:
    """What a variant gets: the shared prompt and tools, plus its own declared additions."""

    prompt: str
    tools: list[ToolFn]
    extra_instructions: str = ""

    @property
    def system_prompt(self) -> str:
        if not self.extra_instructions:
            return self.prompt
        return f"{self.prompt}\n\n{self.extra_instructions}"


def make_bench_agent(*, tool_latency_secs: float = 0.3, extra_instructions: str = "") -> BenchAgent:
    return BenchAgent(BENCH_SYSTEM_PROMPT, make_bench_tools(tool_latency_secs), extra_instructions)
