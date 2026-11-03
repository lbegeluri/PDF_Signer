"""PDF Signer By Levan: open a PDF, place a signature image, save a signed copy."""
import glob
import io
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pymupdf
from PIL import Image, ImageTk

APP_TITLE = "PDF Signer By Levan"
DEFAULT_WIDTH_PT = 150  # signature width on the page, in PDF points
VIEW_HEIGHT_PX = 820    # target rendered page height
FONT = ("Segoe UI", 10)

HINT_EMPTY = "Click the document to place the signature, then drag it with the mouse"
HINT_OPEN = "{name} — " + HINT_EMPTY


def app_dir():
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def list_signatures():
    """signature*.png files next to the exe (signature.png first); the bundled one if none exist."""
    found = {}
    for path in glob.glob(os.path.join(app_dir(), "signature*.png")):
        found[os.path.basename(path)] = path
    if not found:
        bundled = os.path.join(getattr(sys, "_MEIPASS", os.path.join(app_dir(), "samples")), "signature.png")
        return {"signature.png": bundled}
    names = sorted(found, key=lambda n: (n.lower() != "signature.png", natural_key(n)))
    return {n: found[n] for n in names}


def load_signature(path):
    img = Image.open(path).convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    return img.crop(bbox) if bbox else img


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.option_add("*Font", FONT)
        try:
            self.icon = tk.PhotoImage(file=os.path.join(getattr(sys, "_MEIPASS", app_dir()), "icon.png"))
            self.iconphoto(True, self.icon)
        except tk.TclError:
            pass  # the default icon is fine
        self.signatures = list_signatures()
        self.sig = load_signature(next(iter(self.signatures.values())))
        self.doc = None
        self.path = None
        self.page_no = 0
        self.zoom = 1.0
        self.placements = {}  # page_no -> [x_pt, y_pt] centre of the signature on the displayed page
        self.width_pt = tk.DoubleVar(value=DEFAULT_WIDTH_PT)
        self.angle = tk.DoubleVar(value=0)  # degrees, positive = tilt right (clockwise)
        self.page_img = None
        self.sig_img = None
        self.drag_off = (0, 0)

        top = tk.Frame(self, padx=6, pady=6)
        top.pack(fill="x")
        tk.Button(top, text="Open PDF", command=self.open_pdf).pack(side="left")
        tk.Button(top, text="◀", width=3, command=lambda: self.goto(self.page_no - 1)).pack(side="left", padx=(12, 0))
        self.page_label = tk.Label(top, text="–", width=14)
        self.page_label.pack(side="left")
        tk.Button(top, text="▶", width=3, command=lambda: self.goto(self.page_no + 1)).pack(side="left")
        tk.Label(top, text="Signature:").pack(side="left", padx=(16, 4))
        self.sig_name = tk.StringVar(value=next(iter(self.signatures)))
        combo = ttk.Combobox(top, textvariable=self.sig_name, values=list(self.signatures),
                             state="readonly", width=22)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", self.on_signature_chosen)
        tk.Button(top, text="Save signed PDF", bg="#2e7d32", fg="white",
                  command=self.save).pack(side="right")

        bar = tk.Frame(self, padx=6)
        bar.pack(fill="x")
        tk.Label(bar, text="Signature size:").pack(side="left")
        tk.Scale(bar, from_=40, to=400, orient="horizontal", length=180, showvalue=False,
                 variable=self.width_pt, command=lambda _v: self.draw_signature()).pack(side="left", padx=4)
        tk.Label(bar, text="Tilt:").pack(side="left", padx=(12, 0))
        tk.Scale(bar, from_=-180, to=180, orient="horizontal", length=180, showvalue=False,
                 variable=self.angle, command=lambda _v: self.draw_signature()).pack(side="left", padx=4)
        tk.Button(bar, text="0°", width=3, command=self.reset_angle).pack(side="left")
        tk.Button(bar, text="Remove signature", command=self.remove_sig).pack(side="left", padx=12)

        self.hint = tk.Label(self, anchor="w", padx=8, pady=4, fg="#555", text=HINT_EMPTY)
        self.hint.pack(fill="x")

        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(frame, bg="#888", highlightthickness=0)
        vs = tk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        hs = tk.Scrollbar(frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.bind("<Delete>", lambda _e: self.remove_sig())
        self.geometry("1150x900")

    # --- signature choice --------------------------------------------------
    def on_signature_chosen(self, _event=None):
        try:
            self.sig = load_signature(self.signatures[self.sig_name.get()])
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not load the signature file:\n{exc}")
            return
        self.draw_signature()

    # --- document handling -------------------------------------------------
    def open_pdf(self):
        path = filedialog.askopenfilename(title="Choose a PDF file", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            doc = pymupdf.open(path)
            if doc.needs_pass:
                raise ValueError("This PDF is password-protected.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not open the file:\n{exc}")
            return
        if self.doc:
            self.doc.close()
        self.doc, self.path = doc, path
        self.placements.clear()
        self.page_no = 0
        self.render()

    def reset(self):
        if self.doc:
            self.doc.close()
        self.doc = self.path = None
        self.placements.clear()
        self.canvas.delete("all")
        self.page_label.config(text="–")
        self.hint.config(text=HINT_EMPTY)

    def goto(self, n):
        if self.doc and 0 <= n < len(self.doc):
            self.page_no = n
            self.render()

    def render(self):
        page = self.doc[self.page_no]
        self.zoom = VIEW_HEIGHT_PX / page.rect.height
        pix = page.get_pixmap(matrix=pymupdf.Matrix(self.zoom, self.zoom), alpha=False)
        self.page_img = ImageTk.PhotoImage(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.page_img, tags="page")
        self.canvas.configure(scrollregion=(0, 0, pix.width, pix.height))
        self.page_label.config(text=f"Page {self.page_no + 1} / {len(self.doc)}")
        self.hint.config(text=HINT_OPEN.format(name=os.path.basename(self.path)))
        self.draw_signature()

    # --- signature overlay -------------------------------------------------
    def sig_size_pt(self):
        w = self.width_pt.get()
        return w, w * self.sig.height / self.sig.width

    def reset_angle(self):
        self.angle.set(0)
        self.draw_signature()

    def tilted(self, img):
        """img rotated by the chosen tilt (transparent corners, canvas grown to fit)."""
        ang = self.angle.get()
        return img.rotate(-ang, resample=Image.BICUBIC, expand=True) if ang else img

    def bbox_size_pt(self):
        """Width/height of the tilted signature's bounding box, in PDF points."""
        w, h = self.sig_size_pt()
        t = math.radians(self.angle.get())
        c, s = abs(math.cos(t)), abs(math.sin(t))
        return w * c + h * s, w * s + h * c

    def draw_signature(self):
        self.canvas.delete("sig")
        pos = self.placements.get(self.page_no)
        if not self.doc or pos is None:
            return
        w, h = self.sig_size_pt()
        size = (max(1, int(w * self.zoom)), max(1, int(h * self.zoom)))
        self.sig_img = ImageTk.PhotoImage(self.tilted(self.sig.resize(size, Image.LANCZOS)))
        self.canvas.create_image(pos[0] * self.zoom, pos[1] * self.zoom, anchor="center",
                                 image=self.sig_img, tags="sig")

    def on_press(self, e):
        if not self.doc:
            return
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        bw, bh = self.bbox_size_pt()
        pos = self.placements.get(self.page_no)
        if pos and abs(x - pos[0] * self.zoom) <= bw * self.zoom / 2 and abs(y - pos[1] * self.zoom) <= bh * self.zoom / 2:
            self.drag_off = (x - pos[0] * self.zoom, y - pos[1] * self.zoom)
        else:  # place it centred on the click
            self.drag_off = (0, 0)
            self.on_drag(e)

    def on_drag(self, e):
        if not self.doc:
            return
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self.placements[self.page_no] = [(x - self.drag_off[0]) / self.zoom, (y - self.drag_off[1]) / self.zoom]
        self.draw_signature()

    def remove_sig(self):
        if self.doc:
            self.placements.pop(self.page_no, None)
            self.draw_signature()

    # --- saving ------------------------------------------------------------
    def save(self):
        if not self.doc:
            messagebox.showinfo(APP_TITLE, "Open a PDF file first.")
            return
        if not self.placements:
            messagebox.showinfo(APP_TITLE, "Click on a page first to place the signature.")
            return
        base, _ext = os.path.splitext(os.path.basename(self.path))
        out = filedialog.asksaveasfilename(
            title="Save signed PDF", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialdir=os.path.dirname(self.path), initialfile=f"{base}_signed.pdf")
        if not out:
            return
        if os.path.abspath(out) == os.path.abspath(self.path):
            messagebox.showerror(APP_TITLE, "Do not overwrite the original file. Choose a different name.")
            return
        try:
            doc = pymupdf.open(self.path)
            w, _h = self.sig_size_pt()
            tilted = self.tilted(self.sig)
            png = self.png_bytes(tilted)
            scale = w / self.sig.width  # PDF points per signature pixel
            rw, rh = tilted.width * scale, tilted.height * scale
            for n, (cx, cy) in self.placements.items():
                page = doc[n]
                rect = pymupdf.Rect(cx - rw / 2, cy - rh / 2, cx + rw / 2, cy + rh / 2) * page.derotation_matrix
                page.insert_image(rect, stream=png, rotate=page.rotation,
                                  overlay=True, keep_proportion=False)
            doc.save(out, garbage=3, deflate=True)
            doc.close()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Saving failed:\n{exc}")
            return
        if self.ask_another(out):
            self.reset()
            self.open_pdf()
        else:
            self.destroy()

    @staticmethod
    def png_bytes(img):
        b = io.BytesIO()
        img.save(b, "PNG")
        return b.getvalue()

    def ask_another(self, saved_path):
        """Saved-file notice with Yes / No; returns True for Yes."""
        answer = {"yes": False}
        dlg = tk.Toplevel(self)
        dlg.title(APP_TITLE)
        dlg.transient(self)
        dlg.resizable(False, False)
        tk.Label(dlg, text=f"File saved:\n{saved_path}", justify="left", padx=20, pady=12,
                 wraplength=460).pack()
        tk.Label(dlg, text="Sign another document?", font=("Segoe UI", 11, "bold"),
                 padx=20, pady=4).pack()
        row = tk.Frame(dlg, pady=14)
        row.pack()

        def choose(yes):
            answer["yes"] = yes
            dlg.destroy()

        tk.Button(row, text="Yes", width=10, command=lambda: choose(True)).pack(side="left", padx=8)
        tk.Button(row, text="No", width=10, command=lambda: choose(False)).pack(side="left", padx=8)
        dlg.protocol("WM_DELETE_WINDOW", lambda: choose(False))
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dlg.grab_set()
        self.wait_window(dlg)
        return answer["yes"]


if __name__ == "__main__":
    App().mainloop()
