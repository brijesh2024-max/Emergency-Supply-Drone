"""Start the prebuilt exercise from a source checkout or the portable archive."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def run(argv):
    subprocess.run([str(arg) for arg in argv],cwd=ROOT,check=True)

def main():
    if sys.version_info<(3,11):
        raise SystemExit("Use Python 3.11 or later.")
    windows=os.name=="nt"
    python=ROOT/".venv"/("Scripts/python.exe" if windows else "bin/python")
    if not python.exists():
        run([sys.executable,"-m","venv",ROOT/".venv"])
    wheelhouse=ROOT/"vendor"/"windows-py314"
    options=[]
    if wheelhouse.exists() and windows and sys.version_info[:2]==(3,14) and platform.machine().lower() in ("amd64","x86_64"):
        options=["--no-index","--find-links",wheelhouse]
    run([python,"-m","pip","install","--disable-pip-version-check",*options,"-r","backend/requirements.txt"])
    if not (ROOT/"out/index.html").exists():
        npm=shutil.which("npm.cmd" if windows else "npm")
        if not npm:
            raise SystemExit("Install Node.js 22.12+ to build the frontend from source.")
        run([npm,"install"])
        run([npm,"run","build"])
    print("Aeris rescue exercise: http://127.0.0.1:8765",flush=True)
    run([python,"-m","uvicorn","backend.main:app","--host","127.0.0.1","--port","8765","--workers","1"])

if __name__=="__main__":
    main()
