import os
import sys
import tempfile
import threading
import queue
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from datetime import datetime

# sys.path.append moved up to ensure relative imports work before heavy hits
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tkinterdnd2 import DND_FILES, TkinterDnD

# Delayed imports for faster startup
# import fitz
# from PIL import Image, ImageTk

from config import DEFAULT_OUTPUT_DIR
from core.compress import COMPRESSION_LEVEL_LABELS, compress_pdf
from core.executor import CancellableCommand
from core.info import pdf_info, pdf_is_encrypted, pdf_page_count
from core.logger import get_logger
from core.merge import merge_pdfs
from core.ocr import ocr_pdf
from core.mupdf_tools import has_text
from core.output import output_exists, output_path as build_output_path
from core.settings import load_settings, save_settings
from core.validation import validate_pdf_file, validate_pdf_files
from core.validator import check_dependencies

logger = get_logger(__name__)

BG = "#0A0B10"  # Deeper dark
SURFACE = "#161922"
DANGER = "#FF4D6D"
SUCCESS = "#00F59B"
TEXT = "#D1D5DB"
SUBTEXT = "#9CA3AF"
DROP_BG = "#0D0F16"
ACCENT = "#4F46E5"
ACCENT_ACTIVE = "#6366F1"
DROP_BORDER = "#1F2937"
PREVIEW_CANVAS_W = 200
PREVIEW_CANVAS_H = 280
PREVIEW_CENTER_X = PREVIEW_CANVAS_W // 2
PREVIEW_CENTER_Y = PREVIEW_CANVAS_H // 2
PREVIEW_FITZ_SCALE = 0.35
PAD = 10


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 27
        y = y + cy + self.widget.winfo_rooty() + 27
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#1F2937",
            foreground="#D1D5DB",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", 8, "normal"),
            padx=4,
            pady=2,
        )
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


class PDFToolUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Tool")
        self.root.geometry("920x760")
        self.root.configure(bg=BG)

        try:
            check_dependencies()
        except Exception as e:
            logger.error(f"Startup dependency check failed: {e}")
            messagebox.showerror(
                "Missing Dependencies",
                f"Cannot start PDF Tool.\n\n{e}\n\nInstall qpdf, Ghostscript, Tesseract, and pip packages.",
            )
            self.root.destroy()
            sys.exit(1)

        # Thread‑safe cancellation
        self._cancel_event = threading.Event()
        self.runner = None

        self.settings = load_settings()
        self.output_dir = os.path.abspath(self.settings.get("output_dir", DEFAULT_OUTPUT_DIR))
        self.output_template = tk.StringVar(value="{name}.pdf")

        geometry = self.settings.get("window_geometry")
        if geometry:
            self.root.geometry(geometry)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.dropped_files = []

        # Action toggles
        self.do_compress = tk.BooleanVar(value=True)
        self.do_ocr = tk.BooleanVar(value=False)
        self.do_merge = tk.BooleanVar(value=False)

        self.level_labels = dict(COMPRESSION_LEVEL_LABELS)
        self.compression_level = tk.StringVar(value="3")

        self.action_buttons = []
        self.drag_index = None

        self.job_queue = queue.Queue()
        self.preview_image = None
        self._preview_gen = 0
        self._preview_after_id = None
        self._preview_thread_path = None
        self._gs_progress_after_id = None
        self._gs_progress_pending = None
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

        self._build_ui()
        self.refresh_file_list()

    # ---------- UI helpers ----------
    def safe_ui(self, func, *args, **kwargs):
        self.root.after(0, lambda: func(*args, **kwargs))

    def _on_close(self):
        self.settings["window_geometry"] = self.root.winfo_geometry()
        save_settings(self.settings)
        self.root.destroy()

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG, padx=PAD, pady=PAD)
        header.pack(fill="x")
        tk.Label(
            header, text="PDF Tool", fg=TEXT, bg=BG, font=("Segoe UI", 18, "bold")
        ).pack(side="left")
        self.process_btn = ttk.Button(
            header, text="Process", command=self.process_all, style="Accent.TButton"
        )
        self.process_btn.pack(side="right", padx=8)
        self.cancel_btn = ttk.Button(
            header, text="Cancel", command=self.cancel, style="DangerTTk.TButton"
        )
        self.cancel_btn.pack(side="right")
        self.action_buttons = [self.process_btn]
        ToolTip(self.process_btn, "Run selected actions on all loaded PDFs")
        ToolTip(self.cancel_btn, "Stop running task")

        # Main body: left (file area) + right (preview & settings)
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=PAD, pady=5)

        # ---- Left side ----
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        # Drop zone
        self.drop_zone = tk.Label(
            left,
            text="Drag & Drop PDFs Here",
            bg=DROP_BG,
            fg=SUBTEXT,
            height=2,
            font=("Segoe UI", 10),
            highlightthickness=1,
            highlightbackground=DROP_BORDER,
            cursor="hand2",
        )
        self.drop_zone.grid(row=0, column=0, sticky="ew", pady=5)
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind("<<Drop>>", self.handle_drop)
        self.drop_zone.bind("<Enter>", lambda e: self.drop_zone.configure(bg=SURFACE))
        self.drop_zone.bind("<Leave>", lambda e: self.drop_zone.configure(bg=DROP_BG))

        # File tree
        columns = ("name", "size", "pages", "status")
        self.file_tree = ttk.Treeview(
            left, columns=columns, show="headings", selectmode="extended"
        )
        self.file_tree.heading("name", text="File Name")
        self.file_tree.heading("size", text="Size")
        self.file_tree.heading("pages", text="Pages")
        self.file_tree.heading("status", text="Status")
        self.file_tree.column("name", width=300, anchor="w")
        self.file_tree.column("size", width=80, anchor="center")
        self.file_tree.column("pages", width=60, anchor="center")
        self.file_tree.column("status", width=90, anchor="center")
        self.file_tree.grid(row=1, column=0, sticky="nsew")
        self.file_tree.bind("<<TreeviewSelect>>", self.on_treeview_select)
        self.file_tree.bind("<ButtonPress-1>", self.start_drag)
        self.file_tree.bind("<B1-Motion>", self.drag_reorder)
        self.file_tree.bind("<ButtonRelease-1>", self.on_drag_release)

        # Toolbar
        toolbar = tk.Frame(left, bg=BG, pady=5)
        toolbar.grid(row=2, column=0, sticky="ew")
        for caption, cb, tip in [
            ("Add", self.add_files, "Add PDF files"),
            ("Remove", self.remove_selected, "Remove selected files"),
            ("Clear", self.clear_files, "Clear all files"),
            ("↑", lambda: self.move_selected(-1), "Move up"),
            ("↓", lambda: self.move_selected(1), "Move down"),
            ("Info", self.show_pdf_info, "Show PDF details"),
            ("Open Folder", self.open_output_folder, "Open output folder"),
        ]:
            btn = ttk.Button(toolbar, text=caption, command=cb, style="Toolbar.TButton")
            btn.pack(side="left", padx=4)
            ToolTip(btn, tip)

        # ---- Right side ----
        right = tk.Frame(body, bg=BG, width=230)
        right.pack(side="right", fill="y", padx=PAD)
        right.pack_propagate(False)

        # Preview
        self.preview_frame = tk.Frame(right, bg=BG)
        self.preview_frame.pack(fill="x", pady=PAD)
        self.preview_canvas = tk.Canvas(
            self.preview_frame,
            width=PREVIEW_CANVAS_W,
            height=PREVIEW_CANVAS_H,
            bg=DROP_BG,
            highlightthickness=0,
        )
        self.preview_canvas.pack()
        self.page_count_label = tk.Label(
            self.preview_frame,
            text="",
            fg=SUBTEXT,
            bg=BG,
            font=("Segoe UI", 8),
        )
        self.page_count_label.pack()

        # Settings
        settings = tk.Frame(right, bg=BG)
        settings.pack(fill="x")

        # Compression level
        tk.Label(settings, text="Compression", fg=SUBTEXT, bg=BG, anchor="w").pack(
            fill="x", pady=2
        )
        self.level_picker = ttk.Combobox(
            settings,
            textvariable=self.compression_level,
            values=list(self.level_labels.values()),
            state="readonly",
            width=25,
        )
        self.level_picker.pack(fill="x", pady=8)

        # Output folder
        tk.Label(settings, text="Output folder", fg=SUBTEXT, bg=BG, anchor="w").pack(
            fill="x", pady=2
        )
        out_row = tk.Frame(settings, bg=BG)
        out_row.pack(fill="x", pady=8)
        self.output_label = tk.Label(
            out_row, text=os.path.basename(self.output_dir), fg=TEXT, bg=BG, anchor="w"
        )
        self.output_label.pack(side="left", fill="x", expand=True)
        ttk.Button(
            out_row, text="Browse", command=self.select_output, style="Toolbar.TButton"
        ).pack(side="right")

        # Action toggles
        for var, label, tip in [
            (self.do_compress, "Compress", "Reduce file size"),
            (self.do_ocr, "OCR", "Make scanned PDFs searchable"),
            (self.do_merge, "Merge into one", "Combine all files into a single PDF"),
        ]:
            cb = tk.Checkbutton(
                settings,
                text=label,
                variable=var,
                fg=TEXT,
                bg=BG,
                selectcolor=SURFACE,
                activebackground=BG,
                activeforeground=TEXT,
                anchor="w",
            )
            cb.pack(fill="x")
            ToolTip(cb, tip)

        # Log and progress footer
        footer = tk.Frame(self.root, bg=BG, padx=PAD, pady=PAD)
        footer.pack(fill="x", side="bottom")

        log_frame = tk.Frame(footer, bg=BG)
        log_frame.pack(fill="x", expand=True, pady=5)
        self.log = scrolledtext.ScrolledText(
            log_frame,
            height=6,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            font=("Consolas", 9),
            relief="flat",
        )
        self.log.pack(fill="both", expand=True)

        progress_frame = tk.Frame(footer, bg=BG)
        progress_frame.pack(fill="x")
        self.progress = ttk.Progressbar(
            progress_frame, mode="determinate", style="Horizontal.TProgressbar"
        )
        self.progress.pack(fill="x")
        self.status_label = ttk.Label(
            progress_frame, text="Ready", foreground=SUBTEXT, background=BG
        )
        self.status_label.pack(side="left", pady=2)

        # Styles
        self._configure_style()

    def _configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Global backgrounds
        style.configure(".", background=BG, foreground=TEXT, bordercolor=DROP_BORDER, lightcolor=BG, darkcolor=BG)

        # Buttons
        style.configure("Accent.TButton", background=ACCENT, foreground=TEXT,
                        padding=(12, 5), font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", ACCENT_ACTIVE)])

        style.configure("DangerTTk.TButton", background=SURFACE, foreground=DANGER,
                        padding=(12, 5))
        style.map("DangerTTk.TButton", background=[("active", DROP_BORDER)])

        style.configure("Toolbar.TButton", background=SURFACE, foreground=TEXT,
                        padding=(6, 3))
        style.map("Toolbar.TButton", background=[("active", DROP_BORDER)])

        # Treeview
        style.configure("Treeview",
                        background=DROP_BG,
                        foreground=TEXT,
                        fieldbackground=DROP_BG,
                        rowheight=30,
                        borderwidth=0)
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", TEXT)])
        style.configure("Treeview.Heading",
                        background=SURFACE,
                        foreground=SUBTEXT,
                        relief="flat",
                        padding=5)
        style.map("Treeview.Heading", background=[("active", DROP_BORDER)])

        # Progressbar
        style.configure("Horizontal.TProgressbar", troughcolor=DROP_BG,
                        background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                        bordercolor=DROP_BORDER, thickness=8)

        # Combobox
        style.configure("TCombobox",
                        fieldbackground=DROP_BG,
                        background=SURFACE,
                        foreground=TEXT,
                        arrowcolor=TEXT,
                        bordercolor=DROP_BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", DROP_BG)],
                  selectbackground=[("readonly", DROP_BG)],
                  selectforeground=[("readonly", TEXT)])

        # Scrollbar
        style.configure("Vertical.TScrollbar",
                        troughcolor=BG,
                        background=SURFACE,
                        bordercolor=BG,
                        arrowcolor=SUBTEXT)
        style.map("Vertical.TScrollbar", background=[("active", DROP_BORDER)])

    # ---------- Job queue ----------
    def _process_queue(self):
        while True:
            task = self.job_queue.get()
            self._cancel_event.clear()
            self.safe_ui(self.set_running, True)
            try:
                task()
            except Exception as e:
                logger.exception("Background task failed")
                self.safe_ui(self.write_log, f"ERROR: {e}")
            finally:
                self._cancel_event.clear()
                self.runner = None
                self.safe_ui(self.set_running, False)
                self.safe_ui(self.set_status, "")
                self.safe_ui(self.update_progress, 0, 1)
                self.job_queue.task_done()

    def set_running(self, running):
        state = "disabled" if running else "normal"
        for btn in self.action_buttons:
            btn.configure(state=state)
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.level_picker.configure(state="disabled" if running else "readonly")
        self.process_btn.configure(state=state)

    def set_status(self, text):
        self.status_label.configure(text=text or "")

    def write_log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        self.log.insert(tk.END, f"[{t}] {msg}\n")
        self.log.see(tk.END)

    def update_progress(self, val, total):
        self.progress["maximum"] = total
        self.progress["value"] = val

    def cancel(self):
        self._cancel_event.set()
        if self.runner:
            self.runner.cancel()

    # ---------- File handling ----------
    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        self.add_pdf_files(files)

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
        if files:
            self.add_pdf_files(files)

    def add_pdf_files(self, files):
        added = 0
        for fp in files:
            err = validate_pdf_file(fp)
            if err:
                self.write_log(f"Skipped: {err}")
                continue
            if fp not in self.dropped_files:
                self.dropped_files.append(fp)
                added += 1
        if added:
            self.refresh_file_list()
            self.save_current_settings()
            self.write_log(f"Loaded {added} file(s)")

    def remove_selected(self):
        indices = sorted(
            [self.file_tree.index(i) for i in self.file_tree.selection()], reverse=True
        )
        for idx in indices:
            del self.dropped_files[idx]
        self.refresh_file_list()

    def clear_files(self):
        self.dropped_files = []
        self.refresh_file_list()

    def move_selected(self, direction):
        sel = self.file_tree.selection()
        if not sel or len(sel) > 1:
            return
        idx = self.file_tree.index(sel[0])
        new_idx = idx + direction
        if 0 <= new_idx < len(self.dropped_files):
            self.dropped_files[idx], self.dropped_files[new_idx] = (
                self.dropped_files[new_idx],
                self.dropped_files[idx],
            )
            self.refresh_file_list()
            new_item = self.file_tree.get_children()[new_idx]
            self.file_tree.selection_set(new_item)
            self.file_tree.see(new_item)

    def start_drag(self, event):
        item = self.file_tree.identify_row(event.y)
        if item:
            self.drag_index = self.file_tree.index(item)

    def drag_reorder(self, event):
        if self.drag_index is None:
            return
        item = self.file_tree.identify_row(event.y)
        if not item:
            return
        new = self.file_tree.index(item)
        if new != self.drag_index and 0 <= new < len(self.dropped_files):
            self.dropped_files[self.drag_index], self.dropped_files[new] = (
                self.dropped_files[new],
                self.dropped_files[self.drag_index],
            )
            self.drag_index = new

    def on_drag_release(self, event):
        self.refresh_file_list()
        self.save_current_settings()
        self.on_treeview_select()

    def refresh_file_list(self):
        self.file_tree.delete(*self.file_tree.get_children())
        for fp in self.dropped_files:
            name = os.path.basename(fp)
            size = os.path.getsize(fp)
            pages = pdf_page_count(fp) or "?"
            self.file_tree.insert(
                "",
                "end",
                values=(name, f"{size/1024:.1f} KB", pages, "Ready"),
                tags=("Ready",),
            )
        count = len(self.dropped_files)
        self.drop_zone.config(
            text=f"{count} file(s)" if count else "Drag & Drop PDFs Here",
            fg=TEXT if count else SUBTEXT,
        )

    # ---------- Preview ----------
    def on_treeview_select(self, event=None):
        sel = self.file_tree.selection()
        if not sel:
            return
        idx = self.file_tree.index(sel[0])
        fp = self.dropped_files[idx]
        self.page_count_label.configure(text="")
        self._preview_gen += 1
        gen = self._preview_gen
        if self._preview_after_id:
            self.root.after_cancel(self._preview_after_id)
        self._preview_after_id = self.root.after(150, lambda g=gen, f=fp: self._start_preview(g, f))

    def _start_preview(self, gen, path):
        self._preview_after_id = None
        if gen != self._preview_gen:
            return
        self._preview_thread_path = path
        threading.Thread(target=self._render_preview, args=(gen, path), daemon=True).start()

    def _render_preview(self, gen, path):
        import fitz
        from PIL import Image
        try:
            doc = fitz.open(path)
            page_count = len(doc)
            if doc.is_encrypted:
                self.safe_ui(self._set_preview_text, "Encrypted", TEXT)
                return
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(PREVIEW_FITZ_SCALE, PREVIEW_FITZ_SCALE))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.thumbnail((PREVIEW_CANVAS_W, PREVIEW_CANVAS_H))
            self.safe_ui(self._update_preview, img, page_count, gen, path)
        except Exception as e:
            self.safe_ui(self._set_preview_text, "Preview Error", DANGER)

    def _set_preview_text(self, text, color):
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            PREVIEW_CENTER_X, PREVIEW_CENTER_Y, text=text, fill=color
        )
        self.page_count_label.configure(text="")

    def _update_preview(self, img, page_count, gen, path):
        from PIL import ImageTk
        if gen != self._preview_gen or self._preview_thread_path != path:
            return
        self.preview_image = ImageTk.PhotoImage(img)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(
            PREVIEW_CENTER_X, PREVIEW_CENTER_Y, image=self.preview_image, anchor="center"
        )
        self.page_count_label.configure(text=f"Page 1 of {page_count}")

    # ---------- Settings ----------
    def select_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = folder
            self.output_label.configure(text=os.path.basename(folder))
            self.save_current_settings()

    def save_current_settings(self):
        self.settings["output_dir"] = self.output_dir
        save_settings(self.settings)

    def open_output_folder(self):
        os.makedirs(self.output_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(self.output_dir)
        elif sys.platform == "darwin":
            import subprocess; subprocess.Popen(["open", self.output_dir])
        else:
            import subprocess; subprocess.Popen(["xdg-open", self.output_dir])

    def show_pdf_info(self):
        sel = self.file_tree.selection()
        if not sel and self.dropped_files:
            idx = 0
        elif sel:
            idx = self.file_tree.index(sel[0])
        else:
            return
        fp = self.dropped_files[idx]
        info = pdf_info(fp)
        if "error" in info:
            self.write_log(f"ERROR: {info['error']}")
            return
        self.write_log(
            f"{os.path.basename(fp)} | {info['pages']} pages | {'encrypted' if info['encrypted'] else 'not encrypted'} | size {info['size']/1024:.1f} KB"
        )

    def prompt_password_if_needed(self, files):
        encrypted = [fp for fp in files if pdf_is_encrypted(fp)]
        if not encrypted:
            return True, None
        names = "\n".join(os.path.basename(p) for p in encrypted[:5])
        pw = simpledialog.askstring("PDF Password", f"Password for:\n{names}", show="*")
        if not pw:
            self.write_log("Password required – cancelled.")
            return False, None
        return True, pw

    def confirm_overwrite(self, path):
        if not output_exists(path):
            return True
        
        # Thread-safe messagebox call
        result_queue = queue.Queue()
        self.root.after(0, lambda: result_queue.put(
            messagebox.askyesno("Overwrite?", f"{path}\nalready exists. Overwrite?")
        ))
        return result_queue.get() # Blocks background thread until UI returns

    # ---------- Core processing ----------
    def process_all(self):
        files = list(self.dropped_files)
        if not files:
            self.write_log("No PDFs loaded.")
            return

        # Validate
        err = validate_pdf_files(files, minimum=1)
        if err:
            self.write_log(f"ERROR: {err}")
            return

        merge = self.do_merge.get()
        compress = self.do_compress.get()
        ocr = self.do_ocr.get()
        level = self.compression_level.get()

        # Map descriptive label back to numeric key
        level_key = "3"  # Default
        for k, v in COMPRESSION_LEVEL_LABELS.items():
            if v == level:
                level_key = k
                break

        if not any([merge, compress, ocr]):
            self.write_log("No actions selected.")
            return

        # Password
        pw_ok, password = self.prompt_password_if_needed(files)
        if not pw_ok:
            return

        # Confirm outputs (simplified: one final file for merge, individual for others)
        if merge:
            out = filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                initialdir=self.output_dir,
                title="Save merged PDF as",
            )
            if not out:
                return
            if not self.confirm_overwrite(out):
                return
        else:
            # We'll build per‑file outputs inside the worker
            pass

        self.save_current_settings()
        self.run_task(
            self._process_task,
            files, merge, compress, ocr, level_key, password, out if merge else None
        )

    def run_task(self, task_func, *args):
        self.job_queue.put(lambda: task_func(*args))

    def _process_task(self, files, merge, compress, ocr, level, password, out_path):
        try:
            total = 1 if merge else len(files)
            self.safe_ui(self.write_log, "Starting process...")
            self.safe_ui(self.set_status, "Processing...")

            if merge:
                self.safe_ui(self.write_log, "Merging files...")
                self.runner = CancellableCommand()
                # If also compressing/OCR after merge, merge to a temporary file first
                temp_files_to_clean = []
                try:
                    if compress or ocr:
                        fd, tmpmerged = tempfile.mkstemp(suffix=".pdf")
                        os.close(fd)
                        merge_target = tmpmerged
                        temp_files_to_clean.append(tmpmerged)
                    else:
                        merge_target = out_path
                    result = merge_pdfs(files, merge_target, password=password, runner=self.runner)
                    if not result.startswith("SUCCESS"):
                        self.safe_ui(self.write_log, f"Merge failed: {result}")
                        return
                    current = merge_target
                    if compress:
                        self.safe_ui(self.write_log, f"Compressing (level {level})...")
                        self.runner = CancellableCommand()
                        if not ocr:
                            compress_out = out_path
                        else:
                            fd, compress_out = tempfile.mkstemp(suffix=".pdf")
                            os.close(fd)
                            temp_files_to_clean.append(compress_out)
                        cres = compress_pdf(current, compress_out, level, runner=self.runner, include_summary=True, password=password)
                        if not cres.startswith("SUCCESS"):
                            self.safe_ui(self.write_log, f"Compress failed: {cres}")
                            return
                        current = compress_out
                    if ocr:
                        if has_text(current):
                            self.safe_ui(self.write_log, "Text already present – skipping OCR.")
                        else:
                            self.safe_ui(self.write_log, "Applying OCR...")
                            self.runner = CancellableCommand()
                            ores = ocr_pdf(current, os.path.dirname(out_path), output_template=os.path.basename(out_path), runner=self.runner, password=password)
                            if ores != "SUCCESS":
                                self.safe_ui(self.write_log, f"OCR failed: {ores}")
                                return
                            current = out_path

                    # Ensure final file is moved to the actual out_path if it's still in a temp file
                    if os.path.abspath(current) != os.path.abspath(out_path):
                        try:
                            import shutil
                            shutil.copy2(current, out_path)
                        except Exception as e:
                            self.safe_ui(self.write_log, f"Could not save final: {e}")
                            return
                    
                    self.safe_ui(self.write_log, f"Done: {out_path}")
                finally:
                    for tmp in temp_files_to_clean:
                        if os.path.exists(tmp):
                            try:
                                os.remove(tmp)
                            except Exception:
                                pass
            else:
                os.makedirs(self.output_dir, exist_ok=True)
                self.safe_ui(self.write_log, f"Dispatching batch of {len(files)} files to parallel workers...")
                
                # We use the existing compress_many if only compressing, 
                # but for mixed tasks we need a custom worker or sequential parallelization.
                # Simplified for now: use ProcessPoolExecutor directly here.
                
                def run_parallel_job(fp):
                    if self._cancel_event.is_set():
                        return fp, "CANCELLED"
                    
                    current = fp
                    try:
                        if compress:
                            comp_out = build_output_path(self.output_dir, "{name}_compressed.pdf", fp)
                            # Note: confirm_overwrite is tricky in parallel, we'll assume yes or handle sequentially before
                            res = compress_pdf(current, comp_out, level, include_summary=True, password=password)
                            if not res.startswith("SUCCESS"):
                                return fp, f"Compress error: {res}"
                            current = comp_out
                        
                        if ocr and not has_text(current):
                            ocr_out = build_output_path(self.output_dir, "{name}_ocr.pdf", fp)
                            res = ocr_pdf(current, self.output_dir, output_template="{name}_ocr.pdf", password=password)
                            if res != "SUCCESS":
                                return fp, f"OCR error: {res}"
                            current = ocr_out
                            
                        return fp, f"SUCCESS -> {current}"
                    except Exception as e:
                        return fp, f"ERROR: {e}"

                with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
                    futures = [executor.submit(run_parallel_job, f) for f in files]
                    for idx, future in enumerate(futures, start=1):
                        fp, res = future.result()
                        self.safe_ui(self.write_log, f"[{idx}/{len(files)}] {os.path.basename(fp)}: {res}")
                        self.safe_ui(self.update_progress, idx, len(files))

                self.safe_ui(self.write_log, "Batch parallel processing completed.")
        except Exception as e:
            logger.exception("Process task failed")
            self.safe_ui(self.write_log, f"ERROR: {e}")
        finally:
            self.safe_ui(self.set_status, "Done")
            self.safe_ui(self.refresh_file_list)


def _batch_worker(fp, output_dir, compress, ocr, level, password):
    current = fp
    try:
        if compress:
            comp_out = build_output_path(output_dir, "{name}_compressed.pdf", fp)
            res = compress_pdf(current, comp_out, level, include_summary=True, password=password)
            if not res.startswith("SUCCESS"):
                return fp, f"Compress error: {res}"
            current = comp_out
        
        if ocr and not has_text(current):
            ocr_out = build_output_path(output_dir, "{name}_ocr.pdf", fp)
            res = ocr_pdf(current, output_dir, output_template="{name}_ocr.pdf", password=password)
            if res != "SUCCESS":
                return fp, f"OCR error: {res}"
            current = ocr_out
            
        return fp, f"SUCCESS -> {current}"
    except Exception as e:
        return fp, f"ERROR: {e}"

def format_size(size_bytes):
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    # Dual-mode: CLI if arguments present, else GUI
    # Filter out multiprocessing arguments passed to workers
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--multiprocessing") and not sys.argv[1].startswith("-c"):
        from main import run, build_parser
        parser = build_parser()
        # In a bundled app, we might want to ignore the first arg if it's the exe path
        # but argparse handled sys.argv[1:] by default.
        args = parser.parse_args()
        sys.exit(run(args))
    
    try:
        root = TkinterDnD.Tk()
        app = PDFToolUI(root)
        root.mainloop()
    except Exception as e:
        logger = get_logger("crash_reporter")
        logger.exception("Fatal unhandled exception")
        messagebox.showerror("Fatal Error", f"Unexpected error:\n{e}")