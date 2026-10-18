"""Build an allowlisted portable Windows beta; never copy the source tree."""
import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Backend' / 'original'
sys.path.insert(0, str(SOURCE))
from beta_main import VERSION


def build(output, package_only=False):
    if sys.platform != 'win32' or platform.machine().lower() not in {'amd64', 'x86_64'}:
        raise SystemExit('Build with Windows x64 Python.')
    # A fresh output path prevents mixing a prior package with new artifacts.
    output = output.resolve()
    if output.exists() and not package_only:
        raise SystemExit('Choose a new, empty output path for this build.')
    output.mkdir(parents=True, exist_ok=package_only)
    if not package_only:
        subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
        '--windowed', '--name', 'VoiceOS', '--noupx',
        '--paths', str(SOURCE), '--collect-data', 'speech_recognition',
        '--collect-data', 'certifi', '--hidden-import', '_cffi_backend',
        '--distpath', str(output / 'dist'), '--workpath', str(output / 'work'),
        '--specpath', str(output / 'work'), str(SOURCE / 'beta_main.py'),
        ], check=True, cwd=ROOT)
    app = output / 'dist' / 'VoiceOS'
    if not (app / 'VoiceOS.exe').is_file():
        raise SystemExit('No compiled VoiceOS.exe found in this build output.')
    # Retain only the normal x64 PortAudio library; no unused ASIO/other-OS DLLs.
    audio_libs = app / '_internal' / '_sounddevice_data' / 'portaudio-binaries'
    if not audio_libs.resolve().is_relative_to(output):
        raise SystemExit('Invalid build output path.')
    for name in ('libportaudio.dylib', 'libportaudio32bit.dll', 'libportaudio32bit-asio.dll', 'libportaudio64bit-asio.dll', 'libportaudioarm64.dll', 'libportaudioarm64-asio.dll'):
        path = audio_libs / name
        if path.is_file():
            path.unlink()
    shutil.copy2(ROOT / 'packaging' / 'START_HERE.txt', app / 'START_HERE.txt')
    (app / 'Settings.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0VoiceOS.exe" --settings\r\n', encoding='utf-8')
    (app / 'Check microphone.cmd').write_text(
        '@echo off\r\ncd /d "%~dp0"\r\necho Recording two seconds locally. No upload or audio file.\r\n'
        'start "" /wait "%~dp0VoiceOS.exe" --diagnose --record-test\r\n'
        'if exist "%LOCALAPPDATA%\\VoiceOS\\diagnostics.json" notepad "%LOCALAPPDATA%\\VoiceOS\\diagnostics.json"\r\n', encoding='utf-8')
    # Include installed dependency metadata and their shipped license texts.
    notice_lines = ['VoiceOS third-party components', '', 'Each dependency retains its own license. See licenses/ for the installed license texts.', '']
    versions = {}
    licenses = app / 'licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'packaging' / 'PortAudio-LICENSE.txt', licenses / 'PortAudio-LICENSE.txt')
    for distribution in sorted(metadata.distributions(), key=lambda d: d.metadata.get('Name', '')):
        name = distribution.metadata.get('Name', 'unknown')
        if name.lower() in {'pip', 'pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'pefile', 'pywin32-ctypes', 'setuptools', 'packaging'}:
            continue
        versions[name] = distribution.version
        notice_lines.append(f'{name} {distribution.version} — {distribution.metadata.get("License-Expression") or distribution.metadata.get("License", "See license file")}')
        for item in distribution.files or []:
            # dist-info license trees and conventional package license files.
            if any(part.lower() in {'licenses', 'license', 'license.txt', 'license.md', 'copying', 'copying.txt', 'notice', 'notice.txt'} for part in item.parts):
                src = Path(distribution.locate_file(item))
                if src.is_file():
                    target = licenses / name / Path(*item.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, target)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        licenses.mkdir(exist_ok=True)
        shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    # Tcl/Tk license is shipped separately from the Python package metadata.
    for name in ('tcl8.6', 'tk8.6'):
        for filename in ('license.terms', 'license.txt'):
            src = Path(sys.base_prefix) / 'tcl' / name / filename
            if src.is_file():
                shutil.copy2(src, licenses / f'{name}-{filename}')
    (app / 'THIRD_PARTY_NOTICES.txt').write_text('\n'.join(notice_lines), encoding='utf-8')
    manifest = {'version': VERSION, 'platform': 'windows-x64', 'python': platform.python_version(), 'dependencies': versions, 'files': {}}
    forbidden = {'ai_config.json', 'voiceos_contacts.json', 'voiceos_aliases.json', 'provider-key.bin', '.env', 'setup-complete'}
    for path in sorted(app.rglob('*')):
        if path.is_file() and path.name != 'build-manifest.json':
            public_ca_bundle = path.relative_to(app).as_posix() == '_internal/certifi/cacert.pem'
            if path.name in forbidden or (path.suffix.lower() in {'.pem', '.pfx', '.key', '.wav', '.mp3'} and not public_ca_bundle):
                raise SystemExit(f'Unexpected private or recording file in package: {path.relative_to(app)}')
            manifest['files'][path.relative_to(app).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (app / 'build-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    basename = f'VoiceOS-{VERSION}-windows-x64'
    archive = Path(shutil.make_archive(str(output / basename), 'zip', root_dir=app.parent, base_dir=app.name))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{checksum}  {archive.name}\n', encoding='utf-8')
    shutil.copy2(ROOT / 'packaging' / 'RELEASE_NOTES.md', output / 'RELEASE_NOTES.md')
    print(f'Beta package: {archive}')
    print(f'SHA-256: {checksum}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--package-only', action='store_true', help='Reassemble an already compiled build output without rebuilding the EXE')
    args = parser.parse_args()
    build(args.output, args.package_only)
