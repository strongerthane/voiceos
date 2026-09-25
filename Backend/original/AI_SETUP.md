# VoiceOS Hybrid AI — setup & usage

Install these in any order you like. **Commands and autonomous actions work with
ZERO configuration** — Ollama and API keys only power the answer tiers.

## It speaks.

Every response is spoken aloud with the built-in Windows voice (System.Speech —
no installs). Actions confirm out loud — *"Got it — I am opening this for
you…"* — and knowledge questions are answered with the spoken Ollama/API reply.
Disable with `--quiet` or `"tts": false` in ai_config.json. For the mic you
need one pip install:

```text
pip install SpeechRecognition sounddevice numpy
```

## 1. Local tier — Ollama (easy prompts, fast, private, free)

```text
install from https://ollama.com   then:
ollama pull llama3.2:3b
```

That's it — the router finds it at `http://localhost:11434` automatically.

## 2. API tier — any OpenAI-compatible endpoint (hard prompts)

Create `ai_config.json` in this folder:

```json
{
  "ollama_url": "http://localhost:11434",
  "ollama_model": "llama3.2:3b",
  "api_base_url": "https://int.api.nvidia.com/v1",
  "api_model": "meta/llama-3.1-8b-instruct",
  "api_key": "",
  "api_key_env": "VOICEOS_API_KEY",
  "tts": true
}
```

The API tier speaks the OpenAI schema (`/chat/completions` + `Bearer` key), so
ANY of these work by changing `api_base_url` + `api_model`:

| Provider   | api_base_url                    | example api_model            |
|------------|---------------------------------|------------------------------|
| OpenAI     | `https://api.openai.com/v1`      | `gpt-4o-mini`                |
| NVIDIA NIM | `https://int.api.nvidia.com/v1`  | `meta/llama-3.1-8b-instruct` |
| OpenRouter | `https://openrouter.ai/api/v1`   | any router model id          |
| Groq       | `https://api.groq.com/openai/v1` | `llama-3.1-8b-instant`      |
| Claude     | via any OpenAI-compatible endpoint/proxy speaking the OpenAI schema | provider-specific |

Keys are **never hardcoded**: set `api_key` in the file OR use one of these
environment variables (first match wins): `VOICEOS_API_KEY`, `OPENAI_API_KEY`,
`NVIDIA_API_KEY`, `NIM_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`.

## 3. What you can say — actions run autonomously, offline, instantly

| Say this | What happens |
|---|---|
| `open linkedin` / `launch notepad` | opens the site / app |
| `search for sailboats` | web search in the browser |
| `open youtube and play chess videos` | finds the actual video and opens IT |
| `play lofi beats` / `watch cat videos` | same, YouTube default |
| `open amazon and search for headsets` | site search on Amazon |
| `send email to bob about lunch saying see you at noon` | draft opens pre-filled — **you review it and press Send** |
| `create a game via claude code` | Claude Code builds it in `VoiceOS_Actions\` and tells you the result |
| `run command dir` | verified shell command through the verification engine |
| anything else | answered by Ollama (easy) or your API (hard), spoken aloud |

**The human is the last gate**: emails only ever open a draft; unknown names
open a search instead of guessing; Claude builds only files (no shell) in its
own folder.

### Teach it your own shortcuts

`voiceos_aliases.json` (same folder as the code):

```json
{
  "sites": {"mywiki": "https://mywiki.example", "uni": "https://portal.example.edu"},
  "apps": {"vscode": "code"}
}
```

`voiceos_contacts.json` — so `send email to bob` knows the address:

```json
{"bob": "bob@example.com", "mom": "mom@example.com"}
```

## 4. Run it (from Backend\original)

```text
python assistant.py --status              probe every tier + claude + tts
python assistant.py --open linkedin        opens LinkedIn in the browser now
python assistant.py --ask "why is the sky blue"     hard -> your API tier
python assistant.py --listen               one spoken prompt, spoken answer
python assistant.py --loop                 continuous voice session (say 'goodbye')
python assistant.py                        offline self-test (validates everything)
```

The desktop UI (`python ui_engine_final.py`) stays exactly as before — these
modules are the AI/action layer behind it.
