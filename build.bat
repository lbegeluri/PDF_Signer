@echo off
rem Builds a single-file, windowed pdf_signer.exe into .\dist
pip install -r requirements.txt || exit /b 1
python -m PyInstaller --onefile --windowed --name "PDF Signer By Levan" --icon icon.ico ^
  --add-data "samples\signature.png;." --add-data "icon.png;." ^
  --exclude-module pymupdf.layout --exclude-module onnxruntime ^
  --distpath dist --workpath build --clean -y pdf_signer.py
