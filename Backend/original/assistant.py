#!/usr/bin/env python3
"""
VoiceOS Assistant — the single entry point of the hybrid AI system.

Pipeline for every input text (typed or spoken):

    text ──► IntentParser (deterministic, instant, offline)
    │         └ action found? execute it autonomously:
    │             open site/app · search web · deep-link a YouTube video ·
    │             site searches · email DRAFT (you press Send) ·
    │             'run command …' (verified) · builds via Claude Code
    └ not command-like? ─► HybridRouter
              ├ easy  → Ollama (local, fast)
              ├ hard  → OpenAI-compatible API (NIM / OpenAI / OpenRouter /
              │         Groq / Claude via an OpenAI-compat endpoint)
              └ none reachable → offline parser text
    All answers and action confirmations are SPOKEN via Windows TTS
    (System.Speech, zero install) unless disabled (--quiet or tts:false).

Command line:
    python assistant.py                          # offline self-test
    python assistant.py --open linkedin          # direct action, no AI needed
    python assistant.py --ask "your prompt"      # full hybrid pipeline
    python assistant.py --listen                 # one utterance, then answer
    python assistant.py --loop                   # continuous voice session
    python assistant.py --status                 # probe every tier/action
    Flags: --speak force TTS · --quiet silence TTS · --help

Configuration: ai_config.json (template in AI_SETUP.md) or environment
variables — see ai_router.py header for the full list.
"""

import argparse
from typing import Any, Dict, Optional

from ai_router import HybridRouter, OllamaClient, OpenAICompatClient, load_ai_config
from task_actions import GOODBYE_PHRASES, IntentParser, TaskExecutor, claude_cli_available


class VoiceAssistant:
    """text in -> executed action or spoken AI answer, recorded and verified."""

    def __init__(self, tts: Optional[bool] = None):
        self.config = load_ai_config()
        self.parser = IntentParser()
        self.executor = TaskExecutor()
        self.router = HybridRouter(offline_parser=self.parser)
        # None -> follow config (default: speak); True/False force it
        self.tts = bool(self.config.get("tts", True)) if tts is None else bool(tts)

    # ------------------------------------------------------------------
    def handle(self, text: str) -> Dict[str, Any]:
        """The full pipeline. Returns a result dict with ok/detail/path/…."""
        if not text or not text.strip():
            return {"ok": False, "detail": "Empty input.", "path": "none"}

        # 1) deterministic commands win — instant, no model required
        intent = self.parser.parse(text)
        if intent is not None:
            if intent.get("action") == "claude_create":
                self._speak("Got it — I am handing that to Claude Code now. "
                            "It may take a minute; I'll tell you when it's done.")
            result = self.executor.execute(intent)
            result["path"] = "deterministic"
            self._speak(result.get("detail", ""))
            return result

        # 2) otherwise — hybrid AI tiers
        answer = self.router.ask(text)
        model_text = answer.get("text", "")

        # did the model itself name a whitelisted command? then execute it
        follow = self.parser.parse(model_text) if model_text else None
        if follow is not None:
            result = self.executor.execute(follow)
            result["path"] = f"ai-suggested ({answer.get('source')})"
            result["answer"] = model_text
            self._speak(result.get("detail", ""))
            return result

        result = self.executor.execute({"action": "answer", "text": model_text})
        result["path"] = f"ai ({answer.get('source')})"
        result["model"] = answer.get("model")
        result["plan"] = answer.get("plan")
        self._speak(model_text)
        return result

    # ------------------------------------------------------------------
    def _speak(self, text: str):
        if not (self.tts and text):
            return
        try:
            from voice_io import say
            say(str(text)[:400])
        except Exception as e:
            print(f"🔊 TTS unavailable ({e})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_status(ast_: VoiceAssistant) -> int:
    loc: OllamaClient = ast_.router.local
    rem: OpenAICompatClient = ast_.router.remote
    print("VoiceOS hybrid AI — status")
    print(f"  local tier  : {loc.url}  (model '{loc.model}')")
    up = loc.is_available()
    print(f"    reachable : {'YES' if up else 'NO'}")
    if up:
        models = loc.list_models()
        print(f"    models    : {', '.join(models) if models else '(none installed)'}")
    print(f"  api tier    : {rem.base or '(unset)'}  (model '{rem.model or '(unset)'}')")
    print(f"    api key   : {'set' if rem.key else 'NOT set'}")
    print(f"  claude cli  : {'available' if claude_cli_available() else 'not found on PATH'}"
          "  (enables 'create … via claude code')")
    print(f"  aliases     : {len(ast_.parser.sites)} sites, {len(ast_.parser.apps)} apps "
          "(extend via voiceos_aliases.json)")
    print(f"  contacts    : {len(ast_.parser.contacts)} "
          "(add emails via voiceos_contacts.json)")
    print(f"  tts         : {'ON' if ast_.tts else 'off'} (System.Speech)")
    print("  routing     : easy -> local Ollama · hard -> API · everyday actions "
          "run deterministically offline")
    if not up and not rem.is_configured:
        print("  note        : no AI backend ready — commands still work "
              "deterministically; set up Ollama (ollama pull llama3.2:3b) "
              "or fill ai_config.json for AI answers.")
    return 0


def _cmd_open(ast_: VoiceAssistant, what: str) -> int:
    intent = ast_.parser.parse(f"open {what}")
    if intent is None:
        intent = {"action": "search", "target": what, "query": what, "fallback": False}
    res = ast_.executor.execute(intent)
    print(res["detail"])
    return 0 if res["ok"] else 1


def _cmd_ask(ast_: VoiceAssistant, prompt: str) -> int:
    res = ast_.handle(prompt)
    print(f"[path: {res.get('path')}]")
    if res.get("detail"):
        print(res["detail"])
    return 0 if res.get("ok") else 1


def _cmd_listen(ast_: VoiceAssistant) -> int:
    from voice_io import listen
    print("🎤 Say something…")
    text = listen()
    if not text:
        print("Nothing captured.")
        return 1
    return _cmd_ask(ast_, text)


def _cmd_loop(ast_: VoiceAssistant) -> int:
    from voice_io import listen
    print("🎤 Voice session running — say a command or ask anything "
          "(say 'goodbye' to stop).")
    while True:
        try:
            text = listen()
        except KeyboardInterrupt:
            print("Stopped.")
            return 0
        if not text:
            continue
        if " ".join(text.strip().lower().split()) in GOODBYE_PHRASES:
            ast_._speak("Goodbye! Voice session stopped.")
            print("Voice session stopped.")
            return 0
        _cmd_ask(ast_, text)


# ---------------------------------------------------------------------------
# offline self-test — run with no arguments
# ---------------------------------------------------------------------------

def _selftest() -> int:
    import sys
    # Force UTF-8 on Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("VoiceOS Assistant -- self-test (offline)")

    a = VoiceAssistant(tts=False)                  # never speak during tests
    a.executor.dry_run = True                     # never open anything real
    # force deterministic offline routing for the test
    a.router.local = OllamaClient({"ollama_url": "http://127.0.0.1:9", "ollama_model": "x"})
    a.router.remote = OpenAICompatClient({"api_base_url": "", "api_model": "",
                                          "api_key": ""})

    # deterministic path: parser catches the command instantly
    res = a.handle("open the linkedin")
    assert res["path"] == "deterministic" and res["ok"], res
    assert "linkedin.com" in res["detail"], res
    print("[OK] 'open the linkedin' -> deterministic open OK")

    # compound autonomous action
    res = a.handle("open youtube and play chess videos")
    assert res["path"] == "deterministic" and res["ok"], res
    assert "[dry-run]" in res["detail"] and "YouTube" in res["detail"], res
    print("[OK] 'open youtube and play chess videos' -> youtube_play intent OK")

    # email grammar through the full pipeline (unknown contact -> honest ask)
    res = a.handle("send email to bob about lunch")
    assert res["path"] == "deterministic" and res["ok"] is False, res
    assert "voiceos_contacts.json" in res["detail"], res
    print("[OK] email without a known contact -> asks for the address OK")

    # Claude delegation grammar (dry run — never invokes the CLI here)
    res = a.handle("create a game via claude code")
    assert res["path"] == "deterministic" and res["ok"], res
    assert "would ask Claude Code" in res["detail"], res
    print("[OK] 'create a game via claude code' -> claude_create intent OK")

    # non-commands fall to the AI tiers; with none reachable, degrade cleanly
    res = a.handle("what is the capital of france")
    assert res["path"] == "ai (offline)", res
    assert res["ok"] and "No AI backend" in res["detail"], res
    print("[OK] knowledge question without backends -> clean offline answer OK")

    # unknown command target -> transparent search fallback
    res = a.handle("open zzz-bogus-thing")
    assert res["path"] == "deterministic" and "voiceos_aliases.json" in res["detail"], res
    print("[OK] unknown target -> search fallback with alias hint OK")

    # actions land in the verification history the UI reads
    a.handle("open youtube")
    wf = a.executor.workflow
    assert wf is not None and wf.state.status_counts.get("pass", 0) >= 5, \
        (wf.state.status_counts if wf else "no workflow")
    assert len(wf.tasks) >= 6
    print("[OK] actions recorded in core/state verification history OK")

    print("[OK] assistant self-test OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="VoiceOS hybrid AI assistant")
    p.add_argument("--open", metavar="THING", help="open a site/app alias directly (no AI needed)")
    p.add_argument("--ask", metavar="PROMPT", help="send a prompt through the hybrid pipeline")
    p.add_argument("--listen", action="store_true", help="capture one utterance from the mic")
    p.add_argument("--loop", action="store_true", help="continuous voice session (say 'goodbye' to stop)")
    p.add_argument("--status", action="store_true", help="probe every tier and action")
    p.add_argument("--speak", action="store_true", help="force speaking responses aloud")
    p.add_argument("--quiet", action="store_true", help="disable speaking responses aloud")
    args = p.parse_args()

    if args.status:
        return _cmd_status(VoiceAssistant())

    if args.quiet:
        tts = False
    elif args.speak or args.listen or args.loop:
        tts = True
    else:
        tts = None            # follow config (default: ON)
    ast_ = VoiceAssistant(tts=tts)

    if args.open:
        return _cmd_open(ast_, args.open)
    if args.ask:
        return _cmd_ask(ast_, args.ask)
    if args.listen:
        return _cmd_listen(ast_)
    if args.loop:
        return _cmd_loop(ast_)
    return _selftest()


if __name__ == "__main__":
    raise SystemExit(main())
