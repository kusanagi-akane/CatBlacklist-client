"""
貓貓黑名單客戶端 世界上最可愛的貓貓做的黑名單管理工具
可以輕鬆調用API
Made by kusanagi_akane(!草薙明音) 2026 all rights reserved.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import threading
import sys
import os

from client import BlacklistClient, AuthError, APIError


def _resource_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# 好看哒粉粉配色


THEME = {
    "bg":           "#faf0f4",   # 主背景（淡粉白）
    "bg_card":      "#ffffff",   # 卡片背景（純白）
    "bg_input":     "#f5e6ee",   # 輸入框背景（淡粉）
    "bg_output":    "#fdf6f9",   # 輸出區背景
    "accent":       "#e8729a",   # 主色（玫瑰粉）
    "accent_hover": "#f48db5",   # 主色懸停
    "danger":       "#e5566e",   # 紅
    "danger_hover": "#f07088",
    "success":      "#5db87e",   # 成功綠
    "success_hover":"#74d498",
    "warning":      "#e8a944",   # 警告黃
    "fg":           "#3d2b35",   # 主文字（紫）
    "fg_dim":       "#9a8490",   # 次要文字
    "fg_placeholder":"#c7b0bc",  # 佔位文字
    "border":       "#f0d4e0",   # 邊框（淡粉邊線）
    "scrollbar":    "#e8c4d4",
}


# 元件


class PlaceholderEntry(tk.Entry):
    """帶佔位文字的輸入框"""

    def __init__(self, master, placeholder="", show_char=None, **kw):
        super().__init__(master, **kw)
        self.placeholder = placeholder
        self.show_char = show_char
        self._has_real_text = False

        self.bind("<FocusIn>",  self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._show_placeholder()

    def _show_placeholder(self):
        self.configure(show="")
        self.delete(0, tk.END)
        self.insert(0, self.placeholder)
        self.configure(fg=THEME["fg_placeholder"])
        self._has_real_text = False

    def _on_focus_in(self, _event=None):
        if not self._has_real_text:
            self.delete(0, tk.END)
            self.configure(fg=THEME["fg"])
            if self.show_char:
                self.configure(show=self.show_char)
            self._has_real_text = True

    def _on_focus_out(self, _event=None):
        if not self.get():
            self._show_placeholder()

    def get_value(self) -> str:
        """取得實際輸入值"""
        return self.get() if self._has_real_text else ""

    def clear(self):
        self.delete(0, tk.END)
        self._show_placeholder()


class HoverButton(tk.Canvas):
    """圓角漸層按鈕"""

    def __init__(self, master, text="", command=None, width=140, height=36,
                 bg_color=None, hover_color=None, fg_color="#ffffff",
                 radius=8, font=None, **kw):
        super().__init__(master, width=width, height=height,
                         highlightthickness=0,
                         bg=master["bg"] if isinstance(master, tk.Frame) else THEME["bg_card"],
                         **kw)
        self._text = text
        self._command = command
        self._width = width
        self._height = height
        self._bg = bg_color or THEME["accent"]
        self._hover = hover_color or THEME["accent_hover"]
        self._fg = fg_color
        self._radius = radius
        self._font = font or ("Microsoft JhengHei UI", 10, "bold")
        self._enabled = True

        self._draw(self._bg)
        self.bind("<Enter>", lambda e: self._on_hover(True))
        self.bind("<Leave>", lambda e: self._on_hover(False))
        self.bind("<Button-1>", self._on_click)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        points = [
            x1+r, y1, x2-r, y1,
            x2, y1, x2, y1+r,
            x2, y2-r, x2, y2,
            x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r,
            x1, y1+r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kw)

    def _draw(self, color):
        self.delete("all")
        self._round_rect(1, 1, self._width-1, self._height-1, self._radius, fill=color, outline="")
        self.create_text(self._width//2, self._height//2, text=self._text,
                         fill=self._fg, font=self._font)

    def _on_hover(self, entering):
        if self._enabled:
            self._draw(self._hover if entering else self._bg)

    def _on_click(self, _event=None):
        if self._enabled and self._command:
            self._command()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self._draw(self._bg if enabled else THEME["border"])

    def configure_bg(self, bg):
        """更新畫布背景以融入父容器"""
        self.configure(bg=bg)



# 主應用程式


class BlacklistApp(tk.Tk):

    APP_TITLE  = "貓貓黑名單客戶端"
    APP_SIZE   = "880x800"
    MIN_WIDTH  = 760
    MIN_HEIGHT = 600

    def __init__(self):
        super().__init__()
        self.title(self.APP_TITLE)
        self.geometry(self.APP_SIZE)
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.configure(bg=THEME["bg"])
        self.resizable(True, True)
        icon_path = _resource_path(os.path.join("data", "icon.png"))
        if os.path.exists(icon_path):
            try:
                icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, icon)
                self._icon_ref = icon
            except Exception:
                pass
        try:
            self.client = BlacklistClient()
        except Exception as e:
            messagebox.showerror("啟動錯誤", f"無法初始化：\n{e}")
            sys.exit(1)

        self._show_token = False
        self._build_ui()
        self._update_auth_status()

    # ── UI ───────────────────────────────────────────

    def _build_ui(self):
        # ── 頂部標題列 ──
        header = tk.Frame(self, bg=THEME["bg_card"], height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # 標題列圖示
        header_icon_path = _resource_path(os.path.join("data", "icon.png"))
        raw_icon = tk.PhotoImage(file=header_icon_path)
        w, h = raw_icon.width(), raw_icon.height()
        factor = max(1, max(w, h) // 32)
        self._header_icon = raw_icon.subsample(factor, factor)
        tk.Label(header, image=self._header_icon,
                 bg=THEME["bg_card"]).pack(side=tk.LEFT, padx=(16, 6))

        tk.Label(header, text=self.APP_TITLE,
                 font=("Microsoft JhengHei UI", 14, "bold"),
                 bg=THEME["bg_card"], fg=THEME["fg"]).pack(side=tk.LEFT)

        self.status_dot = tk.Label(header, text="●", font=("Segoe UI", 11),
                                   bg=THEME["bg_card"], fg=THEME["fg_dim"])
        self.status_dot.pack(side=tk.RIGHT, padx=(0, 8))
        self.status_label = tk.Label(header, text="未連線",
                                     font=("Microsoft JhengHei UI", 9),
                                     bg=THEME["bg_card"], fg=THEME["fg_dim"])
        self.status_label.pack(side=tk.RIGHT)

        # ── 分隔線 ──
        tk.Frame(self, bg=THEME["border"], height=1).pack(fill=tk.X)

        # ── 主要內容──
        main = tk.Frame(self, bg=THEME["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        left = tk.Frame(main, bg=THEME["bg"], width=340)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        left.pack_propagate(False)

        right = tk.Frame(main, bg=THEME["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        self._build_auth_panel(left)
        self._build_query_panel(left)
        self._build_manage_panel(left)
        self._build_output_panel(right)

        # ── 底部狀態列 ──
        self._build_statusbar()

    # ── 認證面板 ──────────────────────────────────────────

    def _build_auth_panel(self, parent):
        card = self._make_card(parent, "🔑 認證")

        row = tk.Frame(card, bg=THEME["bg_card"])
        row.pack(fill=tk.X, pady=(0, 6))

        self.token_entry = PlaceholderEntry(
            row, placeholder="輸入 API Token ...", show_char="●",
            font=("Consolas", 10), bg=THEME["bg_input"], fg=THEME["fg"],
            insertbackground=THEME["fg"], relief=tk.FLAT, bd=0
        )
        self.token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))

        self.toggle_eye_btn = tk.Label(
            row, text="👁", font=("Segoe UI Emoji", 12), cursor="hand2",
            bg=THEME["bg_card"], fg=THEME["fg_dim"]
        )
        self.toggle_eye_btn.pack(side=tk.RIGHT)
        self.toggle_eye_btn.bind("<Button-1>", self._toggle_token_visibility)

        btn_row = tk.Frame(card, bg=THEME["bg_card"])
        btn_row.pack(fill=tk.X)

        HoverButton(btn_row, text="登入", width=100, height=32,
                    command=self._do_login,
                    bg_color=THEME["success"], hover_color=THEME["success_hover"]
                    ).pack(side=tk.LEFT, padx=(0, 6))
        HoverButton(btn_row, text="登出", width=100, height=32,
                    command=self._do_logout,
                    bg_color=THEME["danger"], hover_color=THEME["danger_hover"]
                    ).pack(side=tk.LEFT, padx=(0, 6))
        HoverButton(btn_row, text="測試連線", width=110, height=32,
                    command=self._do_test_connection
                    ).pack(side=tk.LEFT)

    # ── 查詢面板 ─────────────────────────────────────────

    def _build_query_panel(self, parent):
        card = self._make_card(parent, "🔍 查詢")

        HoverButton(card, text="📋 查詢全部黑名單", width=300, height=34,
                    command=self._do_get_all).pack(fill=tk.X, pady=(0, 8))

        tk.Label(card, text="查詢單一使用者", font=("Microsoft JhengHei UI", 9),
                 bg=THEME["bg_card"], fg=THEME["fg_dim"], anchor="w").pack(fill=tk.X)

        row = tk.Frame(card, bg=THEME["bg_card"])
        row.pack(fill=tk.X, pady=(2, 0))

        self.query_id_entry = PlaceholderEntry(
            row, placeholder="Discord 使用者 ID",
            font=("Consolas", 10), bg=THEME["bg_input"], fg=THEME["fg"],
            insertbackground=THEME["fg"], relief=tk.FLAT, bd=0
        )
        self.query_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 6))

        HoverButton(row, text="查詢", width=80, height=32,
                    command=self._do_get_user).pack(side=tk.RIGHT)

    # ── 管理面板 ─────────────────────────────────────────

    def _build_manage_panel(self, parent):
        card = self._make_card(parent, "⚙️ 管理")

        # — 新增使用者 —
        tk.Label(card, text="新增至黑名單", font=("Microsoft JhengHei UI", 9, "bold"),
                 bg=THEME["bg_card"], fg=THEME["fg"], anchor="w").pack(fill=tk.X, pady=(0, 4))

        fields = [
            ("使用者 ID", "add_id"),
            ("操作者",     "add_by"),
            ("原因",       "add_reason"),
        ]
        for label_text, attr_name in fields:
            row = tk.Frame(card, bg=THEME["bg_card"])
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=label_text, width=8, anchor="e",
                     font=("Microsoft JhengHei UI", 9), bg=THEME["bg_card"],
                     fg=THEME["fg_dim"]).pack(side=tk.LEFT)
            entry = PlaceholderEntry(
                row, placeholder=f"輸入{label_text}",
                font=("Consolas", 10), bg=THEME["bg_input"], fg=THEME["fg"],
                insertbackground=THEME["fg"], relief=tk.FLAT, bd=0
            )
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(4, 0))
            setattr(self, f"{attr_name}_entry", entry)

        # 模式選擇
        mode_row = tk.Frame(card, bg=THEME["bg_card"])
        mode_row.pack(fill=tk.X, pady=(2, 6))
        tk.Label(mode_row, text="模式", width=8, anchor="e",
                 font=("Microsoft JhengHei UI", 9), bg=THEME["bg_card"],
                 fg=THEME["fg_dim"]).pack(side=tk.LEFT)

        self.mode_var = tk.StringVar(value="block")
        for val, label, color in [("block",      "🚫 封鎖", THEME["danger"]),
                                   ("global_ban", "🌐 全域封禁", THEME["warning"])]:
            rb = tk.Radiobutton(mode_row, text=label, variable=self.mode_var, value=val,
                                font=("Microsoft JhengHei UI", 9), bg=THEME["bg_card"],
                                fg=color, selectcolor=THEME["bg_input"],
                                activebackground=THEME["bg_card"], activeforeground=color,
                                indicatoron=True)
            rb.pack(side=tk.LEFT, padx=(6, 2))

        HoverButton(card, text="➕ 新增", width=300, height=32,
                    command=self._do_add_user,
                    bg_color=THEME["success"], hover_color=THEME["success_hover"]
                    ).pack(fill=tk.X, pady=(0, 10))

        # — 分隔線 —
        tk.Frame(card, bg=THEME["border"], height=1).pack(fill=tk.X, pady=4)

        # — 移除使用者 —
        tk.Label(card, text="移除黑名單", font=("Microsoft JhengHei UI", 9, "bold"),
                 bg=THEME["bg_card"], fg=THEME["fg"], anchor="w").pack(fill=tk.X, pady=(4, 4))

        rm_row = tk.Frame(card, bg=THEME["bg_card"])
        rm_row.pack(fill=tk.X, pady=(0, 6))

        self.remove_id_entry = PlaceholderEntry(
            rm_row, placeholder="使用者 ID",
            font=("Consolas", 10), bg=THEME["bg_input"], fg=THEME["fg"],
            insertbackground=THEME["fg"], relief=tk.FLAT, bd=0
        )
        self.remove_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 6))

        HoverButton(rm_row, text="移除", width=80, height=32,
                    command=self._do_remove_user,
                    bg_color=THEME["danger"], hover_color=THEME["danger_hover"]
                    ).pack(side=tk.RIGHT)

        # — 分隔線 —
        tk.Frame(card, bg=THEME["border"], height=1).pack(fill=tk.X, pady=4)

        # — 匯入 / 匯出 —
        io_row = tk.Frame(card, bg=THEME["bg_card"])
        io_row.pack(fill=tk.X, pady=(4, 0))

        HoverButton(io_row, text="📤 匯入覆蓋", width=145, height=32,
                    command=self._do_override,
                    bg_color=THEME["warning"], hover_color="#f0c060", fg_color="#ffffff"
                    ).pack(side=tk.LEFT, padx=(0, 6))

        HoverButton(io_row, text="📥 匯出全部", width=145, height=32,
                    command=self._do_save_all
                    ).pack(side=tk.LEFT)

    # ── 輸出面板 ─────────────────────────────────────────

    def _build_output_panel(self, parent):
        card = tk.Frame(parent, bg=THEME["bg_card"])
        card.pack(fill=tk.BOTH, expand=True)
        title_row = tk.Frame(card, bg=THEME["bg_card"])
        title_row.pack(fill=tk.X, padx=12, pady=(10, 4))

        tk.Label(title_row, text="📄 回應結果",
                 font=("Microsoft JhengHei UI", 11, "bold"),
                 bg=THEME["bg_card"], fg=THEME["fg"]).pack(side=tk.LEFT)

        self.result_count_label = tk.Label(
            title_row, text="",
            font=("Microsoft JhengHei UI", 9),
            bg=THEME["bg_card"], fg=THEME["fg_dim"]
        )
        self.result_count_label.pack(side=tk.LEFT, padx=(10, 0))

        HoverButton(title_row, text="清除", width=60, height=26,
                    command=self._clear_output,
                    bg_color=THEME["border"], hover_color=THEME["fg_dim"],
                    font=("Microsoft JhengHei UI", 8)
                    ).pack(side=tk.RIGHT)

        HoverButton(title_row, text="複製", width=60, height=26,
                    command=self._copy_output,
                    bg_color=THEME["border"], hover_color=THEME["fg_dim"],
                    font=("Microsoft JhengHei UI", 8)
                    ).pack(side=tk.RIGHT, padx=(0, 4))
        text_frame = tk.Frame(card, bg=THEME["bg_output"])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.output_text = tk.Text(
            text_frame, wrap=tk.WORD,
            font=("Cascadia Code", 10),
            bg=THEME["bg_output"], fg=THEME["fg"],
            insertbackground=THEME["fg"],
            selectbackground=THEME["accent"],
            relief=tk.FLAT, bd=8,
            state=tk.DISABLED
        )
        scrollbar = tk.Scrollbar(text_frame, command=self.output_text.yview,
                                  bg=THEME["scrollbar"], troughcolor=THEME["bg_output"],
                                  relief=tk.FLAT, width=10)
        self.output_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.output_text.tag_configure("key",    foreground="#c4508a")
        self.output_text.tag_configure("string", foreground="#3a8a5c")
        self.output_text.tag_configure("number", foreground="#c07820")
        self.output_text.tag_configure("bool",   foreground="#d05070")
        self.output_text.tag_configure("null",   foreground="#9a8490")

    # ── 底部狀態列 ────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=THEME["bg_card"], height=28)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        tk.Frame(self, bg=THEME["border"], height=1).pack(fill=tk.X, side=tk.BOTTOM)

        self.statusbar_label = tk.Label(
            bar, text="就緒", anchor="w",
            font=("Microsoft JhengHei UI", 8),
            bg=THEME["bg_card"], fg=THEME["fg_dim"]
        )
        self.statusbar_label.pack(side=tk.LEFT, padx=12)

        self.statusbar_server = tk.Label(
            bar, text=f"🌐 {self.client.base_url}", anchor="e",
            font=("Microsoft JhengHei UI", 8),
            bg=THEME["bg_card"], fg=THEME["fg_dim"]
        )
        self.statusbar_server.pack(side=tk.RIGHT, padx=12)

    # ── 建立卡片 ────────────────────────────────

    def _make_card(self, parent, title: str) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=THEME["bg"])
        wrapper.pack(fill=tk.X, pady=(0, 6))

        card = tk.Frame(wrapper, bg=THEME["bg_card"])
        card.pack(fill=tk.X)

        tk.Label(card, text=title, font=("Microsoft JhengHei UI", 11, "bold"),
                 bg=THEME["bg_card"], fg=THEME["fg"], anchor="w"
                 ).pack(fill=tk.X, padx=12, pady=(10, 6))

        inner = tk.Frame(card, bg=THEME["bg_card"])
        inner.pack(fill=tk.X, padx=12, pady=(0, 10))
        return inner

    # ── 狀態更新 ──────────────────────────────────────────

    def _update_auth_status(self):
        if self.client.is_logged_in:
            self.status_dot.configure(fg=THEME["success"])
            self.status_label.configure(text="已認證", fg=THEME["success"])
        else:
            self.status_dot.configure(fg=THEME["danger"])
            self.status_label.configure(text="未登入", fg=THEME["danger"])

    def _set_status(self, text: str, color: str = None):
        self.statusbar_label.configure(text=text, fg=color or THEME["fg_dim"])

    def _set_loading(self, loading: bool):
        """切換載入狀態"""
        if loading:
            self._set_status("⏳ 請求中...", THEME["warning"])
        self.update_idletasks()

    # ── 顯示資料 ─────────────────────────

    def _show_data(self, data, label: str = "結果"):
        raw = json.dumps(data, indent=2, ensure_ascii=False)

        self.output_text.configure(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        import re
        lines = raw.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                self.output_text.insert(tk.END, "\n")
            m = re.match(r'^(\s*)"(.+?)"(\s*:\s*)(.*)', line)
            if m:
                indent, key, colon, value = m.groups()
                self.output_text.insert(tk.END, indent)
                self.output_text.insert(tk.END, f'"{key}"', "key")
                self.output_text.insert(tk.END, colon)
                self._insert_colored_value(value)
            else:
                stripped = line.strip()
                if stripped.startswith('"'):
                    self.output_text.insert(tk.END, line, "string")
                elif stripped in ("true", "false", "true,", "false,"):
                    self.output_text.insert(tk.END, line, "bool")
                elif stripped in ("null", "null,"):
                    self.output_text.insert(tk.END, line, "null")
                else:
                    self.output_text.insert(tk.END, line)

        self.output_text.configure(state=tk.DISABLED)
        if isinstance(data, list):
            self.result_count_label.configure(text=f"共 {len(data)} 筆")
        elif isinstance(data, dict) and len(data) > 0:
            self.result_count_label.configure(text=f"共 {len(data)} 個Key")
        else:
            self.result_count_label.configure(text="")

    def _insert_colored_value(self, value: str):
        """為 JSON 值套用顏色"""
        v = value.rstrip(",").strip()
        trailing = value[len(value.rstrip(",")):]

        if v.startswith('"'):
            self.output_text.insert(tk.END, value, "string")
        elif v in ("true", "false"):
            self.output_text.insert(tk.END, value, "bool")
        elif v in ("null",):
            self.output_text.insert(tk.END, value, "null")
        elif v.replace(".", "").replace("-", "").isdigit():
            self.output_text.insert(tk.END, value, "number")
        else:
            self.output_text.insert(tk.END, value)

    def _show_error(self, title: str, error: Exception):
        """統一錯誤處理"""
        if isinstance(error, AuthError):
            icon = "🔒"
            self._set_status(f"認證錯誤: {error}", THEME["danger"])
        elif isinstance(error, APIError):
            icon = "❌"
            self._set_status(f"API 錯誤 [{error.status_code}]", THEME["danger"])
        elif isinstance(error, ConnectionError):
            icon = "🌐"
            self._set_status("連線失敗", THEME["danger"])
        elif isinstance(error, ValueError):
            icon = "⚠️"
            self._set_status(f"輸入錯誤: {error}", THEME["warning"])
        else:
            icon = "❗"
            self._set_status(f"錯誤: {error}", THEME["danger"])

        messagebox.showerror(f"{icon} {title}", str(error))

    # ── 非同步執行─────────────────────────

    def _run_async(self, task_fn, success_fn=None, label="操作"):
        """在背景執行 API 呼叫，完成後在主執行緒更新 UI"""
        self._set_loading(True)

        def _worker():
            try:
                result = task_fn()
                self.after(0, lambda: self._on_task_done(result, success_fn, label))
            except Exception as e:
                self.after(0, lambda: self._on_task_error(e, label))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_task_done(self, result, success_fn, label):
        self._set_loading(False)
        self._set_status(f"✅ {label} 完成", THEME["success"])
        if success_fn:
            success_fn(result)

    def _on_task_error(self, error, label):
        self._set_loading(False)
        self._show_error(label, error)

    # ── 操作實作 ──────────────────────────────────────────

    def _do_login(self):
        token = self.token_entry.get_value().strip()
        if not token:
            messagebox.showwarning("⚠️ 提示", "請輸入 API Token")
            return
        self.client.save_token(token)
        self._update_auth_status()
        self._set_status("✅ 登入成功", THEME["success"])
        messagebox.showinfo("✅ 成功", "已登入並儲存 Token")

    def _do_logout(self):
        if not self.client.is_logged_in:
            messagebox.showinfo("提示", "目前未登入")
            return
        if not messagebox.askyesno("確認登出", "確定要登出嗎？\n本地 Token 將被刪除。"):
            return
        self.client.logout()
        self._update_auth_status()
        self.token_entry.clear()
        self._set_status("已登出", THEME["fg_dim"])

    def _do_test_connection(self):
        self._run_async(
            task_fn=self.client.test_connection,
            success_fn=lambda ok: (
                messagebox.showinfo("✅ 連線成功", "API 伺服器回應正常") if ok
                else messagebox.showwarning("⚠️ 連線失敗", "伺服器無回應或狀態異常")
            ),
            label="連線測試"
        )

    def _do_get_all(self):
        self._run_async(
            task_fn=self.client.get_all,
            success_fn=lambda data: self._show_data(data, "全部黑名單"),
            label="查詢全部"
        )

    def _do_get_user(self):
        user_id = self.query_id_entry.get_value().strip()
        if not user_id:
            messagebox.showwarning("⚠️ 提示", "請輸入使用者 ID")
            return
        self._run_async(
            task_fn=lambda: self.client.get_user(user_id),
            success_fn=lambda data: self._show_data(data, f"使用者 {user_id}"),
            label=f"查詢 {user_id}"
        )

    def _do_add_user(self):
        uid = self.add_id_entry.get_value().strip()
        by  = self.add_by_entry.get_value().strip()
        reason = self.add_reason_entry.get_value().strip()
        mode = self.mode_var.get()

        if not uid:
            messagebox.showwarning("⚠️ 提示", "請輸入使用者 ID")
            return
        if not by:
            messagebox.showwarning("⚠️ 提示", "請輸入操作者")
            return

        mode_label = {"block": "封鎖", "global_ban": "全域封禁"}.get(mode, mode)
        if not messagebox.askyesno(
            "確認新增",
            f"確定要將使用者 {uid} 加入黑名單嗎？\n\n"
            f"模式：{mode_label}\n操作者：{by}\n原因：{reason or '(無)'}"
        ):
            return

        self._run_async(
            task_fn=lambda: self.client.add_user(uid, by, mode, reason),
            success_fn=lambda data: (
                self._show_data(data, "新增結果"),
                self.add_id_entry.clear(),
                self.add_reason_entry.clear(),
            ),
            label=f"新增 {uid}"
        )

    def _do_remove_user(self):
        uid = self.remove_id_entry.get_value().strip()
        if not uid:
            messagebox.showwarning("⚠️ 提示", "請輸入使用者 ID")
            return
        if not messagebox.askyesno("確認移除", f"確定要從黑名單移除使用者 {uid} 嗎？"):
            return

        self._run_async(
            task_fn=lambda: self.client.remove_user(uid),
            success_fn=lambda data: (
                self._show_data(data, "移除結果"),
                self.remove_id_entry.clear(),
            ),
            label=f"移除 {uid}"
        )

    def _do_override(self):
        filepath = filedialog.askopenfilename(
            title="選擇要匯入的 JSON 檔案",
            filetypes=[("JSON 檔案", "*.json"), ("所有檔案", "*.*")]
        )
        if not filepath:
            return

        if not messagebox.askyesno(
            "⚠️ 覆蓋確認",
            "此操作將覆蓋整份黑名單資料！\n\n"
            "系統會自動在覆蓋前備份當前資料。\n確定要繼續嗎？",
            icon="warning"
        ):
            return

        def _task():
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self.client.override(data)

        self._run_async(
            task_fn=_task,
            success_fn=lambda data: self._show_data(data, "覆蓋結果"),
            label="匯入覆蓋"
        )

    def _do_save_all(self):
        filepath = filedialog.asksaveasfilename(
            title="匯出黑名單",
            defaultextension=".json",
            filetypes=[("JSON 檔案", "*.json")]
        )
        if not filepath:
            return

        def _task():
            data = self.client.get_all()
            self.client.save_to_file(data, filepath)
            return data

        self._run_async(
            task_fn=_task,
            success_fn=lambda data: (
                self._show_data(data, "匯出資料"),
                messagebox.showinfo("✅ 匯出成功", f"已儲存至：\n{filepath}")
            ),
            label="匯出全部"
        )

    # ── Token 顯示切換 ───────────────────────────────────

    def _toggle_token_visibility(self, _event=None):
        self._show_token = not self._show_token
        if self.token_entry._has_real_text:
            self.token_entry.configure(show="" if self._show_token else "●")
        self.toggle_eye_btn.configure(
            text="🙈" if self._show_token else "👁",
            fg=THEME["fg"] if self._show_token else THEME["fg_dim"]
        )

    # ── 輸出區操作 ────────────────────────────────────────

    def _clear_output(self):
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.configure(state=tk.DISABLED)
        self.result_count_label.configure(text="")
        self._set_status("已清除輸出", THEME["fg_dim"])

    def _copy_output(self):
        self.output_text.configure(state=tk.NORMAL)
        content = self.output_text.get("1.0", tk.END).strip()
        self.output_text.configure(state=tk.DISABLED)
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self._set_status("📋 已複製到剪貼簿", THEME["success"])
        else:
            self._set_status("沒有可複製的內容", THEME["fg_dim"])


    # ── 程式入口點 ─────────────────────────────────────────

if __name__ == "__main__":
    app = BlacklistApp()
    app.mainloop()
