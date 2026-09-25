"""
VoiceOS Task Actions — deterministic intent parsing + autonomous execution.

Turns natural language into EXECUTED actions (not just "open a tab"):

    open youtube and play chess videos   -> deep-links the actual video
    play lofi beats                      -> same, via YouTube
    open amazon and search for headsets   -> Amazon search results page
    send email to bob about lunch        -> compose window (human presses Send!)
    send email to alice@x.com saying hi  -> pre-filled draft, still human-sent
    search for sailboats                 -> web search in the browser
    open linkedin / launch notepad       -> site / app aliases
    create a game via claude code        -> delegates the build to the Claude CLI
    run command <shell text>             -> verified through core + verify
    open notepad and write hello         -> opens app and executes action

Everything works OFFLINE with zero backends (deterministic grammar),
and every action is recorded through core.VoiceOSWorkflow so the
state/verification history the UI displays stays in sync.

Confirmation model ("the human is always the last gate"):
  * emails only open a DRAFT in the default mail client — never auto-sent;
  * unknown targets open a search instead of guessing;
  * arbitrary shell text requires the explicit phrase "run command …";
  * Claude Code delegation runs with file-only tools inside the dedicated
    VoiceOS_Actions folder — no shell, no network posts, results saved next
    to whatever it created.

Extensions (files next to this code, all optional):
    voiceos_aliases.json   {"sites": {...}, "apps": {...}}
    voiceos_contacts.json  {"bob": "bob@example.com", "mom": "..."}

Run `python task_actions.py` for the offline self-test.
"""

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# built-in aliases (user-extendable through voiceos_aliases.json)
# ---------------------------------------------------------------------------

SITE_ALIASES = {
    "linkedin": "https://www.linkedin.com",
    "linked in": "https://www.linkedin.com",
    "linkdin": "https://www.linkedin.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "google mail": "https://mail.google.com",
    "chatgpt": "https://chat.openai.com",
    "chat gpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "instagram": "https://www.instagram.com",
    "insta": "https://www.instagram.com",
    "x": "https://x.com",
    "twitter": "https://x.com",
    "whatsapp": "https://web.whatsapp.com",
    "reddit": "https://www.reddit.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
    "spotify": "https://open.spotify.com",
    "google": "https://www.google.com",
    "google drive": "https://drive.google.com",
    "drive": "https://drive.google.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "translate": "https://translate.google.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "wikipedia": "https://www.wikipedia.org",
    "nim": "https://build.nvidia.com",
}

APP_ALIASES = {
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "file explorer": "explorer",
    "explorer": "explorer",
    "files": "explorer",
    "file manager": "explorer",
    "terminal": "cmd",
    "cmd": "cmd",
    "command prompt": "cmd",
    "command line": "cmd",
    "settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "control panel": "control",
    "task manager": "taskmgr",
}

# search URLs for "open <site> and search <thing>" style compound intents
SITE_SEARCH_TEMPLATES = {
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "google": "https://www.google.com/search?q={q}",
    "amazon": "https://www.amazon.com/s?k={q}",
    "github": "https://github.com/search?q={q}",
    "reddit": "https://www.reddit.com/search/?q={q}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}",
    "netflix": "https://www.netflix.com/search?q={q}",
    "spotify": "https://open.spotify.com/search/{q}",
    "maps": "https://maps.google.com/?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
}

# requests worth delegating to the Claude Code CLI (artifact building);
# anything else ("write a poem") is answered by the AI tiers instead
CLAUDE_CREATE_HINTS = (
    "game", "app", "website", "web page", "webpage", "script", "program",
    "tool", "cli", "html", "css", "dashboard", "project", "file", "folder",
    "code", "landing page", "calculator", "tts", "story generator",
)

OPEN_VERBS = ("bring up", "pull up", "go to", "goto", "visit",
              "open", "launch", "start", "show")

URL_RE = re.compile(r"^(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?$", re.IGNORECASE)

# what the voice loop treats as "stop listening"
GOODBYE_PHRASES = ("goodbye", "good bye", "bye", "stop listening",
                   "stop", "exit", "quit", "that's all", "thats all")


def _alias_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "voiceos_aliases.json")


def _contacts_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "voiceos_contacts.json")


def load_aliases():
    sites = dict(SITE_ALIASES)
    apps = dict(APP_ALIASES)
    
    # Load user-configured aliases
    try:
        with open(_alias_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            for k, v in (data.get("sites") or {}).items():
                sites[str(k).lower()] = v
            for k, v in (data.get("apps") or {}).items():
                apps[str(k).lower()] = v
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as e:
        print(f"⚠️  Ignoring unreadable voiceos_aliases.json ({e})")
    
    # Auto-discover installed Windows applications
    try:
        from app_discovery import merge_discovered_apps
        apps = merge_discovered_apps(apps)
    except Exception as e:
        print(f"⚠️  App discovery unavailable ({e})")
    
    return sites, apps


def load_contacts() -> Dict[str, str]:
    """Name -> email address mapping from the user's voiceos_contacts.json."""
    try:
        with open(_contacts_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return {str(k).lower(): str(v) for k, v in data.items()}
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as e:
        print(f"⚠️  Ignoring unreadable voiceos_contacts.json ({e})")
    return {}


def looks_like_url(text: str) -> bool:
    return bool(URL_RE.match(text.strip()))


def claude_cli_available() -> bool:
    """True if the Claude Code CLI answers `claude --version`."""
    try:
        proc = subprocess.run(["claude", "--version"], shell=True,
                              capture_output=True, timeout=20)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _first_youtube_result(query: str, timeout: float = 8.0) -> str:
    """Deep-link the first video for a query; fall back to the search page."""
    search_url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
    try:
        req = urllib.request.Request(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", "ignore")
        m = re.search(r'"videoId":"([\w-]{11})"', html)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return search_url


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

class IntentParser:
    """Deterministic natural-language command parser (needs no model)."""

    def __init__(self, sites=None, apps=None, contacts=None):
        if sites and apps:
            self.sites, self.apps = sites, apps
        else:
            self.sites, self.apps = load_aliases()
        self.contacts = contacts if contacts is not None else load_contacts()

    @staticmethod
    def _normalize(target: str) -> str:
        target = re.sub(r"\s+", " ", target.lower().strip().strip(".,!?"))
        return re.sub(r"^(?:the|my|a|an)\s+", "", target)

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        """Return an intent dict, or None if the text is not command-like."""
        raw_text = " ".join(text.strip().split())
        t = " ".join(text.strip().lower().split())
        if not t:
            return None

        # Check for compound app actions first (e.g., "open notepad and write hello")
        try:
            from app_actions import AppActions
            app_actions = AppActions()
            compound = app_actions.parse_compound_action("", raw_text)
            if compound:
                return {
                    "action": "app_action",
                    "app": compound["app"],
                    "action_type": compound["action_type"],
                    "content": compound["content"]
                }
        except Exception:
            pass

        # explicit shell escape hatch — only this phrase runs raw commands
        m_run = re.match(r"^run command\s+(.+)$", t)
        if m_run:
            return {"action": "run_command", "command": m_run.group(1).strip()}

        # compound: "open youtube and play chess videos" / "queue X" / "watch X"
        m = re.match(r"^open\s+(?:youtube|yt)\s+(?:and\s+)?"
                     r"(?:play|queue|watch|find|show)\s+(.+)$", t)
        if m:
            return {"action": "youtube_play", "target": "youtube",
                    "query": m.group(1).strip()}
        m = re.match(r"^(?:play|watch|queue)\s+(.+?)\s+on\s+(?:youtube|yt)$", t)
        if m:
            return {"action": "youtube_play", "target": "youtube",
                    "query": m.group(1).strip()}
        m = re.match(r"^(?:play|watch)\s+(.+)$", t)
        if m:
            return {"action": "youtube_play", "target": "youtube",
                    "query": m.group(1).strip()}

        # compound: "open amazon and search for headsets"
        m = re.match(r"^(?:open|launch|start|go to|visit|show)\s+(.+?)\s+"
                     r"(?:and\s+)?(?:search(?:\s+for)?|find|look up|browse)\s+(.+)$", t)
        if m:
            site = self._normalize(m.group(1))
            if site in SITE_SEARCH_TEMPLATES:
                return {"action": "site_search", "site": site, "target": site,
                        "query": m.group(2).strip()}

        # email: compose a draft in the default mail client — human presses Send
        m = re.match(r"^(?:send|write|compose)\s+(?:an?\s+)?e-?mail\s+(?:to\s+)?"
                     r"(?P<to>.+?)"
                     r"(?:\s+about\s+(?P<subject>.+?))?"
                     r"(?:\s+saying\s+(?P<body>.+))?$", t)
        if m:
            raw_to = re.sub(r"^the\s+", "", m.group("to").strip())
            address = raw_to if "@" in raw_to \
                else self.contacts.get(self._normalize(raw_to), "")
            return {"action": "email", "target": raw_to, "address": address,
                    "subject": (m.group("subject") or "").strip(),
                    "body": (m.group("body") or "").strip()}

        # build/creation requests -> delegate to the Claude Code CLI
        m = re.match(r"^(?:create|make|build|generate|design|develop|fix)\s+"
                     r"(?P<what>.+?)"
                     r"(?:\s+(?:via|using|with)\s+claude(?:\s*code)?)?$", t)
        if m:
            what = m.group("what").strip()
            explicit = re.search(r"(?:via|using|with)\s+claude", t) is not None
            if explicit or any(h in what for h in CLAUDE_CREATE_HINTS):
                return {"action": "claude_create", "target": "claude code",
                        "request": what}
            # plain creative writing falls through to the AI answer tiers

        for verb in OPEN_VERBS:
            if t.startswith(verb + " "):
                target = t[len(verb):].strip()
                return self._resolve(self._normalize(target))

        m = re.match(r"^(?:run|execute)\s+(.+)$", t)
        if m:
            resolved = self._resolve(self._normalize(m.group(1)))
            if resolved.get("action") != "search":   # no alias -> don't guess
                return resolved
            return None                             # -> handled by the AI tiers

        m = re.match(r"^search(?:\s+for)?\s+(.+)$", t)
        if m:
            query = m.group(1).strip()
            return {"action": "search", "target": self._normalize(query),
                    "query": query, "fallback": False}

        return None

    def _resolve(self, target: str) -> Dict[str, Any]:
        # Check if it's an exact app match first
        if target in self.apps:
            return {"action": "open_app", "target": target, "appid": self.apps[target]}
        
        # Try fuzzy matching for apps
        try:
            from app_discovery import get_app_path
            app_path = get_app_path(target, self.apps)
            if app_path:
                return {"action": "open_app", "target": target, "appid": app_path}
        except Exception:
            pass
        
        # Check if it's a site
        if target in self.sites:
            return {"action": "open_url", "target": target, "url": self.sites[target]}
        
        # Check if it looks like a URL
        if looks_like_url(target):
            url = target if target.startswith("http") else f"https://{target}"
            return {"action": "open_url", "target": target, "url": url}
        
        # Unknown target: open a search and be transparent about it
        return {"action": "search", "target": target, "query": target, "fallback": True}

    def answer(self, prompt: str) -> str:
        """Plain-text offline answer used by HybridRouter when no model is up."""
        intent = self.parse(prompt)
        if intent:
            if intent["action"] in ("open_url", "open_app"):
                return f"Command recognized: open {intent.get('target', '')} — works offline."
            if intent["action"] == "search":
                return f"Search recognized for '{intent.get('query', '')}'."
            if intent["action"] == "run_command":
                return "Shell command recognized."
        return ("No AI backend is reachable. Command-style requests "
                "(e.g. 'open linkedin', 'launch notepad', 'open youtube and "
                "play chess videos', 'send email to …') still work offline.")


# ---------------------------------------------------------------------------
# executor
# ---------------------------------------------------------------------------

def _make_workflow():
    try:
        from core import VoiceOSWorkflow
        return VoiceOSWorkflow()
    except Exception as e:
        print(f"⚠️  Verification workflow unavailable ({e})")
        return None


def _actions_dir() -> str:
    """Dedicated folder for Claude-delegated artifacts: <repo>/VoiceOS_Actions."""
    return os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "VoiceOS_Actions"))


class TaskExecutor:
    """Executes parsed intents; records every action through the
    core/verify/state pipeline so the UI can display the result."""

    def __init__(self, workflow=None, dry_run: bool = False):
        self.workflow = workflow
        self.dry_run = dry_run
        self._seq = int(time.time() * 1000) % 10 ** 9

    def _ensure_workflow(self):
        if self.workflow is None:
            self.workflow = _make_workflow()   # may be None if core is missing
        return self.workflow

    def _next_task_id(self) -> str:
        self._seq += 1
        return f"voice_{self._seq}"

    def execute(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        action = intent.get("action")
        out: Dict[str, Any] = {"intent": intent, "action": action, "ok": False,
                               "detail": "", "verification": ""}
        try:
            if action == "app_action":
                app_name = intent.get("app", "")
                action_type = intent.get("action_type", "")
                content = intent.get("content", "")
                okk, detail = self._handle_app_action(app_name, action_type, content)
                out.update(ok=okk, verification="PASS" if okk else "FAIL", detail=detail)

            elif action == "open_url":
                url = intent["url"]
                if self.dry_run:
                    out.update(ok=True, detail=f"[dry-run] would open {url}",
                               verification="SKIPPED")
                else:
                    opened = webbrowser.open(url)
                    out.update(ok=bool(opened),
                               verification="PASS" if opened else "FAIL",
                               detail=(f"Got it — I am opening {intent['target']} for you."
                                      if opened else f"Browser refused to open {url}."))

            elif action == "open_app":
                appid = intent["appid"]
                app_name = intent.get("target", "app")
                if self.dry_run:
                    out.update(ok=True, detail=f"[dry-run] would launch {appid}",
                               verification="SKIPPED")
                else:
                    # Try to launch the app
                    proc = subprocess.run(f'start "" "{appid}"', shell=True, check=False)
                    okk = proc.returncode == 0
                    
                    if okk:
                        out.update(ok=True, verification="PASS",
                                   detail=f"Got it — I am launching {app_name} for you.")
                    else:
                        # Fallback: search for the app on the web if launch fails
                        from app_actions import AppActions
                        app_actions = AppActions()
                        fallback_url = app_actions.open_app_in_browser_fallback(app_name)
                        opened = webbrowser.open(fallback_url)
                        out.update(ok=bool(opened),
                                   verification="PASS" if opened else "FAIL",
                                   detail=(f"Could not launch '{app_name}' locally. "
                                          f"Opening a web search to download it instead."
                                          if opened else
                                          f"Could not launch '{app_name}' ({appid})."))


            elif action == "search":
                query = intent["query"]
                url = "https://duckduckgo.com/?q=" + quote_plus(query)
                msg = (f"No alias for '{intent['target']}' — opening a web search instead. "
                       "Add it to voiceos_aliases.json to open it directly."
                       if intent.get("fallback") else
                       f"Got it — I am searching the web for '{query}' for you.")
                if self.dry_run:
                    out.update(ok=True, detail=f"[dry-run] {msg}", verification="SKIPPED")
                else:
                    opened = webbrowser.open(url)
                    if opened:
                        out.update(ok=True, verification="PASS", detail=msg)
                    else:
                        out.update(ok=False, verification="FAIL",
                                   detail="Browser refused to open the search.")

            elif action == "site_search":
                site, query = intent.get("site", ""), intent["query"]
                template = SITE_SEARCH_TEMPLATES.get(site)
                if not template:
                    out.update(ok=False, verification="ERROR",
                               detail=f"No search template for '{site}'.")
                elif self.dry_run:
                    out.update(ok=True,
                               detail=f"[dry-run] would search {site} for '{query}'.",
                               verification="SKIPPED")
                else:
                    url = template.format(q=quote_plus(query))
                    opened = webbrowser.open(url)
                    out.update(ok=bool(opened),
                               verification="PASS" if opened else "FAIL",
                               detail=(f"Got it — I am showing you '{query}' on {site}."
                                      if opened else
                                      f"Browser refused to open the {site} search."))

            elif action == "youtube_play":
                query = intent["query"]
                if self.dry_run:
                    out.update(ok=True,
                               detail=f"[dry-run] would open YouTube and play '{query}'.",
                               verification="SKIPPED")
                else:
                    video_url = _first_youtube_result(query)
                    opened = webbrowser.open(video_url)
                    msg = (f"Got it — I am opening YouTube and playing "
                           f"'{query}' for you."
                           if "watch" in video_url else
                           f"Opening YouTube results for '{query}' — press play "
                           "on the one you like.")
                    out.update(ok=bool(opened),
                               verification="PASS" if opened else "FAIL",
                               detail=(msg if opened else "Could not open YouTube."))

            elif action == "email":
                address = intent.get("address", "")
                subject = intent.get("subject", "")
                body = intent.get("body", "")
                if not address:
                    out.update(ok=False, verification="ERROR",
                               detail=(f"I don't have an email address for "
                                       f"'{intent.get('target', 'them')}'. Say the full "
                                       "address, or add a contact in "
                                       "voiceos_contacts.json — then I'll draft it."))
                else:
                    mailto = f"mailto:{address}"
                    params = []
                    if subject:
                        params.append("subject=" + quote_plus(subject))
                    if body:
                        params.append("body=" + quote_plus(body))
                    if params:
                        mailto += "?" + "&".join(params)
                    if self.dry_run:
                        out.update(ok=True,
                                   detail=f"[dry-run] would open draft: {mailto}",
                                   verification="SKIPPED")
                    else:
                        opened = webbrowser.open(mailto)
                        out.update(ok=bool(opened),
                                   verification="PASS" if opened else "FAIL",
                                   detail=(("Got it — I've opened an email draft to "
                                            f"{address}"
                                            + (f" about '{subject}'" if subject else "")
                                            + ". Review it — it only sends when you "
                                              "press Send.")
                                           if opened else
                                           "Your mail client refused the draft."))

            elif action == "claude_create":
                request = intent.get("request", "")
                if self.dry_run:
                    out.update(ok=True,
                               detail=(f"[dry-run] would ask Claude Code to build: "
                                       f"{request}"),
                               verification="SKIPPED")
                else:
                    okk, detail = self._delegate_to_claude(request)
                    out.update(ok=okk, verification="PASS" if okk else "ERROR",
                               detail=detail)

            elif action == "run_command":
                # the ONLY path that runs raw shell text — via real verification
                okk, detail, status = self._run_verified_command(intent["command"])
                out.update(ok=okk, detail=detail, verification=status)

            elif action == "answer":
                out.update(ok=True, detail=str(intent.get("text", "")), verification="PASS")

            else:
                out.update(ok=False, detail=f"Unknown action: {action!r}",
                           verification="ERROR")

            if action != "run_command":        # run_command records itself
                self._record(intent, out)
        except Exception as e:
            out.update(ok=False, detail=f"Execution failed: {e}", verification="ERROR")
            if action != "run_command":
                self._record(intent, out)
        return out

    def _delegate_to_claude(self, request: str):
        """Hand a build request to the Claude Code CLI.

        Constrained: file tools only (no Bash, no network posts), working
        directory pinned to VoiceOS_Actions, prompt delivered over stdin.
        Whatever Claude creates lands in that folder together with a summary
        file; nothing outside it is touched.
        """
        actions_dir = _actions_dir()
        try:
            os.makedirs(actions_dir, exist_ok=True)
        except OSError as e:
            return False, f"Could not create the actions folder ({e})."
        prompt = ("Create one small, self-contained, working deliverable as "
                  "index.html (inline CSS and JS, no external dependencies, "
                  f"runs offline in a browser). Request: {request}")
        try:
            proc = subprocess.run(
                ["claude", "-p",
                 "--allowedTools", "Read",
                 "--allowedTools", "Write",
                 "--allowedTools", "Edit",
                 "--allowedTools", "Glob",
                 "--allowedTools", "Grep"],
                cwd=actions_dir,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=900,
                shell=True,          # Windows: resolves the claude.cmd shim
            )
        except (OSError, subprocess.SubprocessError) as e:
            return False, ("Claude Code CLI is not reachable — make sure `claude` is "
                           "installed and signed in, then try again "
                           f"({e}).")
        summary = (proc.stdout or "").strip()
        try:
            with open(os.path.join(actions_dir, "last_claude_result.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write(summary or "(no output)")
        except OSError:
            pass
        if proc.returncode != 0 or not summary:
            stderr = " ".join(((proc.stderr or "").strip())[:200].split())
            return False, (f"Claude Code could not complete that request. {stderr}")
        short = " ".join(summary.split())[:220]
        return True, ("Done — Claude Code finished your request. It says: "
                      f"{short} — the files are in the VoiceOS_Actions folder; "
                      "open it any time with 'open the actions folder'.")

    def _run_verified_command(self, command: str):
        if self.dry_run:
            return True, f"[dry-run] would run verified command '{command}'", "SKIPPED"
        wf = self._ensure_workflow()
        if wf is None:
            return False, "Verification workflow unavailable (core.py missing).", "ERROR"
        task_id = self._next_task_id()
        wf.add_task(task_id, description=f"VoiceOS command: {command}", command=command)
        wf.execute_task(task_id)
        status = str(wf.get_task_status(task_id)).upper()
        okk = status in ("PASS", "COMPLETED")
        return okk, f"Command '{command}' -> {status}", status

    def _handle_app_action(self, app_name: str, action_type: str, content: str) -> Tuple[bool, str]:
        """Handle compound app actions like 'open notepad and write hello'."""
        try:
            from app_discovery import get_app_path
            from app_actions import AppActions
            
            # Try to find the app
            app_path = get_app_path(app_name, {})
            if not app_path:
                # Fallback: search for the app online
                app_actions = AppActions()
                search_url = app_actions.open_app_in_browser_fallback(app_name)
                if webbrowser.open(search_url):
                    return True, (f"App '{app_name}' not found locally. Opening a web search "
                                f"to download it. You can then manually open it and {action_type} {content}")
                else:
                    return False, f"Could not find '{app_name}' or open a web search for it."
            
            app_actions = AppActions()
            
            # Execute the appropriate action
            if action_type == "write":
                success, detail = app_actions.execute_write_action(app_name, content, app_path)
                return success, detail
            
            elif action_type == "create":
                success, detail = app_actions.execute_create_action(app_name, content, app_path)
                return success, detail
            
            elif action_type == "calculate":
                # For calculator, just open it with the expression
                success, filepath = app_actions.save_text_locally(
                    f"Calculation: {content}",
                    f"{app_name}_calc",
                    "txt"
                )
                subprocess.run(f'start "" "{app_path}"', shell=True, check=False)
                return True, f"Opened {app_name}. Calculation saved: {content}. Saved to {filepath}"
            
            elif action_type == "search":
                # Open app and search in it
                subprocess.run(f'start "" "{app_path}"', shell=True, check=False)
                return True, f"Opened {app_name}. Ready to search for: {content}"
            
            else:
                return False, f"Unknown app action type: {action_type}"
        
        except Exception as e:
            return False, f"Error handling app action: {e}"

    def _record(self, intent: Dict[str, Any], out: Dict[str, Any]):
        """Mirror the action into the core/verify/state history for the UI."""
        wf = self._ensure_workflow()
        if wf is None:
            return
        try:
            from verify import command_succeeds
        except Exception:
            return
        label = intent.get("target") or intent.get("query") or intent.get("action", "action")
        task_id = self._next_task_id()
        status = "PASS" if out.get("ok") else "FAIL"
        try:
            wf.add_task(task_id, description=f"VoiceOS action: {label}", command="",
                        verification_config=command_succeeds(""))
            task = wf.tasks.get(task_id)
            task.update_status(status)
            task.update_verification_status({
                "status": out.get("verification") or status,
                "detail": out.get("detail", ""),
                "source": "voiceos_assistant",
            })
            wf.state.record_status(status)
        except Exception as e:
            print(f"⚠️  Could not record action in workflow state ({e})")


# ---------------------------------------------------------------------------
# offline self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    # Force UTF-8 on Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("VoiceOS Task Actions -- self-test (offline)")

    sites, apps = load_aliases()
    assert "linkedin" in sites and "notepad" in apps

    parser = IntentParser(sites, apps, contacts={})

    # --- base grammar -----------------------------------------------------
    intent = parser.parse("open linkedin")
    assert intent == {"action": "open_url", "target": "linkedin",
                      "url": "https://www.linkedin.com"}, intent
    intent = parser.parse("Launch the Calculator")
    assert intent["action"] == "open_app" and intent["appid"] == "calc", intent
    intent = parser.parse("run notepad")
    assert intent["action"] == "open_app" and intent["appid"] == "notepad", intent
    intent = parser.parse("open github.com")
    assert intent["action"] == "open_url" and intent["url"] == "https://github.com", intent
    intent = parser.parse("show me weather")             # unknown target
    assert intent["action"] == "search" and intent["fallback"] is True, intent
    intent = parser.parse("search for fuzzy otters")
    assert intent["action"] == "search" and intent["fallback"] is False, intent
    assert parser.parse("what is love") is None          # -> AI tiers
    assert parser.parse("www.github.com") is None        # no verb -> AI tiers
    intent = parser.parse("start discord")               # no alias -> search
    assert intent["action"] == "search" and intent["fallback"] is True, intent
    intent = parser.parse("run command echo hello")
    assert intent == {"action": "run_command", "command": "echo hello"}, intent
    intent = parser.parse("open the maps")
    assert intent["url"] == "https://maps.google.com", intent
    assert parser.answer("no ai backend question").startswith("No AI backend")
    assert "recognized" in parser.answer("open linkedin").lower()
    print("[OK] base grammar OK")

    # --- autonomous play / site search ------------------------------------
    intent = parser.parse("open youtube and play chess videos")
    assert intent["action"] == "youtube_play" and intent["query"] == "chess videos", intent
    intent = parser.parse("play lofi beats on youtube")
    assert intent["action"] == "youtube_play" and intent["query"] == "lofi beats", intent
    intent = parser.parse("watch cat videos")
    assert intent["action"] == "youtube_play" and intent["query"] == "cat videos", intent
    intent = parser.parse("open amazon and search for wireless headsets")
    assert intent["action"] == "site_search" and intent["site"] == "amazon", intent
    intent = parser.parse("open maps and search coffee shops")
    assert intent["action"] == "site_search" and intent["site"] == "maps", intent
    print("[OK] play/search compound intents OK")

    # --- email with contact lookup + human-send gate -----------------------
    parser.contacts = {"bob": "bob@example.com", "mom": "mom@example.com"}
    intent = parser.parse("send an email to bob about lunch saying see you at noon")
    assert intent["action"] == "email" and intent["address"] == "bob@example.com", intent
    assert intent["subject"] == "lunch" and intent["body"] == "see you at noon", intent
    intent = parser.parse("compose an email to alice@example.com")
    assert intent["action"] == "email" and intent["address"] == "alice@example.com", intent
    parser.contacts = {}
    intent = parser.parse("send email to bob")            # unknown contact
    assert intent["action"] == "email" and intent["address"] == "", intent
    print("[OK] email intents + contact lookup OK")

    # --- Claude Code delegation grammar -------------------------------------
    intent = parser.parse("create a game via claude code")
    assert intent["action"] == "claude_create" and intent["request"] == "a game", intent
    intent = parser.parse("build a snake game")
    assert intent["action"] == "claude_create" and intent["request"] == "a snake game", intent
    intent = parser.parse("write a poem about the sea")    # no artifact hint
    assert intent is None, intent
    print("[OK] Claude delegation grammar OK")

    # --- executor: dry run leaves no side effects ---------------------------
    ex = TaskExecutor(dry_run=True)
    res = ex.execute({"action": "open_url", "target": "linkedin",
                      "url": "https://www.linkedin.com"})
    assert res["ok"] and "[dry-run]" in res["detail"], res
    res = ex.execute({"action": "open_app", "target": "calc", "appid": "calc"})
    assert res["ok"], res
    res = ex.execute({"action": "search", "target": "zzz-bogus",
                      "query": "zzz-bogus", "fallback": True})
    assert res["ok"] and "alias" in res["detail"], res
    res = ex.execute({"action": "run_command", "command": "echo marker_123"})
    assert res["ok"] and res["verification"] == "SKIPPED", res
    res = ex.execute({"action": "nope"})
    assert res["ok"] is False, res
    res = ex.execute({"action": "youtube_play", "target": "youtube",
                      "query": "chess videos"})
    assert res["ok"] and "would open YouTube" in res["detail"], res
    res = ex.execute({"action": "site_search", "site": "amazon",
                      "target": "amazon", "query": "headsets"})
    assert res["ok"], res
    res = ex.execute({"action": "email", "target": "bob", "address": "",
                      "subject": "lunch", "body": "hi"})
    assert res["ok"] is False and "voiceos_contacts.json" in res["detail"], res
    res = ex.execute({"action": "email", "target": "alice",
                      "address": "alice@example.com",
                      "subject": "lunch", "body": "see you at noon"})
    assert res["ok"] and "mailto:alice@example.com" in res["detail"], res
    res = ex.execute({"action": "claude_create", "request": "a game"})
    assert res["ok"] and "would ask Claude Code" in res["detail"], res
    print("[OK] TaskExecutor dry-run actions OK (site_search/youtube/email/claude)")

    # --- executor: recording into the real workflow/state pipeline ----------
    wf = _make_workflow()
    assert wf is not None, "core.VoiceOSWorkflow must be importable here"
    ex2 = TaskExecutor(workflow=wf, dry_run=True)
    ex2.execute({"action": "open_url", "target": "linkedin", "url": "https://www.linkedin.com"})
    ex2.execute({"action": "answer", "text": "hello"})
    assert wf.state.status_counts.get("pass", 0) >= 2, wf.state.status_counts
    assert len(wf.tasks) >= 2
    print("[OK] action recording through core/state OK")

    # --- executor: a LIVE verified shell command (echo never fails) ---------
    ex3 = TaskExecutor(workflow=_make_workflow(), dry_run=False)
    res = ex3.execute({"action": "run_command", "command": "echo voiceos_live_marker"})
    assert res["ok"] and res["verification"] == "PASS", res
    assert "voiceos_live_marker" in res["detail"], res
    print("[OK] live verified command OK")

    print("[OK] task_actions self-test OK")
