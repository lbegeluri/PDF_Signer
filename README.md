# PDF Signer By Levan

A small Windows desktop tool for placing a signature image (PNG) onto a PDF.
Open a PDF, click where the signature should go, drag it into place, and save a signed copy.
No printing and scanning needed.

![icon](icon.png)

> **Note:** this places an *image* of a signature on the page. It is not a cryptographic digital
> signature. Use it only with the signature owner's permission.

## Features

- Opens any unencrypted PDF and renders it page by page
- Click to place, drag to move the signature (per page)
- Adjustable signature **size** and **tilt**
- Several signatures: any `signature*.png` next to the program shows up in a dropdown
- Works with rotated pages and multi-page documents
- The original file is never changed; the result is saved as a new `*_signed.pdf`
- Ships as a single `.exe` with no installation and no Python needed

## Quick start

1. Put your signature on a transparent background as `signature.png` next to the program
   (`PDF Signer By Levan.exe`, or `pdf_signer.py` if running from source).
2. Start the program and click **Open PDF**.
3. Click on the page where the signature should go. Drag it to adjust.
4. Optional: change the **Signature size** and **Tilt** sliders.
5. Click **Save signed PDF**. You can then sign another document or exit.

Extra signatures: add `signature1.png`, `signature2.png`, ... in the same folder.
They appear in the **Signature:** dropdown. If no signature file is found next to the program,
a built-in sample signature is used.

### Controls

| Action | How |
| --- | --- |
| Place signature | Click on the page |
| Move signature | Drag it with the mouse |
| Remove signature from the current page | **Remove signature** button or `Delete` |
| Next / previous page | `▶` / `◀` buttons |
| Reset tilt | `0°` button |

📖 **Full guide with screenshots:** [docs/INSTRUCTIONS.md](docs/INSTRUCTIONS.md)

## Try it

The [`samples`](samples) folder contains a **fictional** `sample.pdf` and six fictional
signatures (`signature.png`, `signature1.png` ... `signature5.png`).
Copy them next to the program to test. None of them belongs to a real person or company.

## Run from source

Requires Python 3.10+ on Windows (Tkinter included with the standard installer).

```bash
pip install -r requirements.txt
python pdf_signer.py
```

Signature files are looked up next to `pdf_signer.py`. If none is found, `samples/signature.png` is used.

## Build the .exe

```bash
build.bat
```

The result is `dist\PDF Signer By Levan.exe`, a single file you can share. Windows SmartScreen may
warn about an unknown publisher the first time (More info → Run anyway), because the file is not
code-signed.

## Tech

Python, Tkinter, [PyMuPDF](https://pymupdf.readthedocs.io/), Pillow, PyInstaller.
The signature is pre-rotated and inserted as an overlay image at the chosen position
(coordinates are handled in PDF points, including page rotation).

## License

[MIT](LICENSE)
