"""Extract and test the shipped ZIP with Python absent from the child's PATH."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


def verify(archive, report, record=False):
    expected = archive.parent / 'SHA256SUMS.txt'
    wanted = expected.read_text(encoding='utf-8').split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != wanted:
        raise SystemExit('Archive checksum does not match SHA256SUMS.txt.')
    with tempfile.TemporaryDirectory(prefix='VoiceOS-extracted-beta-') as temporary:
        folder = Path(temporary)
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise SystemExit('Unsafe archive member.')
            bundle.extractall(folder)
        app = folder / 'VoiceOS'
        manifest = json.loads((app / 'build-manifest.json').read_text(encoding='utf-8'))
        for name, digest in manifest['files'].items():
            if hashlib.sha256((app / name).read_bytes()).hexdigest() != digest:
                raise SystemExit(f'File checksum mismatch: {name}')
        # No developer API keys, PYTHONPATH, installed Python, or project config.
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('VOICEOS_', 'PYTHON')) and k.upper() not in {'OPENAI_API_KEY', 'NVIDIA_API_KEY', 'NIM_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY'}}
        windows = env.get('SystemRoot', r'C:\Windows')
        env['PATH'] = str(Path(windows) / 'System32') + ';' + windows
        env['VOICEOS_CONFIG_DIR'] = str(folder / 'clean-user')
        report = report.resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        command = [str(app / 'VoiceOS.exe'), '--smoke-test', '--report', str(report)]
        if record:
            command.append('--record-test')
        result = subprocess.run(command, cwd=folder, env=env, timeout=90, check=False)
        if not report.exists():
            startup_error = folder / 'clean-user' / 'startup-error.txt'
            if startup_error.exists():
                print(startup_error.read_text(encoding='utf-8'))
            raise SystemExit(f'Bundled application produced no report (exit {result.returncode}).')
        data = json.loads(report.read_text(encoding='utf-8'))
        data.update(zip_checksum_valid=True, file_manifest_valid=True, python_removed_from_path=True)
        report.write_text(json.dumps(data, indent=2), encoding='utf-8')
        print(json.dumps(data, indent=2))
        if result.returncode or not data.get('passed') or not data.get('frozen'):
            raise SystemExit('The extracted beta failed verification.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--record-test', action='store_true')
    args = parser.parse_args()
    verify(args.archive, args.report, args.record_test)
