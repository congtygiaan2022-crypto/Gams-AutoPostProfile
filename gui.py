import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
# Đảm bảo thư mục làm việc luôn là thư mục chứa gui.py (cần thiết khi double-click)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)
from database import Database
from gemlogin_api import GemLoginAPI
from gpmlogin_api import GPMLoginAPI
from facebook_automator import FacebookAutomator
import time
import webbrowser
import psutil

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Công Cụ Đăng Reels Tự Động - Phiên bản v2.0 (GPM/GemLogin)")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.db = Database()
        self.automator = None
        self.stop_flag = False
        self.active_procs = [] # Track worker subprocesses
        self.active_workers = [] # Track worker details for cleanup
        self._build_ui()
        self.refresh_ui()
        # Hook close event
        self.protocol("WM_DELETE_WINDOW", self.on_app_exit)

    def _build_ui(self):
        # ─── TOP TOOLBAR ──────────────────────────────────────
        self.toolbar = tk.Frame(self, bg="#f8f9fa", relief="raised", bd=1, pady=5)
        self.toolbar.pack(side="top", fill="x")

        # Group 1: Page Management
        mgmt_frame = tk.LabelFrame(self.toolbar, text="Quản Lý Nick", bg="#f8f9fa", font=("Arial", 9, "bold"))
        mgmt_frame.pack(side="left", padx=5, pady=2)
        btn_style = dict(relief="flat", cursor="hand2", padx=10, pady=5, font=("Arial", 9))
        tk.Button(mgmt_frame, text="+ Thêm Page", bg="#4a90d9", fg="white",
                  command=self.add_nick_ui, **btn_style).pack(side="left", padx=2)
        tk.Button(mgmt_frame, text="🗑️  Xóa Hết", bg="#888", fg="white",
                  command=self.clear_all_ui, **btn_style).pack(side="left", padx=2)
        tk.Button(mgmt_frame, text="👥 Nhóm", bg="#4a90d9", fg="white",
                  command=self.group_management_ui, **btn_style).pack(side="left", padx=2)
        tk.Button(mgmt_frame, text="🪄 Auto Folder", bg="#2e7d32", fg="white",
                  command=self.auto_map_folders_ui, **btn_style).pack(side="left", padx=2)

        # Group 2: Settings & Global Actions
        settings_frame = tk.LabelFrame(self.toolbar, text="Cài Đặt Tổng", bg="#f8f9fa", font=("Arial", 9, "bold"))
        settings_frame.pack(side="left", padx=5, pady=2)
        tk.Button(settings_frame, text="💬 Bình Luận", bg="#7c5cbf", fg="white",
                  command=self.set_comment_ui, **btn_style).pack(side="left", padx=2)
        tk.Button(settings_frame, text="📁… Lịch Chạy", bg="#e07b39", fg="white",
                  command=self.scheduling_settings_ui, **btn_style).pack(side="left", padx=2)
        tk.Button(settings_frame, text="🌐 Profile", bg="#e67e22", fg="white",
                  command=self.browser_settings_ui, **btn_style).pack(side="left", padx=2)
        tk.Button(settings_frame, text="📊 Log/Thống Kê", bg="#3a9a5c", fg="white",
                  command=self.show_video_log_ui, **btn_style).pack(side="left", padx=2)

        # Selection Control (inside settings frame)
        sel_frame = tk.Frame(settings_frame, bg="#f8f9fa")
        sel_frame.pack(side="left", padx=5)
        tk.Button(sel_frame, text="Chọn Hết", bg="#3a9a5c", fg="white", font=("Arial", 8),
                  command=lambda: self.set_all_enabled(True), relief="flat", padx=5).pack(pady=1)
        tk.Button(sel_frame, text="Bỏ Chọn", bg="#888", fg="white", font=("Arial", 8),
                  command=lambda: self.set_all_enabled(False), relief="flat", padx=5).pack(pady=1)
        tk.Button(sel_frame, text="Gán Profile", bg="#e07b39", fg="white", font=("Arial", 8),
                  command=self.bulk_assign_ui, relief="flat", padx=5).pack(pady=1)

        # Group 3: Execution Control
        exec_frame = tk.LabelFrame(self.toolbar, text="Điều Khiển Chạy", bg="#f8f9fa", font=("Arial", 9, "bold"))
        exec_frame.pack(side="left", padx=5, pady=2)
        
        # Mode Selection
        self.run_mode_var = tk.StringVar()
        mode_map = {"post_and_comment": "Đăng + Comment", "post_only": "Chỉ Đăng", "comment_only": "Chỉ Comment"}
        self.run_mode_var.set(mode_map.get(self.db.get_run_mode(), "Đăng + Comment"))
        mode_combo = ttk.Combobox(exec_frame, textvariable=self.run_mode_var,
                                   values=["Đăng + Comment", "Chỉ Đăng", "Chỉ Comment"],
                                   state="readonly", width=15)
        mode_combo.pack(side="left", padx=5)
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        self.btn_start = tk.Button(exec_frame, text="▶ BẮT ĐẦU", bg="#3a9a5c", fg="white",
                                   command=self.start_posting, relief="flat", font=("Arial", 10, "bold"), padx=15)
        self.btn_start.pack(side="left", padx=5)
        self.btn_stop = tk.Button(exec_frame, text="⏹ DỪNG", bg="#c0392b", fg="white",
                                  command=self.stop_posting, state="disabled", relief="flat", font=("Arial", 10, "bold"), padx=15)
        self.btn_stop.pack(side="left", padx=5)

        # Group 4: Options
        opts_frame = tk.LabelFrame(self.toolbar, text="Tùy Chọn", bg="#f8f9fa", font=("Arial", 9, "bold"))
        opts_frame.pack(side="left", padx=5, pady=2)
        self.skip_commented_var = tk.BooleanVar(value=self.db.get_skip_commented())
        tk.Checkbutton(opts_frame, text="Bỏ qua bài cũ", variable=self.skip_commented_var,
                       bg="#f8f9fa", command=lambda: self.db.set_skip_commented(self.skip_commented_var.get())).pack(anchor="w")
        self.auto_delete_var = tk.BooleanVar(value=self.db.get_auto_delete_videos())
        tk.Checkbutton(opts_frame, text="Tự xóa video", variable=self.auto_delete_var,
                       bg="#f8f9fa", command=self.toggle_auto_delete).pack(anchor="w")

        # ── MAIN CONTENT ──────────────────────────────────────
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=5, sashrelief=tk.RAISED, bg="#d9d9d9")
        self.paned_window.pack(fill="both", expand=True)

        # Main Scrollable list for nicks (in left pane)
        list_container = tk.Frame(self.paned_window, bg="#ffffff")
        self.paned_window.add(list_container, stretch="always")
        
        self.canvas = tk.Canvas(list_container, bg="#ffffff", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.main_frame = tk.Frame(self.canvas, bg="#ffffff")
        
        self.main_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        
        def _on_canvas_configure(e):
            self.canvas.itemconfig(self.canvas.find_withtag("all")[0], width=e.width)
        self.canvas.bind("<Configure>", _on_canvas_configure)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Log box (in right pane)
        log_container = tk.Frame(self.paned_window, bg="#f0f0f0", width=300)
        log_container.pack_propagate(False)
        self.paned_window.add(log_container, minsize=200)

        self.log_text = scrolledtext.ScrolledText(log_container, font=("Consolas", 9), state="normal", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.main_frame = tk.Frame(self.canvas, bg="#e8e8e8")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        # --- Global Folders Section ---
        self.global_folders_frame = tk.LabelFrame(self.main_frame, text=" 📁 Thư Mục Video Dùng Chung (Tất cả Nick) ",
                                                 font=("Arial", 11, "bold"), bg="#ffffff", relief="groove", bd=2)
        self.global_folders_frame.pack(fill="x", padx=10, pady=10)
        
        self.global_list_frame = tk.Frame(self.global_folders_frame, bg="#ffffff")
        self.global_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        tk.Button(self.global_folders_frame, text="+ Thêm Thư Mục Chung",
                                    bg="#4a90d9", fg="white", relief="flat", padx=10,
                                    command=self.add_global_folder_ui).pack(pady=5)

        # --- Global Video Limits ---
        limit_frame = tk.Frame(self.global_folders_frame, bg="#ffffff")
        limit_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(limit_frame, text="Số video mỗi lần chạy (áp dụng tất cả Nick Cá Nhân):",
                 bg="#ffffff", font=("Arial", 9, "bold")).pack(side="left")
        
        g_min, g_max = self.db.get_global_video_limits()
        self.global_min_entry = tk.Entry(limit_frame, width=5, bd=1, relief="solid")
        self.global_min_entry.insert(0, str(g_min))
        self.global_min_entry.pack(side="left", padx=(10, 2))
        tk.Label(limit_frame, text="-", bg="#ffffff").pack(side="left")
        self.global_max_entry = tk.Entry(limit_frame, width=5, bd=1, relief="solid")
        self.global_max_entry.insert(0, str(g_max))
        self.global_max_entry.pack(side="left", padx=(2, 10))

        def save_global_limits(event=None):
            try:
                vmin = int(self.global_min_entry.get())
                vmax = int(self.global_max_entry.get())
                if vmin > 0 and vmax >= vmin:
                    self.db.set_global_video_limits(vmin, vmax)
            except: pass
        self.global_min_entry.bind("<FocusOut>", save_global_limits)
        self.global_max_entry.bind("<FocusOut>", save_global_limits)

        self._refresh_global_folders_ui()
        self.main_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mode_change(self, event=None):
        map_mode = {"Đăng + Comment": "post_and_comment",
                    "Chỉ Đăng": "post_only",
                    "Chỉ Comment": "comment_only"}
        choice = self.run_mode_var.get()
        self.db.set_run_mode(map_mode.get(choice, "post_and_comment"))
        self.log(f"Đã chọn chế độ: {choice}")

    def refresh_ui(self):
        if threading.current_thread() != threading.main_thread():
            self.after(0, self.refresh_ui)
            return
        
        for widget in self.main_frame.winfo_children():
            if widget != self.global_folders_frame: # Keep global section
                widget.destroy()
        
        self._refresh_global_folders_ui()
        
        # Build cards first (FAST)
        nicks = self.db.get_nicks()
        for i, page in enumerate(nicks):
            self._build_page_card(i, page)
        
        # Start background profile pre-fetching
        if not hasattr(self, '_profile_cache'):
            self._profile_cache = {}
            threading.Thread(target=self._background_fetch_profiles, daemon=True).start()

    def _background_fetch_profiles(self):
        browsers = self.db.get_browsers()
        new_cache = {}
        for b in browsers:
            b_id = b['id']
            try:
                # Use a small timeout for startup
                api = GemLoginAPI(b['api_url']) if b['type'] == 'gemlogin' else GPMLoginAPI(b['api_url'])
                profiles = api.get_profiles()
                new_cache[b_id] = profiles if profiles is not None else []
            except:
                new_cache[b_id] = []
        self._profile_cache = new_cache
        self.log("Đã tải xong danh sách Profile trình duyệt.")
        # We don't need to refresh entire UI, just notify that profiles are ready

    def _build_page_card(self, i, page):
        card = tk.LabelFrame(self.main_frame, text="",
                             bg="#ffffff", relief="groove", bd=1)
        card.pack(fill="x", padx=8, pady=5, ipady=5)

        # Row 1: Checkbox + Name + Link
        row1 = tk.Frame(card, bg="#ffffff")
        row1.pack(fill="x", padx=8, pady=(5, 2))

        enabled_var = tk.BooleanVar(value=page.get('enabled', True))
        def toggle_enable(idx=i, var=enabled_var):
            self.db.update_page_enabled(idx, var.get())
        tk.Checkbutton(row1, variable=enabled_var, bg="#ffffff", command=toggle_enable).pack(side="left")

        tk.Label(row1, text=f"#{i+1}", font=("Arial", 10, "bold"), bg="#ffffff").pack(side="left", padx=5)
        
        tk.Label(row1, text="Tên:", bg="#ffffff", width=5, anchor="w").pack(side="left")
        name_entry = tk.Entry(row1, font=("Arial", 10), bd=1, relief="solid")
        name_entry.insert(0, page.get('name', ''))
        name_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        name_entry.bind("<FocusOut>", lambda e, idx=i, ent=name_entry:
                        self.db.update_nick_name(idx, ent.get()))

        # Group selection
        tk.Label(row1, text="Nhóm:", bg="#ffffff", width=6, anchor="w").pack(side="left", padx=(10, 0))
        groups = self.db.get_groups()
        group_names = [g['name'] for g in groups]
        g_combo = ttk.Combobox(row1, values=["(Không nhóm)"] + group_names, state="readonly", width=15)
        g_combo.pack(side="left")

        # Set current group
        curr_g_id = page.get('group_id', '')
        curr_g_name = "(Không nhóm)"
        if curr_g_id:
            for g in groups:
                if g['id'] == curr_g_id:
                    curr_g_name = g['name']
                    break
        g_combo.set(curr_g_name)

        def on_group_change(event, p_idx=i, cb=g_combo, grps=groups):
            choice = cb.get()
            new_g_id = ""
            if choice != "(Không nhóm)":
                for g in grps:
                    if g['name'] == choice:
                        new_g_id = g['id']
                        break
            self.db.update_page_group(p_idx, new_g_id)
            self.log(f"Đã gán Nick #{p_idx+1} vào nhóm: {choice}")
            # Refresh card to show browser changes
            self.refresh_ui()

        g_combo.bind("<<ComboboxSelected>>", on_group_change)

        # Row 2: Link
        row2 = tk.Frame(card, bg="#ffffff")
        row2.pack(fill="x", padx=8, pady=2)

        tk.Label(row2, text="Link:", bg="#ffffff", width=5, anchor="w").pack(side="left")
        link_entry = tk.Entry(row2, font=("Arial", 9), bd=1, relief="solid", fg="#333")
        link_entry.insert(0, page.get('link', ''))
        link_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        link_entry.bind("<FocusOut>", lambda e, idx=i, ent=link_entry:
                        self.db.update_link(idx, ent.get()))

        # Unified Selection
        tk.Label(row2, text="Profile:", bg="#ffffff", width=7, anchor="w").pack(side="left", padx=(10, 0))
        # Unified profile names will be like "[Gem] Profile 1"
        p_combo = ttk.Combobox(row2, state="readonly", width=35)
        p_combo.pack(side="left")

        def refresh_unified_profiles(idx_val=i, combo=p_combo):
            # Clear cache for all and re-load
            if hasattr(self, '_profile_cache'):
                self._profile_cache.clear()
            self._update_card_profiles(idx_val, combo)
            self.log(f"Đã làm mới danh sách profile cho Nick #{idx_val+1}")
        
        tk.Button(row2, text="🔄", command=refresh_unified_profiles, bg="#f0f0f0", relief="flat", padx=2).pack(side="left")

        # Initialize profiles for this card
        self._init_card_profile(i, p_combo)

        # Row 3: Buttons
        row3 = tk.Frame(card, bg="#ffffff")
        row3.pack(fill="x", padx=8, pady=2)
        
        # Action buttons (right side)
        btn_opts = dict(relief="flat", cursor="hand2", padx=6, pady=2)
        tk.Button(row3, text="Lịch Sử", bg="#7c5cbf", fg="white",
                  command=lambda idx=i: self.view_log_ui(idx), **btn_opts).pack(side="right", padx=2)
        tk.Button(row3, text="Xóa", bg="#c0392b", fg="white",
                  command=lambda idx=i: self.remove_page(idx), **btn_opts).pack(side="right", padx=2)
        tk.Button(row3, text="Thêm Path", bg="#2e7d32", fg="white",
                  command=lambda idx=i: self.add_folder_manual(idx), **btn_opts).pack(side="right", padx=2)
        tk.Button(row3, text="Thêm Folder", bg="#4a90d9", fg="white",
                  command=lambda idx=i: self.browse_folders(idx), **btn_opts).pack(side="right", padx=2)
        tk.Button(row3, text="Log Ngày", bg="#3a9a5c", fg="white",
                  command=lambda name=page.get('name', ''): self.show_video_log_ui(filter_name=name),
                  **btn_opts).pack(side="right", padx=2)

        # Row 4: Folders
        row4 = tk.Frame(card, bg="#ffffff")
        row4.pack(fill="x", padx=8, pady=(2, 5))

        if not page.get('folders'):
            tk.Label(row4, text="⚠️ Chưa có thư mục video", fg="#c0392b",
                     bg="#ffffff", font=("Arial", 9, "bold italic")).pack(anchor="w")
        else:
            for j, folder in enumerate(page['folders']):
                f_row = tk.Frame(row4, bg="#ffffff")
                f_row.pack(fill="x", pady=1)
                
                v_count = self.db.get_video_count(folder)
                count_color = "#3a9a5c" if v_count > 0 else "#c0392b"
                count_text = f"({v_count} videos)" if v_count > 0 else "(0 videos - EMPTY)"
                
                tk.Label(f_row, text=f"📁  {folder}", anchor="w",
                         bg="#ffffff", font=("Arial", 9)).pack(side="left")
                tk.Label(f_row, text=count_text, bg="#ffffff",
                         fg=count_color, font=("Arial", 8, "bold")).pack(side="left", padx=5)
                tk.Button(f_row, text="x", fg="gray", bg="#ffffff",
                          relief="flat", cursor="hand2",
                          command=lambda p_idx=i, f_idx=j: self.remove_folder(p_idx, f_idx)
                          ).pack(side="right")

    def _update_card_profiles(self, idx, combo):
        # Use pre-fetched profiles from refresh_ui cycle to avoid freezing
        browsers = self.db.get_browsers()
        all_options = []
        unified_p_map = {} # Map option string -> (browser_id, profile_id, profile_name)
        
        if not hasattr(self, '_profile_cache'):
            # Fallback if called outside refresh_ui
            self._profile_cache = {}

        for b in browsers:
            b_id = b['id']
            b_name = b['name']
            profiles = self._profile_cache.get(b_id, [])
            if not profiles and b_id not in self._profile_cache:
                # Try fetching if missing (rare)
                try:
                    api = GemLoginAPI(b['api_url']) if b['type'] == 'gemlogin' else GPMLoginAPI(b['api_url'])
                    profiles = api.get_profiles() or []
                    self._profile_cache[b_id] = profiles
                except:
                    self._profile_cache[b_id] = []
            
            for p in profiles:
                p_name = p.get('name', p.get('title', p.get('profile_name', 'Unknown')))
                p_id = p.get('id', p.get('profile_id'))
                opt = f"[{b_name}] {p_name}"
                all_options.append(opt)
                unified_p_map[opt] = (b_id, p_id, p_name)
        
        combo['values'] = all_options
        
        # --- SET INITIAL VALUE FROM DB ---
        nicks = self.db.get_nicks()
        if idx < len(nicks):
            Nick = nicks[idx]
            curr_b_id = Nick.get('browser_id')
            curr_p_id = Nick.get('profile_id')
            if curr_b_id and curr_p_id:
                # Find matching option in our unified map
                found_opt = None
                for opt, (b_id, p_id, p_name) in unified_p_map.items():
                    if b_id == curr_b_id and str(p_id) == str(curr_p_id):
                        found_opt = opt
                        break
                
                final_val = ""
                if found_opt:
                    final_val = found_opt
                else:
                    # If profile not found in current API list, show placeholder using stored name
                    p_name_stored = Nick.get('profile_name', 'Unknown')
                    b_name_stored = "Unknown"
                    target_b = self.db.get_browser_by_id(curr_b_id)
                    if target_b: b_name_stored = target_b['name']
                    final_val = f"[{b_name_stored}] {p_name_stored}"
                
                if final_val:
                    # Use after to ensure it takes effect after packing
                    self.after(50, lambda v=final_val: combo.set(v))

        # Store the map for this page card
        if not hasattr(self, '_page_unified_maps'):
            self._page_unified_maps = {}
        self._page_unified_maps[idx] = unified_p_map

        def on_unified_select(event, p_idx=idx, p_var=None, card_combo=combo):
            opt = card_combo.get()
            if opt in unified_p_map:
                b_id, p_id, p_name = unified_p_map[opt]
                self.db.update_page_browser(p_idx, b_id)
                self.db.update_page_profile(p_idx, p_id, p_name)
                self.log(f"Đã gán {opt} cho Nick #{p_idx+1}")

        combo.bind("<<ComboboxSelected>>", on_unified_select)

    def _init_card_profile(self, idx, combo):
        # Initial population of the dropdown
        self._update_card_profiles(idx, combo)

    # ── Popup Windows ─────────────────────────────────────────
    def view_log_ui(self, index):
        page = self.db.get_nicks()[index]
        logs = self.db.get_logs(page['link'])
        win = tk.Toplevel(self)
        win.title(f"Lịch Sử: {page.get('name', page['link'])}")
        win.geometry("700x450")
        win.attributes("-topmost", True)
        
        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(frame, text="Lịch Sử Đăng Bài", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 8))
        txt = scrolledtext.ScrolledText(frame, font=("Consolas", 10), wrap="word")
        txt.pack(fill="both", expand=True)
        
        if not logs:
            txt.insert("1.0", "Chưa có lịch sử.")
        else:
            for log in reversed(logs):
                status_mark = "✓" if "Success" in log.get('status', '') else "✖"
                line = f"[{log.get('timestamp', '')}] {status_mark} {log.get('video', '')} - {log.get('status', '')}"
                if log.get('link') and "Captured" not in log.get('link', ''):
                    line += f"\n  → {log.get('link', '')}"
                txt.insert("end", line + "\n\n")
        txt.configure(state="disabled")

    def set_comment_ui(self):
        win = tk.Toplevel(self)
        win.title("Cài Đặt Bình Luận")
        win.geometry("600x650") # Tăng chiều cao để chứa thêm checkbox
        win.attributes("-topmost", True)
        
        # --- Template Section ---
        tk.Label(win, text="Mẫu Bình Luận (hỗ trợ {a|b|c})",
                 font=("Arial", 12, "bold")).pack(padx=15, pady=(15, 5), anchor="w")
        txt = scrolledtext.ScrolledText(win, font=("Arial", 11), height=10, wrap="word")
        txt.pack(fill="x", padx=15, pady=5)
        txt.insert("1.0", self.db.get_comment_template())
        
        # --- Strategy Section ---
        strat_frame = tk.LabelFrame(win, text=" Chiến thuật bình luận (Thứ tự ưu tiên từ trên xuống) ",
                                     font=("Arial", 11, "bold"), padx=10, pady=10)
        strat_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        strategies = self.db.get_comment_strategies()
        vars = {}
        strat_labels = {
            "home_scroll": "1. Bình luận qua Trang chủ (Home Scroll)",
            "feed_grid": "2. Bình luận qua Bảng feed & Lưới (Feed & Grid)",
            "published_panel": "3. Bình luận qua Bài viết đã đăng (Bảng chi tiết)",
            "published_inline": "4. Bình luận qua Bài viết đã đăng (Trực tiếp trên danh sách)",
            "insight_overview": "5. Bình luận qua Insights: Tổng quan nội dung",
            "insight_content": "6. Bình luận qua Insights: Tất cả nội dung"
        }
        for key, label in strat_labels.items():
            var = tk.BooleanVar(value=strategies.get(key, True))
            vars[key] = var
            tk.Checkbutton(strat_frame, text=label, variable=var, font=("Arial", 10)).pack(anchor="w", pady=2)

        # --- Buttons ---
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        def save():
            # Save template
            self.db.set_comment_template(txt.get("1.0", "end-1c"))
            # Save strategies
            new_strats = {k: v.get() for k, v in vars.items()}
            self.db.set_comment_strategies(new_strats)
            self.log("Đã lưu mẫu và chiến thuật bình luận.")
            win.destroy()
            
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=15, pady=5, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Lưu Cài Đặt", relief="flat", bg="#7c5cbf", fg="white",
                  padx=15, pady=5, command=save).pack(side="right", padx=5)

    def browser_settings_ui(self):
        win = tk.Toplevel(self)
        win.title("Cấu Hình Trình Duyệt")
        win.geometry("700x500")
        win.attributes("-topmost", True)
        
        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        # Browser Connections Section
        tk.Label(main_frame, text="Quản Lý Kết Nối Đa Điểm (Song Song)", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 15))
        
        list_frame = tk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True)
        
        def refresh_list():
            for widget in list_frame.winfo_children():
                widget.destroy()
            
            # --- DEDICATED SLOTS FOR MULTI-POINT ---
            browsers = self.db.get_browsers()
            for b_id in ["gemlogin_default", "gpmlogin_default"]:
                b = self.db.get_browser_by_id(b_id)
                if not b: continue
                
                row = tk.Frame(list_frame, pady=8, bg="#f0f4f8", relief="groove", bd=1)
                row.pack(fill="x", pady=4)
                
                tk.Label(row, text="Tên:", font=("Arial", 9), bg="#f0f4f8").pack(side="left", padx=(10, 0))
                name_ent = tk.Entry(row, width=15, font=("Arial", 10, "bold"))
                name_ent.insert(0, b['name'])
                name_ent.pack(side="left", padx=5)
                
                tk.Label(row, text="Loại:", font=("Arial", 9), bg="#f0f4f8").pack(side="left", padx=(5, 0))
                type_var = tk.StringVar(value=b['type'])
                type_combo = ttk.Combobox(row, textvariable=type_var, values=["gemlogin", "gpmlogin"], width=10, state="readonly")
                type_combo.pack(side="left", padx=2)
                
                tk.Label(row, text="API URL:", font=("Arial", 9), bg="#f0f4f8").pack(side="left", padx=(10, 0))
                url_ent = tk.Entry(row, width=25, font=("Consolas", 10))
                url_ent.insert(0, b['api_url'])
                url_ent.pack(side="left", padx=5)
                
                def make_save(bid=b_id, n_ent=name_ent, t_var=type_var, u_ent=url_ent):
                    def _s():
                        new_name = n_ent.get().strip()
                        new_type = t_var.get()
                        new_url = u_ent.get().strip()
                        self.db.update_browser(bid, new_name, new_type, new_url)
                        self.log(f"Đã lưu cấu hình {new_name} ({new_type})")
                        self.refresh_ui()
                    return _s
                
                def make_test(t_var=type_var, ent=url_ent):
                    def _t():
                        url = ent.get().strip()
                        t = t_var.get()
                        self.log(f"Đang kiểm tra {t} tại {url}...")
                        try:
                            api = GemLoginAPI(url) if t == "gemlogin" else GPMLoginAPI(url)
                            profiles = api.get_profiles()
                            # Now check if profiles is NOT None (None means failure)
                            if profiles is not None:
                                messagebox.showinfo("Kết nối", f"Kết nối {t} thành công!\nTìm thấy {len(profiles)} profiles.")
                                self.log(f"Kết nối {t} thành công: {len(profiles)} profiles.")
                            else:
                                messagebox.showerror("Kết nối", f"Không thể kết nối đến {t} hoặc URL không đúng.")
                                self.log(f"Kết nối {t} thất bại.")
                        except Exception as e:
                            messagebox.showerror("Lỗi", f"Lỗi hệ thống: {e}")
                    return _t
                
                tk.Button(row, text="Lưu", command=make_save(), bg="#2e7d32", fg="white", relief="flat", width=8).pack(side="left", padx=5)
                tk.Button(row, text="Test", command=make_test(), bg="#1976d2", fg="white", relief="flat", width=8).pack(side="left", padx=5)

            ttk.Separator(list_frame).pack(fill="x", pady=15)
            
            # --- CUSTOM / REMOTE Hubs ---
            tk.Label(list_frame, text="Thêm Kết Nối Khác (Tùy Chỉnh):", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
            
            add_row = tk.Frame(list_frame)
            add_row.pack(fill="x", pady=5)
            n_new = tk.Entry(add_row, width=15)
            n_new.insert(0, "Sub Hub")
            n_new.pack(side="left", padx=2)
            t_new = ttk.Combobox(add_row, values=["gemlogin", "gpmlogin"], width=10, state="readonly")
            t_new.set("gpmlogin")
            t_new.pack(side="left", padx=2)
            u_new = tk.Entry(add_row, width=20)
            u_new.insert(0, "http://")
            u_new.pack(side="left", padx=2)
            
            def add_new():
                name = n_new.get().strip()
                if name:
                    self.db.add_browser(name, t_new.get(), u_new.get().strip())
                    refresh_list()
            tk.Button(add_row, text="+ Thêm Hub", command=add_new, bg="#7b1fa2", fg="white", relief="flat", padx=10).pack(side="left", padx=5)
            
            # List existing others
            others = [b for b in browsers if b['id'] not in ["gemlogin_default", "gpmlogin_default"]]
            for b in others:
                orow = tk.Frame(list_frame, pady=2)
                orow.pack(fill="x")
                tk.Label(orow, text=f"• {b['name']} ({b['type']})", width=25, anchor="w").pack(side="left")
                tk.Label(orow, text=b['api_url'], width=30, anchor="w").pack(side="left")
                tk.Button(orow, text="Xóa", command=lambda bid=b['id']: [self.db.remove_browser(bid), refresh_list()],
                          bg="#d32f2f", fg="white", relief="flat", padx=8).pack(side="left", padx=5)
                          
        refresh_list()
        
        def on_close():
            if hasattr(self, '_profile_cache'):
                self._profile_cache.clear() # Clear cache when settings change
            self.refresh_ui()
            win.destroy()
            
        tk.Button(main_frame, text="Đóng", command=on_close, bg="#888", fg="white", relief="flat", pady=5, width=10).pack(pady=10)
        win.protocol("WM_DELETE_WINDOW", on_close)

    def scheduling_settings_ui(self):
        config = self.db.get_scheduling_config()
        win = tk.Toplevel(self)
        win.title("Cài Đặt Lịch Chạy")
        win.geometry("450x400")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        
        pad = dict(padx=15, pady=5)
        tk.Label(win, text="Cấu Hình Lịch Chạy", font=("Arial", 13, "bold")).pack(**pad, anchor="w")
        ttk.Separator(win).pack(fill="x", padx=10)
        
        # Loop mode
        tk.Label(win, text="Chế Độ Lặp:", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        loop_mode_var = tk.StringVar(value=config['loop_mode'])
        for val, label in [("once", "Chạy 1 lần"), ("infinite", "Vòng lặp vô hạn")]:
            tk.Radiobutton(win, text=label, variable=loop_mode_var, value=val).pack(padx=25, anchor="w")
        
        count_row = tk.Frame(win)
        count_row.pack(fill="x", padx=25)
        tk.Radiobutton(count_row, text="Chạy N lần:", variable=loop_mode_var, value="count").pack(side="left")
        count_entry = tk.Entry(count_row, width=8, bd=1, relief="solid")
        count_entry.insert(0, str(config['loop_count']))
        count_entry.pack(side="left", padx=8)

        ttk.Separator(win).pack(fill="x", padx=10, pady=8)

        # Rest interval
        tk.Label(win, text="Nghỉ Giữa Các Lần (phút):", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        rest_row = tk.Frame(win)
        rest_row.pack(fill="x", padx=25)
        tk.Label(rest_row, text="Min:").pack(side="left")
        rest_min = tk.Entry(rest_row, width=8, bd=1, relief="solid")
        rest_min.insert(0, str(config['rest_min']))
        rest_min.pack(side="left", padx=8)
        tk.Label(rest_row, text="Max:").pack(side="left")
        rest_max = tk.Entry(rest_row, width=8, bd=1, relief="solid")
        rest_max.insert(0, str(config['rest_max']))
        rest_max.pack(side="left", padx=8)

        ttk.Separator(win).pack(fill="x", padx=10, pady=8)

        # Time window
        tk.Label(win, text="Khung Giờ Hoạt Động (HH:MM):", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        time_row = tk.Frame(win)
        time_row.pack(fill="x", padx=25)
        tk.Label(time_row, text="Từ:").pack(side="left")
        time_start = tk.Entry(time_row, width=8, bd=1, relief="solid")
        time_start.insert(0, config['time_start'])
        time_start.pack(side="left", padx=8)
        tk.Label(time_row, text="Đến:").pack(side="left")
        time_end = tk.Entry(time_row, width=8, bd=1, relief="solid")
        time_end.insert(0, config['time_end'])
        time_end.pack(side="left", padx=8)

        ttk.Separator(win).pack(fill="x", padx=10, pady=8)
        
        # Parallel Workers
        tk.Label(win, text="Số Luồng Chạy Song Song:", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        p_row = tk.Frame(win)
        p_row.pack(fill="x", padx=25)
        tk.Label(p_row, text="Max threads:").pack(side="left")
        p_count_entry = tk.Entry(p_row, width=8, bd=1, relief="solid")
        p_count_entry.insert(0, str(self.db.get_max_parallel_workers()))
        p_count_entry.pack(side="left", padx=8)

        # Buttons
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=15)
        
        def save_settings():
            try:
                self.db.set_scheduling_config(
                    loop_mode_var.get(),
                    int(count_entry.get()),
                    int(rest_min.get()),
                    int(rest_max.get()),
                    time_start.get(),
                    time_end.get()
                )
                self.db.set_max_parallel_workers(int(p_count_entry.get()))
                messagebox.showinfo("Thành công", "Đã lưu cài đặt lịch chạy.")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Dữ liệu không hợp lệ: {e}")
                
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=15, pady=5, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Lưu Cài Đặt", relief="flat", bg="#3a9a5c", fg="white",
                  padx=15, pady=5, command=save_settings).pack(side="right", padx=5)

    def browse_folders(self, page_index):
        win = tk.Toplevel(self)
        win.title("Chọn Thư Mục")
        win.geometry("550x380")
        win.attributes("-topmost", True)
        
        tk.Label(win, text="Thư Mục Đã Chọn", font=("Arial", 12, "bold")).pack(padx=15, pady=(15, 5), anchor="w")
        
        list_frame = tk.Frame(win, relief="sunken", bd=1)
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        txt = scrolledtext.ScrolledText(list_frame, font=("Arial", 10), state="disabled", height=12)
        txt.pack(fill="both", expand=True)
        
        self.temp_folders = []
        
        def refresh():
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            if not self.temp_folders:
                txt.insert("1.0", "(Chưa chọn thư mục nào)")
            else:
                for p in self.temp_folders:
                    txt.insert("end", f"📁  {p}\n")
            txt.configure(state="disabled")
            
        def add_folder():
            folder = filedialog.askdirectory(parent=win)
            if folder and folder not in self.temp_folders:
                self.temp_folders.append(folder)
                refresh()
                
        def remove_last():
            if self.temp_folders:
                self.temp_folders.pop()
                refresh()
                
        def save_all():
            for folder in self.temp_folders:
                self.db.add_folder(page_index, folder)
            self.refresh_ui()
            win.destroy()
            
        refresh()
        
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Button(btn_frame, text="+ Thêm Thư Mục", relief="flat", bg="#4a90d9", fg="white",
                  padx=10, pady=5, command=add_folder).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Xóa Cuối", relief="flat", bg="#c0392b", fg="white",
                  padx=10, pady=5, command=remove_last).pack(side="left", padx=2)
                  
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=10, pady=5, command=win.destroy).pack(side="right", padx=2)
        tk.Button(btn_frame, text="Lưu Tất Cả", relief="flat", bg="#3a9a5c", fg="white",
                  padx=10, pady=5, command=save_all).pack(side="right", padx=2)

    def add_folder_manual(self, page_index):
        win = tk.Toplevel(self)
        win.title("Nhập Đường Dẫn")
        win.geometry("500x150")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        
        tk.Label(win, text="Nhập đường dẫn thư mục:", font=("Arial", 11, "bold")).pack(padx=15, pady=(15, 5), anchor="w")
        path_entry = tk.Entry(win, font=("Arial", 10), bd=1, relief="solid")
        path_entry.pack(fill="x", padx=15, pady=5)
        path_entry.focus()
        
        def save_path():
            path = path_entry.get().strip()
            if path:
                self.db.add_folder(page_index, path)
                self.refresh_ui()
                win.destroy()
        
        path_entry.bind("<Return>", lambda e: save_path())
        
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=12, pady=4, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Thêm", relief="flat", bg="#3a9a5c", fg="white",
                  padx=12, pady=4, command=save_path).pack(side="right", padx=5)

    def group_management_ui(self):
        win = tk.Toplevel(self)
        win.title("Quản Lý Nhóm")
        win.geometry("600x400")
        win.attributes("-topmost", True)
        
        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)
        
        tk.Label(main_frame, text="Danh Sách Nhóm", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))
        
        # Use a canvas with scrollbar for the group list
        list_container = tk.Frame(main_frame, relief="sunken", bd=1)
        list_container.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(list_container)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        list_frame = tk.Frame(canvas)
        
        list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def refresh_list():
            for widget in list_frame.winfo_children():
                widget.destroy()
                
            groups = self.db.get_groups()
            if not groups:
                tk.Label(list_frame, text="Chưa có nhóm nào. Hãy thêm nhóm mới ở dưới.", pady=20).pack()
            
            for g in groups:
                row = tk.Frame(list_frame, pady=5, bd=1, relief="solid")
                row.pack(fill="x", pady=2, padx=5)
                
                tk.Label(row, text=f"Nhóm: {g['name']}", font=("Arial", 10, "bold"), width=20, anchor="w").pack(side="left", padx=5)
                
                profile_str = f"Profile: {g.get('profile_name', 'Chưa gán')}" if g.get('profile_name') else "Profile: Chưa gán"
                tk.Label(row, text=profile_str, font=("Arial", 9), width=25, anchor="w").pack(side="left", padx=5)
                
                tk.Button(row, text="Xóa", command=lambda gid=g['id']: delete_group(gid),
                          bg="#c0392b", fg="white", relief="flat", padx=8).pack(side="right", padx=5)
                          
        def delete_group(gid):
            if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa nhóm này? Các Nick trong nhóm sẽ bị gỡ khỏi nhóm."):
                self.db.remove_group(gid)
                refresh_list()
                self.refresh_ui()
                
        refresh_list()
        
        ttk.Separator(main_frame).pack(fill="x", pady=15)
        
        tk.Label(main_frame, text="Thêm Nhóm Mới", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        add_frame = tk.Frame(main_frame)
        add_frame.pack(fill="x")
        
        tk.Label(add_frame, text="Tên nhóm:").pack(side="left")
        name_entry = tk.Entry(add_frame, width=20)
        name_entry.pack(side="left", padx=5)
        
        def add_group():
            name = name_entry.get().strip()
            if name:
                self.db.add_group(name)
                name_entry.delete(0, 'end')
                refresh_list()
                self.refresh_ui()
                
        tk.Button(add_frame, text="+ Thêm Nhóm", command=add_group, bg="#4a90d9", fg="white", relief="flat", padx=10).pack(side="left", padx=5)
        name_entry.bind("<Return>", lambda e: add_group())
        
        tk.Button(main_frame, text="Đóng", command=win.destroy, bg="#888", fg="white", relief="flat", pady=5, width=10).pack(pady=10)

    def _refresh_global_folders_ui(self):
        for widget in self.global_list_frame.winfo_children():
            widget.destroy()
            
        folders = self.db.get_global_folders()
        if not folders:
            tk.Label(self.global_list_frame, text="Chưa có thư mục chung.", font=("Arial", 9, "italic"), bg="#ffffff", fg="#888").pack(anchor="w")
            return
            
        for i, f in enumerate(folders):
            row = tk.Frame(self.global_list_frame, bg="#ffffff")
            row.pack(fill="x", pady=2)
            
            v_count = self.db.get_video_count(f)
            count_color = "#3a9a5c" if v_count > 0 else "#c0392b"
            count_text = f"({v_count} videos)" if v_count > 0 else "(0 videos - EMPTY)"
            
            tk.Label(row, text=f"📁 {f}", font=("Arial", 9), bg="#ffffff").pack(side="left")
            tk.Label(row, text=count_text, fg=count_color, font=("Arial", 8, "bold"), bg="#ffffff").pack(side="left", padx=5)
            
            tk.Button(row, text="x", fg="gray", bg="#ffffff", relief="flat", cursor="hand2",
                      command=lambda idx=i: self.remove_global_folder(idx)).pack(side="right")
                      
    def add_global_folder_ui(self):
        folder = filedialog.askdirectory(title="Chọn Thư Mục Video Chung")
        if folder:
            self.db.add_global_folder(folder)
            self._refresh_global_folders_ui()

    def remove_global_folder(self, index):
        self.db.remove_global_folder(index)
        self._refresh_global_folders_ui()

    def add_nick_ui(self):
        win = tk.Toplevel(self)
        win.title("Thêm Nick Cá Nhân")
        win.geometry("350x130")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        
        tk.Label(win, text="Số lượng Nick Cá Nhân muốn thêm:", font=("Arial", 11)).pack(padx=15, pady=(15, 5), anchor="w")
        entry = tk.Entry(win, bd=1, relief="solid", width=10)
        entry.insert(0, "1")
        entry.pack(padx=15, pady=5, anchor="w")
        entry.focus()
        
        def do_add():
            try:
                count = int(entry.get())
                if count > 0:
                    for _ in range(count):
                        self.db.add_nick("https://facebook.com/...")
                    self.refresh_ui()
                    win.destroy()
            except ValueError:
                pass
        
        entry.bind("<Return>", lambda e: do_add())
        
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=8)
        
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=12, pady=4, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Thêm", relief="flat", bg="#4a90d9", fg="white",
                  padx=12, pady=4, command=do_add).pack(side="right", padx=5)

    def remove_page(self, index):
        if messagebox.askyesno("Xác Nhận", "Xóa Nick Cá Nhân này?"):
            self.db.remove_nick(index)
            self.refresh_ui()

    def clear_all_ui(self):
        if messagebox.askyesno("Xác Nhận", "Bạn có chắc muốn xóa TẤT CẢ nicks?"):
            self.db.clear_all()
            self.refresh_ui()

    def remove_folder(self, page_index, folder_index):
        self.db.remove_folder(page_index, folder_index)
        self.refresh_ui()

    def toggle_auto_delete(self):
        val = self.auto_delete_var.get()
        self.db.set_auto_delete_videos(val)
        self.log(f"Tự xóa video: {'Bật' if val else 'Tắt'}")

    def show_video_log_ui(self, filter_name=None):
        log_file = "thongke_ngay.txt"
        win = tk.Toplevel(self)
        title = f"Log Ngày: {filter_name}" if filter_name else "Thống Kê Log Hệ Thống"
        win.title(title)
        win.geometry("900x600")
        win.attributes("-topmost", True)
        
        tk.Label(win, text=title, font=("Arial", 13, "bold")).pack(padx=15, pady=(10, 5), anchor="w")
        
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10), wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=5)
        
        def populate():
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            if not os.path.exists(log_file):
                txt.insert("1.0", "Chưa có dữ liệu log.")
                txt.configure(state="disabled")
                return
            
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                filtered = []
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    if filter_name and f"Page: {filter_name}" not in line:
                        continue
                    filtered.append(line)
                
                txt.insert("1.0", "\n".join(filtered))
            except Exception as e:
                txt.insert("1.0", f"Lỗi đọc log: {e}")
            txt.configure(state="disabled")
            
        populate()
        
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=8)
        
        def clear_logs():
            if messagebox.askyesno("Xác nhận", "Xóa toàn bộ log hôm nay?", parent=win):
                if os.path.exists(log_file):
                    os.remove(log_file)
                populate()
                
        tk.Button(btn_frame, text="Xoá Log", relief="flat", bg="#c0392b", fg="white",
                  padx=12, pady=4, command=clear_logs).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Làm Mới", relief="flat", bg="#4a90d9", fg="white",
                  padx=12, pady=4, command=populate).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Đóng", relief="flat", bg="#888", fg="white",
                  padx=12, pady=4, command=win.destroy).pack(side="right", padx=5)

    def set_all_enabled(self, status):
        nicks = self.db.get_nicks()
        for i in range(len(nicks)):
            self.db.update_page_enabled(i, status)
        self.refresh_ui()

    def bulk_assign_ui(self):
        # Find which nicks are selected
        nicks = self.db.get_nicks()
        selected_indices = [i for i, p in enumerate(nicks) if p.get('enabled', True)]
        
        if not selected_indices:
            messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất một Nick Cá Nhân để gán hàng loạt.")
            return
            
        win = tk.Toplevel(self)
        win.title(f"Gán Hàng Loạt (Đã chọn {len(selected_indices)} Page)")
        win.geometry("500x200")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        
        main_frame = tk.Frame(win, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)
        
        tk.Label(main_frame, text="Chọn profile (bao gồm trình duyệt) để gán cho các page đã chọn", font=("Arial", 10, "bold")).pack(pady=(0, 15))
        
        # Unified Profile Selection
        row = tk.Frame(main_frame)
        row.pack(fill="x", pady=5)
        tk.Label(row, text="Profile:", width=12, anchor="w").pack(side="left")
        p_var = tk.StringVar(value="Đang tải danh sách...")
        p_combo = ttk.Combobox(row, textvariable=p_var, state="readonly", width=45)
        p_combo.pack(side="left")
        
        bulk_unified_map = {}
        
        def update_bulk_profiles():
            nonlocal bulk_unified_map
            browsers = self.db.get_browsers()
            all_opts = []
            if not hasattr(self, '_profile_cache'): self._profile_cache = {}
            for b in browsers:
                b_id = b['id']
                b_name = b['name']
                # Use cache if available
                profiles = self._profile_cache.get(b_id)
                if profiles is None:
                    # If not in cache, try fetching once
                    try:
                        api = GemLoginAPI(b['api_url']) if b['type'] == 'gemlogin' else GPMLoginAPI(b['api_url'])
                        profiles = api.get_profiles() or []
                        self._profile_cache[b_id] = profiles
                    except:
                        self._profile_cache[b_id] = []
                        profiles = []
                
                for p in profiles:
                    p_name = p.get('name', p.get('title', p.get('profile_name', 'Unknown')))
                    p_id = p.get('id', p.get('profile_id'))
                    opt = f"[{b_name}] {p_name}"
                    all_opts.append(opt)
                    bulk_unified_map[opt] = (b_id, p_id, p_name)
            
            p_combo['values'] = all_opts
            if all_opts: p_var.set(all_opts[0])
            else: p_var.set("Không tìm thấy profile nào")
            
        update_bulk_profiles()
        
        def apply_bulk():
            opt = p_var.get()
            if opt in bulk_unified_map:
                b_id, p_id, p_name = bulk_unified_map[opt]
                for idx in selected_indices:
                    self.db.update_page_browser(idx, b_id)
                    self.db.update_page_profile(idx, p_id, p_name)
                self.log(f"Đã gán hàng loạt {opt} cho {len(selected_indices)} Nick.")
                self.refresh_ui()
                win.destroy()
            else:
                messagebox.showerror("Lỗi", "Vui lòng chọn một profile hợp lệ.")
                
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=20)
        tk.Button(btn_frame, text="Hủy", command=win.destroy, bg="#888", fg="white", width=10, relief="flat").pack(side="right", padx=5)
        tk.Button(btn_frame, text="Áp Dụng", command=apply_bulk, bg="#3a9a5c", fg="white", width=15, relief="flat", font=("Arial", 10, "bold")).pack(side="right", padx=5)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}\n"
        print(f"[{timestamp}] [LOG] {message}")
        if hasattr(self, 'log_text'):
            def _update():
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg)
                self.log_text.see("end")
                self.log_text.configure(state="disabled") # Should be disabled usually
            self.after(0, _update)

    def write_thongke(self, message):
        log_file = "thongke_ngay.txt"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def auto_map_folders_ui(self):
        # Ask for base directory
        base_dir = filedialog.askdirectory(title="Chọn thư mục chứa các folder video (vd: downloads)",
                                         initialdir=r"G:\Documentss\Antigravity_Gams_Youtubedownload\downloads")
        if not base_dir:
            return
        
        mapped_count, details = self.db.auto_map_folders(base_dir)
        if mapped_count > 0:
            msg = f"Đã tự động gán {mapped_count} folder mới cho các Nick.\n\nChi tiết:\n" + "\n".join(details[:10])
            if len(details) > 10:
                msg += f"\n... và {len(details)-10} page khác."
            messagebox.showinfo("Thành công", msg)
            self.refresh_ui()
        else:
            messagebox.showwarning("Thông báo", "Không tìm thấy folder nào khớp với tên Nick Cá Nhân (hoặc các page đã có folder).")

    def view_comment_history(self):
        win = tk.Toplevel(self)
        win.title("Lịch Sử Comment")
        win.geometry("700x500")
        win.lift()
        win.focus_force()
        
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        
        history = self.db.comment_history
        if not history:
            txt.insert("1.0", "Chưa có lịch sử comment nào.")
        else:
            text = ""
            for page, entries in history.items():
                text += f"=== Page: {page} ===\n"
                for entry in entries:
                    text += f"[{entry.get('timestamp')}] Video: {entry.get('video')} -> {entry.get('post_link')}\n"
                text += "\n"
            txt.insert("1.0", text)
        txt.configure(state="disabled")

    # ── Start / Stop ──────────────────────────────────────────
    def start_posting(self):
        self.stop_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        threading.Thread(target=self._start_posting_thread, daemon=True).start()

    def stop_posting(self):
        self.stop_flag = True
        self.log("Stop requested. Đang dừng sau video hiện tại...")
        self.btn_stop.configure(state="disabled")

    def _start_posting_thread(self):
        try:
            self.db.reload()
            run_number = 0
            config = self.db.get_scheduling_config()
            loop_mode = config['loop_mode']
            loop_count = config['loop_count']
            rest_min = config['rest_min']
            rest_max = config['rest_max']
            time_start = config['time_start']
            time_end = config['time_end']

            while True:
                if self.stop_flag:
                    self.log("Đã dừng theo yêu cầu.")
                    break
                
                from datetime import datetime
                current_time = datetime.now().strftime("%H:%M")
                if not (time_start <= current_time <= time_end):
                    self.log(f"Ngoài khung giờ hoạt động ({time_start}-{time_end}). Hiện tại: {current_time}")
                    self.log(f"Chờ đến {time_start}...")
                    while not self.stop_flag:
                        current_time = datetime.now().strftime("%H:%M")
                        if time_start <= current_time <= time_end:
                            break
                        time.sleep(60)
                    if self.stop_flag:
                        break
                    self.log("Đã vào khung giờ hoạt động. Bắt đầu chạy...")

                run_number += 1
                if loop_mode == 'once':
                    self.log("Bắt đầu chạy 1 lần...")
                elif loop_mode == 'count':
                    self.log(f"Lần chạy {run_number}/{loop_count}...")
                else:
                    self.log(f"Vòng lặp #{run_number} (vô hạn)...")

                nicks = self.db.get_nicks()
                run_mode = self.db.get_run_mode()
                skip_commented = self.skip_commented_var.get()
                auto_delete = self.auto_delete_var.get()
                
                enabled_pages = [p for p in nicks if p.get('enabled', True)]
                if not enabled_pages:
                    self.log("Không có Nick nào được chọn để chạy.")
                else:
                    total_en = len(enabled_pages)
                    self.log(f"Quét công việc của {total_en} Nick...")
                    
                    global_folders = self.db.get_global_folders()
                    profile_groups = {}  # key=(b_id, p_id), value=list of page work dicts
                    
                    for idx, page in enumerate(enabled_pages, 1):
                        if self.stop_flag: break
                        page_name = page.get('name', '?')
                        stt = f"[{idx}/{total_en}]"
                        
                        page_folders = page.get('folders', [])
                        folders = list(set(page_folders + global_folders))
                        
                        if not folders:
                            self.log(f"{stt} [{page_name}] Bỏ qua (Chưa cấu hình thư mục video)")
                            continue
                            
                        unposted_files = []
                        to_comment_historic = []
                        
                        if run_mode != 'comment_only':
                            existing_logs = self.db.get_logs(page['link'])
                            posted_set = {log.get('video') for log in (existing_logs or [])
                                          if log.get('status', '') in ('Success', 'Uploaded', 'Uploaded (No Comment)')}
                            for folder in folders:
                                if os.path.exists(folder):
                                    try:
                                        v_files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))]
                                        for vf in v_files:
                                            if vf not in posted_set:
                                                unposted_files.append([folder, vf])
                                    except: pass
                        
                        if run_mode == 'comment_only':
                            logs = self.db.get_logs(page['link'])
                            for log_entry in (logs or []):
                                v_name = log_entry.get('video', '')
                                if skip_commented and self.db.has_commented(page['link'], v_name):
                                    continue
                                to_comment_historic.append(v_name)
                                
                        has_work = bool(unposted_files) if run_mode != 'comment_only' else bool(to_comment_historic)
                        if not has_work:
                            self.log(f"{stt} [{page_name}] Bỏ qua (Không có bài mới cần đăng)")
                            continue

                        # Resolve browser/profile key
                        p_idx = -1
                        for k, p_raw in enumerate(nicks):
                            if p_raw['link'] == page['link']:
                                p_idx = k
                                break
                        b_id = self.db.resolve_page_browser_id(p_idx) if p_idx != -1 else page.get('browser_id', 'gemlogin_default')
                        p_id = page.get('profile_id', '')
                        key = (b_id, p_id)
                        
                        if key not in profile_groups:
                            profile_groups[key] = []
                        profile_groups[key].append({
                            'name': page.get('name'),
                            'link': page.get('link'),
                            'folders': folders,
                            'unposted_files': unposted_files,
                            'to_comment_historic': to_comment_historic,
                        })

                    if not profile_groups:
                        self.log("Không có Nick nào có việc cần làm trong vòng này.")
                    else:
                        # ─── PHASE 2: SPAWN 1 CMD / PROFILE ────────────────────────────
                        import json, subprocess, tempfile
                        self.active_procs = []
                        self.active_workers = []
                        max_workers = self.db.get_max_parallel_workers()
                        
                        group_items = list(profile_groups.items())
                        for i, ((b_id, p_id), pages_for_profile) in enumerate(group_items):
                            if self.stop_flag: break
                            
                            # Kiểm tra số lượng luồng đang chạy
                            while not self.stop_flag:
                                running_procs = [p for p in self.active_procs if p.poll() is None]
                                if len(running_procs) < max_workers:
                                    break
                                time.sleep(2)
                            
                            if self.stop_flag: break
                            
                            b_config = self.db.get_browser_by_id(b_id)
                            if not b_config: continue

                            # 1. PRE-STOP
                            try:
                                api_cls = GemLoginAPI if b_config['type'] == 'gemlogin' else GPMLoginAPI
                                api_inst = api_cls(b_config['api_url'])
                                self.log(f"[Pre-check] Đảm bảo profile {p_id} tắt trước khi mở...")
                                api_inst.stop_profile(str(p_id))
                                time.sleep(1)
                            except: pass

                            job = {
                                'run_mode': run_mode,
                                'skip_commented': skip_commented,
                                'auto_delete': auto_delete,
                                'browser_config': b_config,
                                'profile_id': str(p_id),
                                'profile_label': str(p_id),
                                'pages': pages_for_profile,
                            }
                            
                            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8', dir=_BASE_DIR, prefix=f'job_{p_id}_')
                            json.dump(job, tmp, ensure_ascii=False)
                            tmp.close()
                            
                            env = os.environ.copy()
                            env["PYTHONUTF8"] = "1"
                            env["PYTHONIOENCODING"] = "utf-8:replace"
                            
                            # Sử dụng đường dẫn tuyệt đối của Python hiện tại để tránh lỗi "python" không tìm thấy
                            python_exe = sys.executable
                            if python_exe.lower().endswith("pythonw.exe"):
                                python_exe = python_exe[:-9] + "python.exe"
                            
                            job_basename = os.path.basename(tmp.name)
                            parent_pid = str(os.getpid())
                            
                            # Tạo file .bat tạm thời cho worker này
                            # Cách đáng tin cậy nhất để tránh lỗi quoting/encoding của Windows CMD
                            bat_name = job_basename.replace('.json', '.bat')
                            bat_path = os.path.join(_BASE_DIR, bat_name)
                            bat_content = (
                                "@echo off\r\n"
                                "chcp 65001 > nul\r\n"
                                f'"{python_exe}" page_worker.py {job_basename} {parent_pid}\r\n'
                                f'del /f /q "%~f0"\r\n'  # Tự xóa file bat sau khi xong
                            )
                            with open(bat_path, 'w', encoding='ascii') as bf:
                                bf.write(bat_content)
                            
                            args = ["cmd", "/c", bat_path]
                            
                            proc = subprocess.Popen(args, env=env, cwd=_BASE_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
                            self.active_procs.append(proc)
                            self.active_workers.append({
                                'proc': proc,
                                'b_id': b_id,
                                'p_id': p_id,
                                'job_path': tmp.name
                            })
                            self.log(f"[{i+1}/{len(group_items)}] Đã mở CMD Worker cho Profile {p_id} ({len(pages_for_profile)} Nick)")

                        # 2. WAIT
                        self.log("Đang chờ tất cả CMD Worker hoàn tất...")
                        while not self.stop_flag:
                            running_procs = [p for p in self.active_procs if p.poll() is None]
                            if not running_procs: break
                            time.sleep(3)

                        # 3. POST-STOP: Tắt trình duyệt sau khi làm xong
                        if not self.stop_flag:
                            for (b_id, p_id), _ in profile_groups.items():
                                try:
                                    b_config = self.db.get_browser_by_id(b_id)
                                    api_cls = GemLoginAPI if b_config['type'] == 'gemlogin' else GPMLoginAPI
                                    api_cls(b_config['api_url']).stop_profile(str(p_id))
                                    self.log(f"[Post-stop] Đã đóng profile {p_id}.")
                                except: pass

                        if self.stop_flag:
                            self.terminate_all_workers()
                                
                    self.log(f"===== Đã xử lý xong bộ {total_en} Nick =====")

                if self.stop_flag:
                    break
                if loop_mode == 'once':
                    break
                elif loop_mode == 'count' and run_number >= loop_count:
                    break
                
                import random
                rest_seconds = random.randint(rest_min * 60, rest_max * 60)
                self.log(f"Nghỉ {rest_seconds // 60} phút trước lần chạy tiếp theo...")
                elapsed = 0
                while elapsed < rest_seconds and not self.stop_flag:
                    time.sleep(10)
                    elapsed += 10
                    
        except Exception as global_e:
            self.log(f"!!! CRITICAL ERROR IN WORKER THREAD: {global_e}")
            import traceback
            print(traceback.format_exc())
            self.stop_flag = True
        finally:
            self.log("Hoàn tất.")
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")

    def terminate_all_workers(self):
        if not hasattr(self, 'active_workers') or not self.active_workers:
            return
        
        self.log("Đang tắt tất cả các luồng worker và đóng trình duyệt...")
        
        # 1. Đóng toàn bộ trình duyệt profile qua API trước
        for worker in self.active_workers:
            b_id = worker.get('b_id')
            p_id = worker.get('p_id')
            if b_id and p_id:
                try:
                    b_config = self.db.get_browser_by_id(b_id)
                    if b_config:
                        api_cls = GemLoginAPI if b_config['type'] == 'gemlogin' else GPMLoginAPI
                        self.log(f"Đóng trình duyệt profile {p_id}...")
                        api_cls(b_config['api_url']).stop_profile(str(p_id))
                except Exception as e:
                    self.log(f"Lỗi khi đóng profile {p_id}: {e}")

        # 2. Sử dụng taskkill /F /T để tắt triệt để cây tiến trình (cmd + python)
        import subprocess
        for worker in self.active_workers:
            proc = worker.get('proc')
            if proc and proc.poll() is None:
                try:
                    self.log(f"Đang dừng tiến trình PID {proc.pid}...")
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True, creationflags=0x08000000)
                except Exception as e:
                    self.log(f"Lỗi taskkill PID {proc.pid}: {e}")
                    try:
                        proc.terminate()
                    except:
                        pass
        
        # 3. Dọn dẹp các file JSON công việc tạm thời
        for worker in self.active_workers:
            job_path = worker.get('job_path')
            if job_path and os.path.exists(job_path):
                try:
                    os.remove(job_path)
                except Exception as e:
                    self.log(f"Lỗi khi xóa file tạm {job_path}: {e}")

        self.active_workers.clear()
        self.active_procs.clear()

    def on_app_exit(self):
        """ Kill all child processes before exiting """
        self.stop_flag = True
        self.terminate_all_workers()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = App()
    app.mainloop()
