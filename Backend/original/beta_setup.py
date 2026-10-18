"""A short, optional first-run setup for the Windows beta."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlsplit

from ai_router import load_ai_config
from secure_store import save_api_key
from user_paths import user_dir


def save_settings(config, key=None):
    # Keys are encrypted separately, never serialized with the public settings.
    data = {k: v for k, v in config.items() if k != 'api_key'}
    folder = user_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if key is not None:
        save_api_key(key)
    temporary = folder / 'ai_config.tmp'
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(folder / 'ai_config.json')
    (folder / 'setup-complete').touch()


def show_setup() -> bool:
    from native_glass import enable_dpi_awareness
    enable_dpi_awareness()
    cfg = load_ai_config()
    root = tk.Tk()
    root.title('VoiceOS · Setup')
    root.configure(bg='#08090d')
    root.resizable(False, False)
    width, height = 620, min(740, root.winfo_screenheight() - 80)
    root.geometry(f'{width}x{height}+{(root.winfo_screenwidth()-width)//2}+{max(16,(root.winfo_screenheight()-height)//2)}')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 10), background='#08090d', foreground='#f4f6fb')
    style.configure('TEntry', fieldbackground='#171a22', foreground='#f4f6fb', padding=7, insertcolor='#f4f6fb')
    style.configure('TCombobox', fieldbackground='#171a22', background='#252935', foreground='#f4f6fb', padding=6)
    style.map('TCombobox', fieldbackground=[('readonly', '#171a22')], foreground=[('readonly', '#f4f6fb')])
    style.configure('TButton', padding=(16, 9), background='#252935', foreground='#f4f6fb', borderwidth=0)
    style.map('TButton', background=[('active', '#363b49')])
    style.configure('Primary.TButton', background='#eef0fa', foreground='#10121a')
    style.map('Primary.TButton', background=[('active', '#d9dcf2')])
    style.configure('TCheckbutton', background='#08090d', foreground='#c3c9d4')
    style.map('TCheckbutton', background=[('active', '#08090d')])
    root.option_add('*TCombobox*Listbox.background', '#171a22')
    root.option_add('*TCombobox*Listbox.foreground', '#f4f6fb')

    # Scroll on smaller laptop screens; the actions remain visible below.
    footer = ttk.Frame(root, padding=(28, 12, 28, 20))
    footer.pack(side='bottom', fill='x')
    canvas = tk.Canvas(root, bg='#08090d', highlightthickness=0)
    scroll = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
    scroll.pack(side='right', fill='y')
    canvas.pack(fill='both', expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    frame = ttk.Frame(canvas, padding=(28, 26, 28, 10))
    window = canvas.create_window(0, 0, window=frame, anchor='nw')
    frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
    root.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-int(e.delta/120), 'units'))

    def label(text, size=10, color='#c3c9d4', pady=(0, 6)):
        tk.Label(frame, text=text, bg='#08090d', fg=color, font=('Segoe UI', size),
                 anchor='w', justify='left', wraplength=530).pack(fill='x', pady=pady)

    label('Your desktop, by voice.', 25, '#f4f6fb')
    label('Start with “open YouTube” or “open Notepad”.\nAI answers are optional. No account is needed to try commands.', pady=(0, 22))
    label('Microphone', 12, '#f4f6fb')
    devices = [('Windows default microphone', None)]
    try:
        from voice_io import list_input_devices
        devices.extend((f"{d['name']} [{d['index']}]", d['index']) for d in list_input_devices())
    except Exception:
        label('No microphone found. Enable desktop microphone access in Windows Settings. Typed commands still work.')
    selected = next((i for i, (_, value) in enumerate(devices) if value == cfg.get('input_device')), 0)
    mic = ttk.Combobox(frame, values=[name for name, _ in devices], state='readonly')
    mic.current(selected)
    mic.pack(fill='x')
    events = queue.Queue()
    status = tk.StringVar(value='Test records two seconds locally. It does not upload or save audio.')
    def test_microphone():
        test.configure(state='disabled')
        status.set('Listening for two seconds…')
        device = devices[mic.current()][1]
        def worker():
            try:
                from voice_io import record_audio_data
                audio = record_audio_data(2, device=device)
                events.put(('Microphone ready. Speak after clicking the bar.', bool(audio.frame_data)))
            except Exception:
                events.put(('Could not record. Choose another microphone or enable Windows microphone access.', False))
        threading.Thread(target=worker, daemon=True).start()
    test = ttk.Button(frame, text='Test microphone', command=test_microphone)
    test.pack(anchor='w', pady=(10, 5))
    tk.Label(frame, textvariable=status, wraplength=530, justify='left', anchor='w',
             font=('Segoe UI', 9), bg='#08090d', fg='#c3c9d4').pack(fill='x', pady=(0, 20))
    def poll():
        try:
            message, ok = events.get_nowait()
            status.set(message)
            test.configure(state='normal')
        except queue.Empty:
            pass
        root.after(100, poll)
    root.after(100, poll)

    label('AI answers · optional', 12, '#f4f6fb')
    mode = ttk.Combobox(frame, state='readonly', values=['Start with commands', 'Ollama on this laptop', 'Cloud API'])
    initial_mode = cfg.get('ai_mode', 'cloud' if cfg.get('api_key') else 'commands')
    mode.current({'commands': 0, 'local': 1, 'cloud': 2}.get(initial_mode, 0))
    mode.pack(fill='x', pady=(0, 8))
    local = ttk.Frame(frame)
    cloud = ttk.Frame(frame)
    def field(parent, text, initial, secret=False):
        ttk.Label(parent, text=text).pack(anchor='w', pady=(6, 3))
        value = tk.StringVar(value=initial)
        entry = ttk.Entry(parent, textvariable=value, show='•' if secret else '')
        entry.pack(fill='x')
        return value
    ollama_model = field(local, 'Installed Ollama model', cfg['ollama_model'])
    ttk.Label(local, text='Ollama must be installed and running. Model download is separate.').pack(anchor='w', pady=(5, 10))
    api_url = field(cloud, 'OpenAI-compatible API URL', cfg['api_base_url'])
    api_model = field(cloud, 'Model', cfg['api_model'])
    key = field(cloud, 'API key · encrypted for your Windows account', '', secret=True)
    if cfg.get('api_key'):
        ttk.Label(cloud, text='Leave the key blank to keep the existing key.').pack(anchor='w', pady=(5, 0))
    # Insertion before this anchor keeps disclosure and actions below the fields.
    disclosure = ttk.Frame(frame)
    disclosure.pack(fill='x', pady=(18, 0))
    tts = tk.BooleanVar(value=cfg.get('tts', True))
    ttk.Checkbutton(disclosure, text='Speak responses with the Windows voice', variable=tts).pack(anchor='w')
    tk.Label(disclosure, text='Voice recognition uses Google’s online speech service. AI questions use your selected provider. Typed commands work without speech recognition.\n\nClick the bar to speak · Ctrl+T to type · Ctrl+, for settings · Esc to quit',
             bg='#08090d', fg='#c3c9d4', font=('Segoe UI', 9), wraplength=530, justify='left').pack(fill='x', pady=(10, 0))
    def change_mode(_=None):
        local.pack_forget()
        cloud.pack_forget()
        target = local if mode.current() == 1 else cloud if mode.current() == 2 else None
        if target:
            target.pack(fill='x', before=disclosure)
    mode.bind('<<ComboboxSelected>>', change_mode)
    change_mode()
    accepted = [False]
    error = tk.StringVar()
    tk.Label(footer, textvariable=error, bg='#08090d', fg='#ff8a99', wraplength=530, justify='left').pack(fill='x', pady=(0, 8))
    buttons = ttk.Frame(footer)
    buttons.pack(fill='x')
    def finish():
        updated = dict(cfg)
        updated.update(input_device=devices[mic.current()][1], tts=tts.get(),
                       ai_mode=('commands', 'local', 'cloud')[mode.current()])
        updated.pop('api_key', None)
        if mode.current() == 1:
            if not ollama_model.get().strip():
                error.set('Enter a model installed in Ollama, or choose Start with commands.')
                return
            updated['ollama_model'] = ollama_model.get().strip()
        if mode.current() == 2:
            parsed = urlsplit(api_url.get().strip())
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                error.set('Enter an HTTPS API URL without a username, password, or query string.')
                return
            if not api_model.get().strip() or not (key.get().strip() or cfg.get('api_key')):
                error.set('Enter the provider model and API key, or start with commands.')
                return
            updated.update(api_base_url=api_url.get().strip().rstrip('/'), api_model=api_model.get().strip())
        try:
            provider_key = (key.get().strip() or cfg.get('api_key') or None) if mode.current() == 2 else None
            save_settings(updated, key=provider_key)
        except OSError:
            error.set('Could not save settings for this Windows account. Check folder permissions and try again.')
            return
        accepted[0] = True
        root.destroy()
    ttk.Button(buttons, text='Close', command=root.destroy).pack(side='left')
    ttk.Button(buttons, text='Start VoiceOS', style='Primary.TButton', command=finish).pack(side='right')
    root.bind('<Escape>', lambda e: root.destroy())
    root.mainloop()
    return accepted[0]
