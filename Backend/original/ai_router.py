"""
VoiceOS Hybrid AI Router
========================

Two-tier model routing — the "hybrid api local system":

    easy queries/tasks  -> LOCAL   (Ollama: fast, private, no key needed)
    hard queries        -> API     (any OpenAI-compatible endpoint)

The API tier is pure OpenAI schema (/chat/completions + Bearer key), so it
works unchanged with OpenAI, NVIDIA NIM, OpenRouter, Together, Groq, or
Claude through an OpenAI-compatible endpoint/proxy — just set
api_base_url + api_model + api_key.

If Ollama is down, command-like prompts still succeed fully OFFLINE via a
deterministic parser (task_actions.IntentParser) that never needs a model.

Zero pip dependencies: HTTP uses only the standard library (urllib), so
this module runs on a bare Python install.

Configuration (checked in this order):
    1. optional ai_config.json next to this file (see ai_config.example.json)
    2. environment variables:
         VOICEOS_OLLAMA_URL    VOICEOS_OLLAMA_MODEL
         VOICEOS_API_BASE      VOICEOS_API_MODEL
    API keys are NEVER hardcoded — they come from ai_config.json or from
    the first of these env vars that is set:
         VOICEOS_API_KEY, OPENAI_API_KEY, NVIDIA_API_KEY,
         NIM_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY

Run `python ai_router.py` for the offline self-test (no network needed).
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # local fast tier (Ollama daemon)
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3.2:3b",
    # remote strong tier (any OpenAI-compatible endpoint)
    "api_base_url": "https://int.api.nvidia.com/v1",   # NVIDIA NIM
    "api_model": "meta/llama-3.1-8b-instruct",
    "api_key": "",
    "api_key_env": "VOICEOS_API_KEY",
    # speak every answer/confirmation aloud (Windows System.Speech)
    "tts": True,
}

KNOWN_KEY_ENVARS = [
    "VOICEOS_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY",
    "NIM_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
]


def _config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_config.json")


def load_ai_config() -> Dict[str, Any]:
    """defaults <- optional ai_config.json <- environment overrides."""
    cfg = dict(DEFAULT_CONFIG)
    path = _config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        except (OSError, json.JSONDecodeError) as e:
            print(f"⚠️  Ignoring unreadable ai_config.json ({e})")
    for key in ("ollama_url", "ollama_model", "api_base_url", "api_model", "api_key"):
        env = os.environ.get(f"VOICEOS_{key.upper()}")
        if env:
            cfg[key] = env
    return cfg


def api_key_from(cfg: Dict[str, Any]) -> str:
    """API key from explicit config or env vars — never hardcoded."""
    if cfg.get("api_key"):
        return str(cfg["api_key"])
    for name in [cfg.get("api_key_env", "")] + KNOWN_KEY_ENVARS:
        value = os.environ.get(name or "")
        if value:
            return value
    return ""


# ---------------------------------------------------------------------------
# local tier — Ollama
# ---------------------------------------------------------------------------

class OllamaClient:
    """Client for the local Ollama daemon (stdlib urllib only)."""

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        self.cfg = cfg or load_ai_config()
        self.url = str(self.cfg.get("ollama_url", "http://localhost:11434")).rstrip("/")
        self.model = str(self.cfg.get("ollama_model", "llama3.2:3b"))

    def is_available(self, timeout: float = 2.0) -> bool:
        """True if the Ollama daemon answers on /api/tags."""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=timeout) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def list_models(self, timeout: float = 2.0) -> List[str]:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return [str(m.get("name", "?")) for m in data.get("models", [])]
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return []

    def generate(self, prompt: str, system: Optional[str] = None, timeout: float = 90) -> str:
        body = {
            "model": self.model,
            "messages": ([{"role": "system", "content": system}] if system else [])
                        + [{"role": "user", "content": prompt}],
            "stream": False,
        }
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data.get("message", {}).get("content", "")).strip()


# ---------------------------------------------------------------------------
# remote tier — any OpenAI-compatible endpoint
# ---------------------------------------------------------------------------

class OpenAICompatClient:
    """Client for any endpoint that speaks the OpenAI /chat/completions schema.

    Works out of the box with OpenAI, NVIDIA NIM, OpenRouter, Together,
    Groq, or Claude via an OpenAI-compatible endpoint/proxy.
    """

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        self.cfg = cfg or load_ai_config()
        self.base = str(self.cfg.get("api_base_url", "")).rstrip("/")
        self.model = str(self.cfg.get("api_model", ""))
        self.key = api_key_from(self.cfg)

    @property
    def is_configured(self) -> bool:
        return bool(self.base and self.model and self.key)

    def generate(self, prompt: str, system: Optional[str] = None, timeout: float = 120) -> str:
        if not self.is_configured:
            raise RuntimeError("API tier not configured (set api_base_url, api_model and a key)")
        messages = ([{"role": "system", "content": system}] if system else []) \
                   + [{"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": messages, "temperature": 0.4}
        req = urllib.request.Request(
            f"{self.base}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data["choices"][0]["message"]["content"]).strip()


# ---------------------------------------------------------------------------
# difficulty split + router
# ---------------------------------------------------------------------------

HARD_MARKERS = (
    "why", "how do i", "how to", "explain", "summar", "write", "translate",
    "compare", "analyze", "research", "recommend", "difference", "essay",
    "code", "refactor", "debug", "pros and cons", "plan", "describe",
    "give me", "list of", "history", "meaning",
)


def classify_difficulty(prompt: str) -> str:
    """Rule-based split: command-like/trivial -> 'easy', else -> 'hard'."""
    p = " ".join(prompt.strip().lower().split())
    if not p:
        return "easy"
    if len(p.split()) <= 2:
        return "easy"
    if any(m in p for m in HARD_MARKERS):
        return "hard"
    if "?" in prompt or len(p.split()) >= 8:
        return "hard"
    return "easy"


class HybridRouter:
    """Pick local-first for easy prompts, escalate to the API for hard ones,
    degrade to the deterministic offline parser when a tier is missing."""

    def __init__(self,
                 local: Optional[OllamaClient] = None,
                 remote: Optional[OpenAICompatClient] = None,
                 offline_parser: Any = None):
        self.local = local or OllamaClient()
        self.remote = remote or OpenAICompatClient()
        self.offline_parser = offline_parser
        self.last_decision: Dict[str, Any] = {}

    def route(self, prompt: str) -> str:
        """Return 'local' | 'api' | 'offline'."""
        difficulty = classify_difficulty(prompt)
        local_up = self.local.is_available()
        api_set = self.remote.is_configured
        if difficulty == "easy":
            plan = "local" if local_up else "offline"
        else:
            plan = "api" if api_set else ("local" if local_up else "offline")
        self.last_decision = {
            "difficulty": difficulty,
            "ollama_up": local_up,
            "api_configured": api_set,
            "plan": plan,
        }
        return plan

    def decision(self) -> Dict[str, Any]:
        return dict(self.last_decision or {})

    def ask(self, prompt: str, system: Optional[str] = None) -> Dict[str, Any]:
        """Answer a prompt with the best tier available, with fallbacks."""
        plan = self.route(prompt)
        started = time.time()

        def result(text: str, source: str, model: str) -> Dict[str, Any]:
            return {
                "text": text,
                "source": source,
                "model": model,
                "plan": plan,
                "decision": self.decision(),
                "duration": round(time.time() - started, 2),
            }

        if plan == "api":
            try:
                return result(self.remote.generate(prompt, system), "api", self.remote.model)
            except Exception as e:                      # network/model/quota problems
                print(f"⚠️  API tier failed ({e}) — falling back to local")
                plan = "local"

        if plan == "local":
            try:
                return result(self.local.generate(prompt, system), "local", self.local.model)
            except Exception as e:
                print(f"⚠️  Local tier failed ({e}) — falling back to offline parser")

        if self.offline_parser is not None:
            try:
                return result(self.offline_parser.answer(prompt), "offline", "deterministic-parser")
            except Exception as e:
                print(f"⚠️  Offline parser failed ({e})")
        return result("", "unavailable", "none")


# ---------------------------------------------------------------------------
# offline self-test — no network needed
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("VoiceOS Hybrid AI Router — self-test (offline)")

    # difficulty classifier
    assert classify_difficulty("open linkedin") == "easy"
    assert classify_difficulty("play spotify") == "easy"
    assert classify_difficulty("why does tkinter crash when bg is used on ttk widgets?") == "hard"
    assert classify_difficulty("explain how transformers work and compare them to rnn models") == "hard"
    print("✓ difficulty classifier OK")

    # config: env override wins over defaults
    os.environ["VOICEOS_OLLAMA_MODEL"] = "test-model:tiny"
    try:
        cfg = load_ai_config()
        assert cfg["ollama_model"] == "test-model:tiny"
    finally:
        del os.environ["VOICEOS_OLLAMA_MODEL"]
    print("✓ config defaults + env override OK")

    # an unreachable Ollama must fail fast and quietly
    dead = OllamaClient({"ollama_url": "http://127.0.0.1:9", "ollama_model": "x"})
    assert dead.is_available(timeout=0.5) is False
    assert dead.list_models(timeout=0.5) == []
    print("✓ unreachable Ollama handled gracefully")

    # API tier configuration gating + key lookup from env
    blank = OpenAICompatClient({"api_base_url": "", "api_model": "m", "api_key": ""})
    assert blank.is_configured is False
    os.environ["VOICEOS_API_KEY"] = "test-key"
    try:
        env_keyed = OpenAICompatClient({"api_base_url": "http://x/v1", "api_model": "m"})
        assert env_keyed.is_configured is True
    finally:
        del os.environ["VOICEOS_API_KEY"]
    print("✓ API tier configuration gating + env key lookup OK")

    class FakeLocal:
        model = "fake-local-model"

        def is_available(self, timeout: float = 2.0) -> bool:
            return True

        def generate(self, prompt: str, system: Optional[str] = None) -> str:
            return f"local answer to: {prompt}"

    class OfflineStub:
        def answer(self, prompt: str) -> str:
            return f"offline answer to: {prompt}"

    # easy -> local, hard -> local when API is unconfigured
    r_local = HybridRouter(local=FakeLocal(), remote=blank, offline_parser=OfflineStub())
    assert r_local.route("open mail") == "local"
    assert r_local.route("explain the trade tariffs situation in detail carefully now") == "local"
    ans = r_local.ask("open mail")
    assert ans["source"] == "local" and ans["model"] == "fake-local-model"
    assert ans["plan"] == "local" and ans["duration"] >= 0
    print("✓ easy/hard routing with no API configured OK")

    # hard -> api when configured (no call is made: only routing decisions tested)
    r_api = HybridRouter(local=FakeLocal(),
                         remote=OpenAICompatClient({"api_base_url": "http://x/v1",
                                                    "api_model": "strong-model",
                                                    "api_key": "k"}),
                         offline_parser=OfflineStub())
    assert r_api.route("open mail") == "local"              # easy stays local
    assert r_api.route("explain why the sky is blue and how scattering works") == "api"
    assert r_api.decision()["difficulty"] == "hard"
    assert r_api.decision()["plan"] == "api"
    print("✓ hard prompts escalate to the API tier OK")

    # nothing configured/reachable -> offline parser for both difficulties
    r_off = HybridRouter(local=dead, remote=blank, offline_parser=OfflineStub())
    assert r_off.route("open notepad") == "offline"
    assert r_off.route("explain quantum tunneling at length today") == "offline"
    ans = r_off.ask("open notepad")
    assert ans["source"] == "offline" and ans["text"].startswith("offline answer")
    assert r_off.decision()["ollama_up"] is False and r_off.decision()["api_configured"] is False
    print("✓ offline degradation OK")

    print("✓ ai_router self-test OK")
