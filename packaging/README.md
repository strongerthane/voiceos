# Build the Windows beta

Use Windows x64 and Python 3.14 with Tcl/Tk. Create a fresh virtual environment;
do not package the developer's global Python environment or copy their project
directory into the distribution.

```powershell
python -m venv .beta-build-env
.\.beta-build-env\Scripts\python.exe -m pip install -r packaging\requirements-windows.lock
.\.beta-build-env\Scripts\python.exe packaging\build_windows.py --output artifacts\beta-1
```

Use a new output folder for each build. The script creates a portable ZIP,
SHA256SUMS.txt, a dependency/file hash manifest, license notices and release notes.
It only packages Python imports and explicit dependency data, never local JSON
configuration, API keys, recordings, screenshots or contact files. It refuses
private configuration filenames inside the app folder before archiving.

Test the extracted executable rather than only the source:

```powershell
$env:VOICEOS_CONFIG_DIR = "$env:TEMP\VoiceOS-beta-check"
Start-Process -Wait artifacts\beta-1\dist\VoiceOS\VoiceOS.exe -ArgumentList '--smoke-test'
Get-Content "$env:VOICEOS_CONFIG_DIR\diagnostics.json"
```

`--diagnose --record-test` also records two seconds locally without uploading or
persisting audio. Normal launch presents first-run setup; `--settings` reopens it.
Test the ZIP on a second clean Windows laptop before calling the beta broadly
validated. This build is unsigned; signing requires a separately obtained code
signing identity. Do not disable Windows security to build or run it.

For an already compiled output, `--package-only` refreshes notices, the file
manifest, ZIP and checksum without compiling again. Run the ZIP verification
again afterward. The x64 package retains only the standard PortAudio DLL, with
its license, and omits unused ASIO and other-platform binaries.
