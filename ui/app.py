import os
import sys
import tempfile
import threading
import queue
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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
from core.compress import COMPRESSION_LEVEL_LABELS, PERFORMANCE_PROFILES, compress_pdf, get_parallelism_settings
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

# --- Design System Constants ---
BG = "#0A0B10"
SURFACE = "#161922"
SURFACE_ALT = "#10131B"
BORDER = "#242938"
DANGER = "#FF4D6D"
SUCCESS = "#00F59B"
TEXT = "#D1D5DB"
SUBTEXT = "#9CA3AF"
DROP_BG = "#0D0F16"
ACCENT = "#4F46E5"
ACCENT_ACTIVE = "#6366F1"
DROP_BORDER = "#1F2937"
WARNING = "#FBBF24"

# Spacing Scale (based on 4px grid)
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

# Typography
FONT_H1 = ("Segoe UI", 20, "bold")
FONT_H2 = ("Segoe UI", 12, "bold")
FONT_H3 = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_CAPTION = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)

# Derived layout constants
PAD = SPACE_MD
CARD_PAD = SPACE_LG
PREVIEW_CANVAS_W = 200
PREVIEW_CANVAS_H = 280
PREVIEW_CENTER_X = 100
PREVIEW_CENTER_Y = 140
PREVIEW_FITZ_SCALE = 0.35


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
        # FIX: bbox("insert") only works on Text/Entry widgets. Use winfo geometry for
        # all other widget types (Button, Label, Checkbutton, etc.) to avoid TclError.
        try:
            x, y, _cx, cy = self.widget.bbox("insert")
            x = x + self.widget.winfo_rootx() + 27
            y = y + cy + self.widget.winfo_rooty() + 27
        except tk.TclError:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
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
        self.root.geometry("1024x800")
        self.root.minsize(980, 760)
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
        self.performance_profile = tk.StringVar(
            value=self.settings.get("performance_profile", "balanced")
        )

        geometry = self.settings.get("window_geometry")
        if geometry:
            self.root.geometry(geometry)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.dropped_files = []
        self._page_count_jobs = set()
        self._file_meta = {}
        self._metadata_executor = ThreadPoolExecutor(max_workers=2)

        # Action toggles
        self.do_compress = tk.BooleanVar(value=True)
        self.do_ocr = tk.BooleanVar(value=False)
        self.do_merge = tk.BooleanVar(value=False)
        self.do_rotate = tk.BooleanVar(value=False)

        self.level_labels = dict(COMPRESSION_LEVEL_LABELS)
        # FIX: Initial value must be a label string (matching the combobox values),
        # not a numeric key. Previously value="3" caused the label->key mapping in
        # process_all to silently fall back to default on first use.
        _default_label = self.level_labels.get("3", list(self.level_labels.values())[0])
        self.compression_level = tk.StringVar(value=_default_label)

        self.action_buttons = []
        self.drag_index = None
        self._is_processing = False

        self.job_queue = queue.Queue()
        self.preview_image = None
        self._preview_gen = 0
        self._preview_after_id = None
        self._preview_thread_path = None
        self._gs_progress_after_id = None
        self._gs_progress_pending = None
        self._blink_after_id = None
        self._blink_step = 0
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

        self._build_ui_v2()
        self._bind_ui_state()
        self.refresh_file_list()

    # ---------- UI helpers ----------
    def safe_ui(self, func, *args, **kwargs):
        self.root.after(0, lambda: func(*args, **kwargs))

    def _blink_status(self):
        """Creates a blinking ellipsis and color animation in the status bar."""
        if not self._is_processing:
            self._blink_after_id = None
            return
        
        dots = "." * (self._blink_step % 4)
        current_text = self.status_label.cget("text").rstrip(".")
        self.status_label.configure(text=f"{current_text}{dots}")
        
        # Toggle color between SUBTEXT and ACCENT for 'blinking' effect
        color = ACCENT if (self._blink_step % 2 == 0) else TEXT
        self.status_label.configure(foreground=color)
        
        self._blink_step += 1
        self._blink_after_id = self.root.after(500, self._blink_status)

    def _on_close(self):
        self.settings["window_geometry"] = self.root.winfo_geometry()
        # FIX: cancel_futures parameter requires Python 3.9+. Guard for compatibility.
        import sys as _sys
        if _sys.version_info >= (3, 9):
            self._metadata_executor.shutdown(wait=False, cancel_futures=True)
        else:
            self._metadata_executor.shutdown(wait=False)
        save_settings(self.settings)
        self.root.destroy()

    def _build_ui_v2(self):
        """Build the UI using modular components for better maintainability."""
        self._configure_style()
        self._setup_layout_containers()
        
        self._create_header()
        self._create_body()
        self._create_footer()
        
        self._setup_keyboard_shortcuts()

    def _setup_layout_containers(self):
        """Initialize the main high-level containers."""
        self.header_frame = tk.Frame(self.root, bg=BG, padx=PAD, pady=PAD)
        self.header_frame.pack(fill="x", side="top")

        self.footer_frame = tk.Frame(self.root, bg=BG, padx=PAD, pady=PAD)
        self.footer_frame.pack(fill="x", side="bottom")

        self.body_container = tk.Frame(self.root, bg=BG)
        self.body_container.pack(fill="both", expand=True, padx=PAD, pady=5)
        self.body_container.grid_columnconfigure(0, weight=5)
        self.body_container.grid_columnconfigure(1, weight=3)
        self.body_container.grid_rowconfigure(0, weight=1)

    def _create_header(self):
        """Create the top navigation and global action bar."""
        # Title and description
        title_col = tk.Frame(self.header_frame, bg=BG)
        title_col.pack(side="left", fill="x", expand=True)
        tk.Label(title_col, text="pdf-suite", fg=TEXT, bg=BG, font=FONT_H1).pack(anchor="w")
        tk.Label(
            title_col,
            text="Fast PDF merge, compression, OCR, and batch processing",
            fg=SUBTEXT, bg=BG, font=FONT_CAPTION,
        ).pack(anchor="w", pady=(2, 0))

        # Status Badges
        header_meta = tk.Frame(self.header_frame, bg=BG)
        header_meta.pack(side="left", padx=(0, SPACE_LG))
        self.file_count_badge = tk.Label(
            header_meta, text="0 files", fg=TEXT, bg=SURFACE, font=("Segoe UI", 9, "bold"), padx=10, pady=6
        )
        self.file_count_badge.pack(side="left", padx=(0, SPACE_SM))
        self.total_size_badge = tk.Label(
            header_meta, text="0 B", fg=SUBTEXT, bg=SURFACE_ALT, font=FONT_CAPTION, padx=10, pady=6
        )
        self.total_size_badge.pack(side="left")

        # Global Actions
        action_bar = tk.Frame(self.header_frame, bg=BG)
        action_bar.pack(side="right")
        self.cancel_btn = ttk.Button(action_bar, text="Cancel", command=self.cancel, style="DangerTTk.TButton")
        self.cancel_btn.pack(side="right")
        self.process_btn = ttk.Button(
            action_bar, text="Process Files", command=self.process_all, style="Accent.TButton"
        )
        self.process_btn.pack(side="right", padx=(0, SPACE_SM))
        self.action_buttons = [self.process_btn]
        ToolTip(self.process_btn, "Run selected actions (Ctrl+Enter)")
        ToolTip(self.cancel_btn, "Stop running task (Esc)")

    def _create_body(self):
        """Create the central workspace and sidebar."""
        self._create_workspace_panel()
        self._create_sidebar_panel()

    def _create_workspace_panel(self):
        """Create the left panel containing the file list and drop zone."""
        left = tk.Frame(self.body_container, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, PAD))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        # Panel Header
        left_header = tk.Frame(left, bg=SURFACE)
        left_header.grid(row=0, column=0, sticky="ew", padx=CARD_PAD, pady=(CARD_PAD, SPACE_SM))
        tk.Label(left_header, text="Workspace", fg=TEXT, bg=SURFACE, font=FONT_H2).pack(anchor="w")
        self.workspace_summary = tk.Label(
            left_header, text="Load PDFs, reorder them, then run selected actions.",
            fg=SUBTEXT, bg=SURFACE, font=FONT_CAPTION,
        )
        self.workspace_summary.pack(anchor="w", pady=(3, 0))

        # Drop Zone (Call to Action)
        self.drop_zone = tk.Label(
            left, text="Drop PDF files here or click Add", bg=DROP_BG, fg=TEXT,
            height=3, font=("Segoe UI", 11, "bold"), highlightthickness=1,
            highlightbackground=DROP_BORDER, cursor="hand2", justify="center",
        )
        self.drop_zone.grid(row=1, column=0, sticky="ew", padx=CARD_PAD, pady=(0, 10))
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind("<<Drop>>", self.handle_drop)
        self.drop_zone.bind("<Button-1>", lambda _e: self.add_files())
        self.drop_zone.bind("<Enter>", lambda _e: self.drop_zone.configure(bg=SURFACE_ALT))
        self.drop_zone.bind("<Leave>", lambda _e: self.drop_zone.configure(bg=DROP_BG))

        # File List Table
        table_frame = tk.Frame(left, bg=SURFACE)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=CARD_PAD, pady=(0, SPACE_SM))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("name", "size", "pages", "status")
        self.file_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        for col in columns: self.file_tree.heading(col, text=col.capitalize())
        self.file_tree.column("name", width=300, anchor="w")
        self.file_tree.column("size", width=90, anchor="center")
        self.file_tree.column("pages", width=70, anchor="center")
        self.file_tree.column("status", width=90, anchor="center")
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        self.file_tree.bind("<<TreeviewSelect>>", self.on_treeview_select)
        self.file_tree.bind("<ButtonPress-1>", self.start_drag)
        self.file_tree.bind("<B1-Motion>", self.drag_reorder)
        self.file_tree.bind("<ButtonRelease-1>", self.on_drag_release)
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.file_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.file_tree.configure(yscrollcommand=tree_scroll.set)

        # Toolbar
        toolbar = tk.Frame(left, bg=SURFACE)
        toolbar.grid(row=3, column=0, sticky="ew", padx=CARD_PAD, pady=(0, CARD_PAD))
        for caption, cb, tip in [
            ("Add", self.add_files, "Add PDF files (Ctrl+O)"),
            ("Remove", self.remove_selected, "Remove selected files (Del)"),
            ("Clear", self.clear_files, "Clear all files"),
            ("Move Up", lambda: self.move_selected(-1), "Move up (Alt+Up)"),
            ("Move Down", lambda: self.move_selected(1), "Move down (Alt+Down)"),
            ("Info", self.show_pdf_info, "Show PDF details"),
            ("Open Folder", self.open_output_folder, "Open output folder"),
        ]:
            btn = ttk.Button(toolbar, text=caption, command=cb, style="Toolbar.TButton")
            btn.pack(side="left", padx=4)
            ToolTip(btn, tip)

    def _create_sidebar_panel(self):
        """Create the right sidebar with preview and configuration options (scrollable)."""
        right_container = tk.Frame(self.body_container, bg=BG)
        right_container.grid(row=0, column=1, sticky="nsew")
        right_container.grid_columnconfigure(0, weight=1)
        right_container.grid_rowconfigure(0, weight=1)

        canvas = tk.Canvas(right_container, bg=BG, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(right_container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        right = tk.Frame(canvas, bg=BG)
        # FIX: Keep reference to the window to update its width on canvas resize
        canvas_window = canvas.create_window((0, 0), window=right, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            # Update the width of the inner frame to match the canvas
            canvas.itemconfig(canvas_window, width=event.width)
        
        right.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        
        # Mousewheel support: limit to when mouse is over the sidebar
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        # Preview Section
        self.preview_frame = tk.Frame(
            right, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, padx=CARD_PAD, pady=CARD_PAD
        )
        self.preview_frame.pack(fill="x", pady=(0, PAD))
        tk.Label(self.preview_frame, text="Preview", fg=TEXT, bg=SURFACE, font=FONT_H2).pack(anchor="w")
        self.preview_meta_label = tk.Label(
            self.preview_frame, text="Select file to render first page preview.",
            fg=SUBTEXT, bg=SURFACE, font=FONT_CAPTION,
        )
        self.preview_meta_label.pack(anchor="w", pady=(2, 10))
        self.preview_canvas = tk.Canvas(
            self.preview_frame, width=PREVIEW_CANVAS_W, height=PREVIEW_CANVAS_H,
            bg=DROP_BG, highlightthickness=1, highlightbackground=DROP_BORDER,
        )
        self.preview_canvas.pack()
        self.page_count_label = tk.Label(self.preview_frame, text="", fg=SUBTEXT, bg=SURFACE, font=FONT_CAPTION)
        self.page_count_label.pack(anchor="center", pady=(SPACE_SM, 0))

        # Workflow Configuration
        settings = tk.Frame(
            right, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, padx=CARD_PAD, pady=CARD_PAD
        )
        settings.pack(fill="x", pady=(0, PAD))
        tk.Label(settings, text="Workflow", fg=TEXT, bg=SURFACE, font=FONT_H2).pack(anchor="w")
        self.action_summary = tk.Label(
            settings, text="Compress enabled. OCR and merge off.", fg=SUBTEXT,
            bg=SURFACE, font=FONT_CAPTION, justify="left", wraplength=240,
        )
        self.action_summary.pack(anchor="w", pady=(2, 12))

        for var, label, tip in [
            (self.do_compress, "Compress", "Reduce file size"),
            (self.do_ocr, "OCR", "Make scanned PDFs searchable"),
            (self.do_rotate, "Rotate 90° CW", "Rotate all pages clockwise"),
            (self.do_merge, "Merge into one", "Combine all files into a single PDF"),
        ]:
            cb = ttk.Checkbutton(settings, text=label, variable=var, style="Workflow.TCheckbutton")
            cb.pack(fill="x", pady=4)
            ToolTip(cb, tip)

        for label, var, values, space in [
            ("Compression", self.compression_level, list(self.level_labels.values()), (8, 2)),
            ("Performance", self.performance_profile, list(PERFORMANCE_PROFILES), (2, 2))
        ]:
            tk.Label(settings, text=label, fg=SUBTEXT, bg=SURFACE, anchor="w").pack(fill="x", pady=space)
            picker = ttk.Combobox(settings, textvariable=var, values=values, state="readonly", width=25)
            picker.pack(fill="x", pady=SPACE_SM)
            if label == "Compression": self.level_picker = picker
            else: self.performance_picker = picker

        tk.Label(settings, text="Output folder", fg=SUBTEXT, bg=SURFACE, anchor="w").pack(fill="x", pady=2)
        out_row = tk.Frame(settings, bg=SURFACE)
        out_row.pack(fill="x", pady=SPACE_SM)
        self.output_label = tk.Label(
            out_row, text=self._truncate_path(self.output_dir), fg=TEXT,
            bg=SURFACE, anchor="w", justify="left", wraplength=180,
        )
        self.output_label.pack(side="left", fill="x", expand=True)
        ttk.Button(out_row, text="Browse", command=self.select_output, style="Toolbar.TButton").pack(side="right")

        queue_card = tk.Frame(
            right, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, padx=CARD_PAD, pady=CARD_PAD
        )
        queue_card.pack(fill="x")
        tk.Label(queue_card, text="Queue Snapshot", fg=TEXT, bg=SURFACE, font=FONT_H2).pack(anchor="w")
        self.queue_summary = tk.Label(
            queue_card, text="No files loaded yet.", fg=SUBTEXT,
            bg=SURFACE, font=FONT_CAPTION, justify="left", wraplength=240,
        )
        self.queue_summary.pack(anchor="w", pady=(SPACE_XS, 0))

    def _create_footer(self):
        """Create the activity log and progress indicators."""
        log_header = tk.Frame(self.footer_frame, bg=BG)
        log_header.pack(fill="x", pady=(0, 6))
        tk.Label(log_header, text="Activity Log", fg=TEXT, bg=BG, font=FONT_H3).pack(side="left")
        ttk.Button(log_header, text="Clear Log", command=lambda: self.log.delete("1.0", tk.END), style="Toolbar.TButton").pack(side="right")

        log_frame = tk.Frame(self.footer_frame, bg=BG)
        log_frame.pack(fill="x", expand=True, pady=5)
        self.log = scrolledtext.ScrolledText(
            log_frame, height=6, bg=SURFACE, fg=TEXT, insertbackground=TEXT, font=FONT_MONO, relief="flat",
        )
        self.log.pack(fill="both", expand=True)

        progress_frame = tk.Frame(self.footer_frame, bg=BG)
        progress_frame.pack(fill="x")
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill="x")
        status_row = tk.Frame(progress_frame, bg=BG)
        status_row.pack(fill="x", pady=(6, 0))
        self.status_label = ttk.Label(status_row, text="Ready", foreground=SUBTEXT, background=BG)
        self.status_label.pack(side="left")
        self.progress_detail = tk.Label(status_row, text="Idle", fg=SUBTEXT, bg=BG, font=FONT_CAPTION)
        self.progress_detail.pack(side="right")
        self._set_preview_text("No preview", SUBTEXT)

    def _setup_keyboard_shortcuts(self):
        """Bind global and local keyboard events."""
        self.root.bind("<Control-o>", lambda _e: self.add_files())
        self.root.bind("<Control-Return>", lambda _e: self.process_all() if not self._is_processing else None)
        self.root.bind("<Escape>", lambda _e: self.cancel())
        self.file_tree.bind("<Delete>", lambda _e: self.remove_selected())
        self.root.bind("<Alt-Up>", lambda _e: self.move_selected(-1))
        self.root.bind("<Alt-Down>", lambda _e: self.move_selected(1))

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
                        padding=(14, 7), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("Accent.TButton", background=[("active", ACCENT_ACTIVE), ("disabled", DROP_BORDER)])

        style.configure("DangerTTk.TButton", background=SURFACE, foreground=DANGER,
                        padding=(12, 7), borderwidth=0)
        style.map("DangerTTk.TButton", background=[("active", DROP_BORDER), ("disabled", DROP_BORDER)])

        style.configure("Toolbar.TButton", background=SURFACE, foreground=TEXT,
                        padding=(8, 5), borderwidth=0)
        style.map("Toolbar.TButton", background=[("active", DROP_BORDER), ("disabled", DROP_BORDER)])

        # Treeview
        style.configure("Treeview", background=DROP_BG, foreground=TEXT, fieldbackground=DROP_BG,
                        font=("Segoe UI", 10), rowheight=32, borderwidth=0)
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", TEXT)])
        style.configure("Treeview.Heading", background=SURFACE, foreground=TEXT, relief="flat",
                        font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Treeview.Heading", background=[("active", DROP_BORDER)])

        # Progressbar
        style.configure("Horizontal.TProgressbar", troughcolor="#242938",
                        background=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                        bordercolor=BORDER, thickness=16)

        # Combobox
        style.configure("TCombobox", fieldbackground=DROP_BG, background=SURFACE, foreground=TEXT,
                        arrowcolor=TEXT, font=("Segoe UI", 10), bordercolor=DROP_BORDER)
        style.map("TCombobox", fieldbackground=[("readonly", DROP_BG)],
                  selectbackground=[("readonly", DROP_BG)],
                  selectforeground=[("readonly", TEXT)])

        # Checkbutton
        style.configure("Workflow.TCheckbutton", background=SURFACE, foreground=TEXT, font=("Segoe UI", 11))
        style.map("Workflow.TCheckbutton", background=[("active", SURFACE)], foreground=[("active", TEXT)])

        # Scrollbar
        style.configure("Vertical.TScrollbar", troughcolor=BG, background=SURFACE, bordercolor=BG, arrowcolor=SUBTEXT)
        style.map("Vertical.TScrollbar", background=[("active", DROP_BORDER)])

    def _bind_ui_state(self):
        for var in (self.do_compress, self.do_ocr, self.do_merge, self.do_rotate):
            var.trace_add("write", lambda *_args: self._update_action_summary())
        self.compression_level.trace_add("write", lambda *_args: self._update_action_summary())
        self.performance_profile.trace_add("write", lambda *_args: self._update_action_summary())
        self._update_action_summary()
        self._sync_output_label()

    def _truncate_path(self, path, max_len=36):
        if len(path) <= max_len:
            return path
        return f"...{path[-(max_len - 3):]}"

    def _sync_output_label(self):
        if hasattr(self, "output_label"):
            self.output_label.configure(text=self._truncate_path(self.output_dir))

    def _update_action_summary(self):
        if not hasattr(self, "action_summary"):
            return
        parts = []
        if self.do_compress.get():
            level_label = self.level_labels.get(self.compression_level.get(), self.compression_level.get())
            parts.append(f"Compress: {level_label}")
        if self.do_ocr.get():
            parts.append("OCR")
        if self.do_rotate.get():
            parts.append("Rotate 90°")
        if self.do_merge.get():
            parts.append("Merge")
        if not parts:
            parts.append("No actions selected")
        self.action_summary.configure(
            text=" | ".join(parts) + f"\nProfile: {self.performance_profile.get()}"
        )
        self._update_workspace_summary()

    def _update_workspace_summary(self):
        if not hasattr(self, "file_count_badge"):
            return
        count = len(self.dropped_files)
        total_size = sum(os.path.getsize(fp) for fp in self.dropped_files if os.path.exists(fp))
        self.file_count_badge.configure(text=f"{count} file{'s' if count != 1 else ''}")
        self.total_size_badge.configure(text=format_size(total_size))
        if count:
            selected = len(self.file_tree.selection()) if hasattr(self, "file_tree") else 0
            self.workspace_summary.configure(
                text=f"{count} file(s) queued. Drag to reorder. {selected} selected."
            )
            merge_note = "single merged output" if self.do_merge.get() else "individual output files"
            self.queue_summary.configure(
                text=f"{count} file(s) ready for processing.\nOutputs: {merge_note}\nDestination: {self._truncate_path(self.output_dir, 42)}"
            )
        else:
            self.workspace_summary.configure(text="Load PDFs, reorder them, then run selected actions.")
            self.queue_summary.configure(text="No files loaded yet.")

    # ---------- Job queue ----------
    def _process_queue(self):
        while True:
            task = self.job_queue.get()
            self.safe_ui(self.write_log, "Starting background task...")
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
                self.safe_ui(self.set_status, "Ready")
                self.safe_ui(self.update_progress, 0, 1)
                self.job_queue.task_done()

    def set_running(self, running):
        self._is_processing = running
        state = "disabled" if running else "normal"
        for btn in self.action_buttons:
            btn.configure(state=state)
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.level_picker.configure(state="disabled" if running else "readonly")
        self.performance_picker.configure(state="disabled" if running else "readonly")
        # FIX: Start/stop the blink animation when processing state changes.
        if running:
            self._blink_step = 0
            if not self._blink_after_id:
                self._blink_status()
        else:
            if self._blink_after_id:
                self.root.after_cancel(self._blink_after_id)
                self._blink_after_id = None
            self.status_label.configure(foreground=SUBTEXT)

    def set_status(self, text):
        self.status_label.configure(text=text or "")

    def write_log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        self.log.insert(tk.END, f"[{t}] {msg}\n")
        self.log.see(tk.END)

    def update_progress(self, val, total):
        try:
            self.progress["maximum"] = total
            self.progress["value"] = val
            if total <= 1:
                # For single-step jobs, use percentage if val > 0
                if val == 0:
                    self.progress_detail.configure(text="Idle")
                else:
                    self.progress_detail.configure(text="Working...")
            else:
                self.progress_detail.configure(text=f"{val}/{total} files complete")
        except Exception as e:
            logger.error(f"Progress update failed: {e}")

    def cancel(self):
        self._cancel_event.set()
        self.set_status("Cancelling...")
        self.progress_detail.configure(text="Stopping current task")
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
                self._file_meta.setdefault(fp, self._build_file_meta(fp))
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
        self._file_meta.clear()
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
            meta = self._file_meta.setdefault(fp, self._build_file_meta(fp))
            self.file_tree.insert(
                "",
                "end",
                iid=fp,
                values=(meta["name"], meta["size_label"], meta["pages"], "Ready"),
                tags=("Ready",),
            )
            self._queue_page_count_lookup(fp)
        count = len(self.dropped_files)
        self.drop_zone.config(
            text=f"{count} file(s) loaded. Drop more PDFs to add." if count else "Drop PDF files here or click Add",
            fg=TEXT if count else SUBTEXT,
        )
        if not count:
            self.preview_meta_label.configure(text="Select file to render first page preview.")
            self._set_preview_text("No preview", SUBTEXT)
        self._update_workspace_summary()

    def _build_file_meta(self, fp):
        size = os.path.getsize(fp)
        return {
            "name": os.path.basename(fp),
            "size_label": format_size(size),
            "pages": "...",
        }

    def _queue_page_count_lookup(self, fp):
        meta = self._file_meta.get(fp)
        if not meta or meta["pages"] != "..." or fp in self._page_count_jobs:
            return
        self._page_count_jobs.add(fp)
        self._metadata_executor.submit(self._resolve_page_count, fp)

    def _resolve_page_count(self, fp):
        pages = pdf_page_count(fp) or "?"
        self.safe_ui(self._apply_page_count, fp, pages)

    def _apply_page_count(self, fp, pages):
        self._page_count_jobs.discard(fp)
        meta = self._file_meta.get(fp)
        if not meta:
            return
        meta["pages"] = pages
        if self.file_tree.exists(fp):
            self.file_tree.item(
                fp,
                values=(meta["name"], meta["size_label"], meta["pages"], "Ready"),
            )

    # ---------- Preview ----------
    def on_treeview_select(self, event=None):
        sel = self.file_tree.selection()
        if not sel:
            self.preview_meta_label.configure(text="Select file to render first page preview.")
            self._set_preview_text("No preview", SUBTEXT)
            self._update_workspace_summary()
            return
        idx = self.file_tree.index(sel[0])
        fp = self.dropped_files[idx]
        self.preview_meta_label.configure(text=os.path.basename(fp))
        self.page_count_label.configure(text="")
        self._preview_gen += 1
        gen = self._preview_gen
        if self._preview_after_id:
            self.root.after_cancel(self._preview_after_id)
        self._preview_after_id = self.root.after(150, lambda g=gen, f=fp: self._start_preview(g, f))
        self._update_workspace_summary()

    def _start_preview(self, gen, path):
        self._preview_after_id = None
        if gen != self._preview_gen:
            return
        self._preview_thread_path = path
        threading.Thread(target=self._render_preview, args=(gen, path), daemon=True).start()

    def _render_preview(self, gen, path):
        import fitz
        from PIL import Image
        # FIX: Use context manager to ensure fitz document is always closed,
        # preventing file handle / memory leaks on every preview render.
        try:
            with fitz.open(path) as doc:
                page_count = len(doc)
                if doc.is_encrypted:
                    self.safe_ui(self._set_preview_text, "Encrypted", WARNING)
                    return
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(PREVIEW_FITZ_SCALE, PREVIEW_FITZ_SCALE))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail((PREVIEW_CANVAS_W, PREVIEW_CANVAS_H))
            self.safe_ui(self._update_preview, img, page_count, gen, path)
        except Exception as e:
            # FIX: Log the actual exception instead of silently swallowing it.
            logger.debug("Preview render failed for %s: %s", path, e)
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
        meta = self._file_meta.setdefault(path, self._build_file_meta(path))
        meta["pages"] = page_count
        self.preview_image = ImageTk.PhotoImage(img)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(
            PREVIEW_CENTER_X, PREVIEW_CENTER_Y, image=self.preview_image, anchor="center"
        )
        self.page_count_label.configure(text=f"Page 1 of {page_count}")
        if self.file_tree.exists(path):
            self.file_tree.item(
                path,
                values=(meta["name"], meta["size_label"], meta["pages"], "Ready"),
            )

    # ---------- Settings ----------
    def select_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir = folder
            self._sync_output_label()
            self._update_workspace_summary()
            self.save_current_settings()

    def save_current_settings(self):
        self.settings["output_dir"] = self.output_dir
        self.settings["performance_profile"] = self.performance_profile.get()
        save_settings(self.settings)

    def _parallelism(self, file_count):
        profile = self.performance_profile.get()
        return get_parallelism_settings(file_count, profile=profile)

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
        return messagebox.askyesno("Overwrite?", f"{path}\nalready exists. Overwrite?")

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
        rotate = self.do_rotate.get()
        level = self.compression_level.get()

        # Map descriptive label back to numeric key
        level_key = "3"  # Default
        for k, v in COMPRESSION_LEVEL_LABELS.items():
            if v == level:
                level_key = k
                break

        if not any([merge, compress, ocr, rotate]):
            self.write_log("No actions selected.")
            return

        # Password
        pw_ok, password = self.prompt_password_if_needed(files)
        if not pw_ok:
            return

        # FIX: Initialize out=None before the conditional so it is always defined.
        # Previously out was only assigned inside the if-merge block; while Python's
        # ternary short-circuit prevented an actual UnboundLocalError in the original
        # code, the intent is clearer and safer with explicit initialization.
        out = None
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

        self.save_current_settings()
        self.write_log("Task queued for background execution.")
        self.run_task(
            self._process_task,
            files, merge, compress, ocr, rotate, level_key, password, out
        )

    def run_task(self, task_func, *args):
        self.job_queue.put(lambda: task_func(*args))

    def _process_task(self, files, merge, compress, ocr, rotate, level, password, out_path):
        from core.pipeline import PipelineRunner, MergeStep, CompressStep, OCRStep, RotateStep
        try:
            max_workers, threads_per_worker = self._parallelism(len(files))
            self.safe_ui(self.write_log, "Starting process...")
            self.safe_ui(self.set_status, "Processing...")
            self.safe_ui(self.update_progress, 0, len(files))
            self.safe_ui(
                self.write_log,
                f"Profile: {self.performance_profile.get()} | workers={max_workers} | threads/worker={threads_per_worker}",
            )

            if merge:
                # Sequential Pipeline for Merged Result
                steps = [MergeStep(password=password)]
                if rotate:
                    steps.append(RotateStep(angle=90, password=password))
                if compress:
                    steps.append(CompressStep(level=level, password=password, threads=threads_per_worker))
                if ocr:
                    steps.append(OCRStep(password=password, threads=threads_per_worker))

                def pipeline_cb(cur, total, msg):
                    self.safe_ui(self.write_log, msg)
                    self.safe_ui(self.update_progress, cur, total)

                self.runner = PipelineRunner(steps, progress_callback=pipeline_cb)
                result = self.runner.run(files, out_path)
                
                if result == "SUCCESS":
                    self.safe_ui(self.update_progress, len(steps), len(steps))
                    self.safe_ui(self.write_log, "Job complete.")
                    self.safe_ui(messagebox.showinfo, "Success", f"Task completed successfully!\n\nOutput: {out_path}")
                else:
                    self.safe_ui(self.write_log, result)
                    self.safe_ui(messagebox.showerror, "Task Error", result)
            else:
                # Batch Processing with Parallel Workers
                os.makedirs(self.output_dir, exist_ok=True)
                self.safe_ui(self.write_log, f"Dispatching batch of {len(files)} files to parallel workers...")

                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(
                            _batch_worker,
                            f,
                            self.output_dir,
                            compress,
                            ocr,
                            rotate,
                            level,
                            password,
                            threads_per_worker,
                        )
                        for f in files
                    ]
                    for idx, future in enumerate(futures, start=1):
                        # FIX: Check cancel event between futures so the user can
                        # abort a batch run. Previously Cancel had no effect in batch
                        # mode because self.runner was None and no cancel check existed.
                        if self._cancel_event.is_set():
                            self.safe_ui(self.write_log, "Batch cancelled by user.")
                            # Cancel remaining pending futures (idx is 1-based, futures 0-based)
                            for f in futures[idx - 1:]:
                                f.cancel()
                            break
                        fp, res = future.result()
                        self.safe_ui(self.write_log, f"[{idx}/{len(files)}] {os.path.basename(fp)}: {res}")
                        self.safe_ui(self.update_progress, idx, len(files))

                if not self._cancel_event.is_set():
                    self.safe_ui(self.write_log, "Batch complete.")
                    self.safe_ui(messagebox.showinfo, "Success", f"All {len(files)} files processed successfully!\n\nDestination: {self.output_dir}")
        except Exception as e:
            logger.exception("Process task failed")
            self.safe_ui(self.write_log, f"ERROR: {e}")
        finally:
            self.safe_ui(self.set_status, "Done")
            self.safe_ui(self.refresh_file_list)


def _batch_worker(fp, output_dir, compress, ocr, rotate, level, password, threads_per_worker):
    from core.pipeline import PipelineRunner, CompressStep, OCRStep, RotateStep
    try:
        steps = []
        if rotate:
            steps.append(RotateStep(angle=90, password=password))
        if compress:
            steps.append(CompressStep(level=level, password=password, threads=threads_per_worker))
        if ocr:
            steps.append(OCRStep(password=password, threads=threads_per_worker))
            
        if not steps:
            return fp, "No actions selected"
            
        # Determine final output path for this file
        # Use simple naming pattern for batch: processed_{name}
        out_name = build_output_path(output_dir, "processed_{name}.pdf", fp)
        
        runner = PipelineRunner(steps)
        result = runner.run([fp], out_name)
        
        if result == "SUCCESS":
            return fp, f"SUCCESS -> {out_name}"
        return fp, result
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


if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    # Enable High-DPI awareness on Windows to fix blurry text
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    
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
