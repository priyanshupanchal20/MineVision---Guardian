# MineVision Guardian
cd "$PSScriptRoot\.."
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -q -r raspberry_pi\requirements.txt
pip install -q -r raspberry_pi\requirements-dev.txt
python raspberry_pi\run.py
