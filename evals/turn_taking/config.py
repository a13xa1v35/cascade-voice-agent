"""Full-Duplex-Bench run config: strict pydantic model, YAML loader, sample selection."""

from __future__ import annotations

import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from evals.turn_taking.agent import BENCH_AGENT_VERSION, bench_agent_fingerprint, tool_names
from evals.turn_taking.variants import VARIANTS
from hr_screener.config import Settings

BENCH_LANGUAGE = "en"  # FDB inputs are English; the agent language is fixed accordingly.

KNOWN_TASKS: dict[str, tuple[str, ...]] = {
    "v1": (
        "candor_pause_handling",
        "candor_turn_taking",
        "icc_backchannel",
        "synthetic_user_interruption",
        "synthetic_pause_handling",
    ),
    "v1.5": ("user_interruption", "user_backchannel", "talking_to_other", "background_speech"),
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskSelection(_Strict):
    n: int | None = Field(default=None, ge=1)
    ids: list[str] | None = None
    all: bool | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> TaskSelection:
        given = [self.n is not None, self.ids is not None, self.all is True]
        if sum(given) != 1:
            raise ValueError("specify exactly one of n, ids, all: true")
        return self


class Selection(_Strict):
    seed: int = 0
    from_manifest: str | None = None
    # Manifests whose samples must NOT be drawn again (a held-out set disjoint from the
    # samples a design was tuned on). Applies to `n` draws and `all`; explicit `ids` that
    # overlap them are an error.
    exclude_manifests: list[str] = Field(default_factory=list)
    tasks: dict[str, TaskSelection] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exclude_needs_a_draw(self) -> Selection:
        if self.exclude_manifests and self.from_manifest:
            raise ValueError("exclude_manifests can't be combined with from_manifest")
        return self

    @field_validator("tasks")
    @classmethod
    def _known_tasks(cls, tasks: dict[str, TaskSelection]) -> dict[str, TaskSelection]:
        for key in tasks:
            version, _, task = key.partition("/")
            if task not in KNOWN_TASKS.get(version, ()):
                raise ValueError(f"unknown task {key!r}; known: {known_task_keys()}")
        return tasks


class AgentConfig(_Strict):
    variant: str = "baseline"
    # Named param set of the variant (evals/turn_taking/designs.py: v1, v2, v3, production) that
    # variant_params starts from. Only for variants that have designs (system_one); name it
    # explicitly, an unnamed one is the first design (v1).
    design: str | None = None
    audio_profile: Literal["telephony", "web"] = "telephony"
    settings_overrides: dict[str, Any] = Field(default_factory=dict)
    # Merged over the variant's default params and validated (unknown key, locked key or wrong
    # type is an error). The merged dict is what runs and what the manifest records.
    variant_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("settings_overrides")
    @classmethod
    def _valid_overrides(cls, overrides: dict[str, Any]) -> dict[str, Any]:
        for key in overrides:
            if key == "language":
                raise ValueError("the bench language is fixed to en: FDB inputs are English")
            if key not in Settings.model_fields:
                raise ValueError(f"unknown Settings field {key!r}")
            if (
                key.endswith(("_api_key", "_auth_token", "_api_token"))
                or key == "cloudflare_account_id"
            ):
                raise ValueError(f"secret {key!r} must come from env_file, not the config")
        return overrides

    @model_validator(mode="after")
    def _valid_variant_params(self) -> AgentConfig:
        variant = VARIANTS.get(self.variant)
        if variant is None:
            return self  # unknown variant names are reported by the CLI
        variant.resolve_params(self.variant_params, design=self.design)  # raises ValueError
        return self


class RunConfig(_Strict):
    concurrency: int = Field(default=2, ge=1)
    trailing_silence_secs: float = Field(default=2.0, ge=0)
    clean_inputs: bool = True
    skip_existing: bool = True
    # AssemblyAI allows 5 new sessions per minute per account; stay one under so that
    # pipecat's own reconnects have headroom. Applies to every session incl. clean inputs.
    max_session_starts_per_minute: int = Field(default=4, ge=1)
    max_retries: int = Field(default=2, ge=0)  # rate-limited sessions only
    retry_wait_secs: float = Field(default=60.0, ge=0)
    tool_latency_secs: float = Field(default=0.3, ge=0)  # simulated latency of each mock tool


class JudgeConfig(_Strict):
    provider: str
    model: str


class EvalConfig(_Strict):
    device: str = "auto"
    metrics: Literal["local", "all"] = "local"
    judge: JudgeConfig = JudgeConfig(provider="anthropic", model="claude-sonnet-5-5")


class BenchConfig(_Strict):
    run_name: str
    data_root: str = "evals/turn_taking/data/fdb"
    env_file: str
    selection: Selection = Field(default_factory=Selection)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    run: RunConfig = Field(default_factory=RunConfig)
    eval: EvalConfig = Field(default_factory=EvalConfig)

    @field_validator("run_name")
    @classmethod
    def _safe_name(cls, name: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise ValueError("run_name may only contain letters, digits, '.', '_' and '-'")
        return name

    @model_validator(mode="after")
    def _need_samples(self) -> BenchConfig:
        if not self.selection.tasks and not self.selection.from_manifest:
            raise ValueError("selection needs tasks or from_manifest")
        return self


def known_task_keys() -> list[str]:
    return [f"{v}/{t}" for v, tasks in KNOWN_TASKS.items() for t in tasks]


def load_config(path: str | Path) -> BenchConfig:
    with Path(path).open() as f:
        raw = yaml.safe_load(f)
    return BenchConfig.model_validate(raw)


# --- Agent settings -----------------------------------------------------------------------


def resolve_settings(cfg: BenchConfig) -> Settings:
    """Settings from env_file, then overrides, then language forced to en."""
    values: dict[str, Any] = {**cfg.agent.settings_overrides, "language": BENCH_LANGUAGE}
    return Settings(_env_file=cfg.env_file, **values)


def agent_resolved(
    cfg: BenchConfig, settings: Settings, *, fake_classifier: bool = False
) -> dict[str, str]:
    """The non-secret settings actually used (never key values)."""
    voice = {
        "assemblyai": settings.assemblyai_voice_id or "(pipecat default)",
        "cartesia": settings.cartesia_voice_id,
        "elevenlabs": settings.elevenlabs_voice_id,
    }[settings.tts_provider]
    variant = VARIANTS.get(cfg.agent.variant)
    # Which named design a run used (only variants that have designs), recorded next to the
    # resolved params it expands to.
    design = (
        {"design": cfg.agent.design or variant.default_design or ""}
        if variant and variant.designs
        else {}
    )
    return {
        "stt_provider": settings.stt_provider,
        "tts_provider": settings.tts_provider,
        "anthropic_model": settings.anthropic_model,
        "language": settings.language,
        "voice_id": voice,
        "audio_profile": cfg.agent.audio_profile,
        "variant": cfg.agent.variant,
        **design,
        "bench_agent_version": BENCH_AGENT_VERSION,
        "bench_agent_fingerprint": bench_agent_fingerprint(),
        "tools": ",".join(tool_names()),
        "variant_extra_instructions": variant.extra_instructions if variant else "",
        "variant_params": json.dumps(
            variant.resolve_params(
                cfg.agent.variant_params, design=cfg.agent.design, fake_classifier=fake_classifier
            ),
            sort_keys=True,
        )
        if variant
        else "",
    }


# --- Selection -> manifest ----------------------------------------------------------------


def _natural_key(text: str) -> tuple[int, str]:
    return (int(text), text) if text.isdigit() else (10**12, text)


def list_ids(task_dir: Path) -> list[str]:
    if not task_dir.is_dir():
        raise FileNotFoundError(f"missing task folder: {task_dir}")
    return sorted((p.name for p in task_dir.iterdir() if p.is_dir()), key=_natural_key)


def select_samples(cfg: BenchConfig, base: Path | None = None) -> list[dict[str, str]]:
    """Deterministic selection: sorted ids, then a seeded random.sample per task."""
    base = base or Path.cwd()
    if cfg.selection.from_manifest:
        manifest = json.loads((base / cfg.selection.from_manifest).read_text())
        samples = [dict(s) for s in manifest["samples"]]
        for s in samples:
            if not (Path(s["source"]) / "input.wav").is_file():
                raise FileNotFoundError(f"manifest sample missing: {s['source']}")
        return samples
    root = (base / cfg.data_root).resolve()
    excluded: set[tuple[str, str, str]] = set()
    for path in cfg.selection.exclude_manifests:
        for s in json.loads((base / path).read_text())["samples"]:
            excluded.add((s["version"], s["task"], s["id"]))
    samples: list[dict[str, str]] = []
    for key, sel in cfg.selection.tasks.items():
        version, _, task = key.partition("/")
        task_dir = root / version / task
        all_ids = list_ids(task_dir)
        ids = [i for i in all_ids if (version, task, i) not in excluded]
        if sel.ids is not None:
            missing = [i for i in sel.ids if i not in all_ids]
            if missing:
                raise ValueError(f"{key}: ids not found: {missing}")
            overlap = [i for i in sel.ids if (version, task, i) in excluded]
            if overlap:
                raise ValueError(f"{key}: ids are in an excluded manifest: {overlap}")
            chosen = sorted(sel.ids, key=_natural_key)
        elif sel.n is not None:
            rng = random.Random(f"{cfg.selection.seed}/{key}")
            chosen = sorted(rng.sample(ids, min(sel.n, len(ids))), key=_natural_key)
        else:
            chosen = ids
        samples += [
            {"version": version, "task": task, "id": i, "source": str(task_dir / i)} for i in chosen
        ]
    return samples


def build_manifest(
    cfg: BenchConfig, samples: list[dict[str, str]], resolved: dict[str, str]
) -> dict[str, Any]:
    return {
        "run_name": cfg.run_name,
        "created_at": datetime.now(UTC).isoformat(),
        "language": resolved["language"],
        "agent_resolved": resolved,
        "config": cfg.model_dump(mode="json"),
        "samples": samples,
    }


def _sample_id(s: dict[str, str]) -> tuple[str, str, str]:
    return (s["version"], s["task"], s["id"])


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write the run manifest, keeping samples an earlier invocation already selected.

    A `--limit` / `--only` run, or a resume, must never shrink the manifest: stage 2
    scores and `from_manifest` pairs against it. Samples are unioned in a stable order.
    A different agent config under the same run_name is a mistake and is refused.
    """
    if path.exists():
        old = json.loads(path.read_text())
        if old.get("agent_resolved") != manifest["agent_resolved"]:
            raise SystemExit(f"{path} was written by a different agent config; use a new run_name")
        seen = {_sample_id(s) for s in old["samples"]}
        extra = [s for s in manifest["samples"] if _sample_id(s) not in seen]
        manifest = {**manifest, "created_at": old["created_at"]}
        manifest["samples"] = old["samples"] + extra
    path.write_text(json.dumps(manifest, indent=1))
