"""TekTıkla kurulum programı (TekTikla-Setup-x.y.z.exe).

İçine gömülü payload.zip'teki uygulamayı yönetici izni istemeden
%LOCALAPPDATA%\\Programs\\TekTıkla klasörüne kurar, kısayolları ve "Programlar ve Özellikler"
kaydını oluşturur. Aynı exe, kurulum klasörüne "uninstall.exe" olarak kopyalanır ve
--uninstall ile kaldırıcı olarak çalışır.

Parametreler:  /SILENT  arayüzsüz kur ve TekTıkla'yı başlat (uygulama içi güncelleme bunu kullanır)
               --uninstall  kaldır
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
import winreg
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from _version import VERSION  # derleme sırasında build_release.py üretir
except ImportError:
    VERSION = "0.0.0"

APP_NAME = "TekTıkla"
APP_EXE = "TekTikla.exe"
PUBLISHER = "TekTıkla"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TekTikla"
WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_KEYS = (rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_GUID}",
                 rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_GUID}")
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/#download"
NO_WINDOW = subprocess.CREATE_NO_WINDOW

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home()))
DEFAULT_DIR = LOCAL / "Programs" / APP_NAME
START_MENU = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
DATA_DIRS = [Path(os.environ.get("APPDATA", "")) / "TekTikla", LOCAL / "TekTikla"]

# Uygulamanın varsayılan "Siyah" temasıyla aynı renkler
BG, PANEL, TEXT, MUTED, FAINT = "#0A0A0A", "#161616", "#F2F2F2", "#8E8E8E", "#4A4A4A"
# düğme renkleri: (zemin, üzerine gelince, yazı)
BTN_STYLES = {"primary": ("#FFFFFF", "#DCDCDC", "#0A0A0A"), "secondary": ("#1E1E1E", "#2A2A2A", "#F2F2F2")}


def resource(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / name


class RoundButton(tk.Canvas):
    """Yuvarlak köşeli, sabit boyutlu düğme. Kenar yumuşatması için build_release.py'nin ürettiği
    btn_<tür>[_hover]_<en>x<boy>.png zeminlerini kullanır; bulamazsa köşeleri tuvalde çizer."""

    def __init__(self, parent, text, command, kind="secondary", width=132, height=44, font_size=11):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2")
        self.action, self.enabled, self.kind = command, True, kind
        self._bw, self._bh = width, height  # _w Tk'nin kendi iç adı, ezilmemeli
        self._images = {}
        for state in ("", "_hover"):
            path = resource(f"btn_{kind}{state}_{width}x{height}.png")
            if path.exists():
                try:
                    self._images[state] = tk.PhotoImage(file=str(path))
                except tk.TclError:
                    pass
        self._bg_item = None
        self._label = self.create_text(width / 2, height / 2, text=text, font=(FONT, font_size, "bold"),
                                       fill=BTN_STYLES[kind][2])
        self._paint(False)
        self.bind("<Enter>", lambda e: self._paint(True))
        self.bind("<Leave>", lambda e: self._paint(False))
        self.bind("<Button-1>", lambda e: self.action() if self.enabled else None)

    def _paint(self, hover: bool) -> None:
        hover = hover and self.enabled
        if self._bg_item:
            self.delete(self._bg_item)
        img = self._images.get("_hover" if hover else "")
        if img:
            self._bg_item = self.create_image(0, 0, image=img, anchor="nw")
        else:
            w, h, r = self._bw - 1, self._bh - 1, 12
            pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
            self._bg_item = self.create_polygon(pts, smooth=True, fill=BTN_STYLES[self.kind][1 if hover else 0])
        self.tag_lower(self._bg_item)

    def configure_text(self, text: str) -> None:
        self.itemconfigure(self._label, text=text)

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        self.itemconfigure(self._label, fill=BTN_STYLES[self.kind][2] if on else FAINT)
        self.configure(cursor="hand2" if on else "arrow")
        self._paint(False)


def load_font() -> str:
    """Uygulamadaki Geist fontunu sisteme kurmadan, yalnızca bu süreç için yükler."""
    path = resource("Geist.ttf")
    try:
        import ctypes
        if path.exists() and ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, None):  # FR_PRIVATE
            return "Geist"
    except OSError:
        pass
    return "Segoe UI"


FONT = load_font()


# ----------------------------------------------------------------------------- sistem işleri

def desktop_dir() -> Path:
    if os.environ.get("TT_TEST_DESKTOP"):  # yalnızca otomatik testler için: gerçek masaüstüne dokunmasın
        return Path(os.environ["TT_TEST_DESKTOP"])
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return Path(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
    except OSError:
        return Path.home() / "Desktop"


def make_shortcut(link: Path, target: Path) -> None:
    # Türkçe karakterli yollar bozulmasın diye değerleri ortam değişkeniyle, komutu UTF-16 base64 ile veriyoruz
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TT_LINK);"
        "$s.TargetPath=$env:TT_TARGET;$s.WorkingDirectory=$env:TT_WORKDIR;"
        "$s.IconLocation=$env:TT_ICON;$s.Description=$env:TT_DESC;$s.Save()"
    )
    env = dict(os.environ, TT_LINK=str(link), TT_TARGET=str(target), TT_WORKDIR=str(target.parent),
               TT_ICON=f"{target},0", TT_DESC="TekTıkla - Bütün sitelerden video indir")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                    base64.b64encode(script.encode("utf-16-le")).decode()],
                   env=env, creationflags=NO_WINDOW, check=True, timeout=60, capture_output=True)


def webview2_installed() -> bool:
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key in WEBVIEW2_KEYS:
            try:
                with winreg.OpenKey(root, key) as k:
                    if winreg.QueryValueEx(k, "pv")[0] not in ("", "0.0.0.0"):
                        return True
            except OSError:
                continue
    return False


def installed_dir() -> Path | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            return Path(winreg.QueryValueEx(k, "InstallLocation")[0])
    except OSError:
        return None


def app_running(install_dir: Path) -> bool:
    exe = install_dir / APP_EXE
    if not exe.exists():
        return False
    try:  # çalışan bir exe yeniden adlandırılamaz
        tmp = exe.with_suffix(".check")
        exe.rename(tmp)
        tmp.rename(exe)
        return False
    except OSError:
        return True


def close_app() -> None:
    subprocess.run(["taskkill", "/IM", APP_EXE, "/F"], creationflags=NO_WINDOW, capture_output=True)


def install(target: Path, desktop: bool, progress) -> Path:
    staging = target.with_name(target.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(resource("payload.zip")) as z:
        members = z.infolist()
        total = sum(m.file_size for m in members) or 1
        done = 0
        for m in members:
            z.extract(m, staging)
            done += m.file_size
            progress(done / total * 0.85, "Dosyalar kopyalanıyor…")

    progress(0.88, "Eski sürüm değiştiriliyor…")
    old = target.with_name(target.name + ".old")
    shutil.rmtree(old, ignore_errors=True)
    if target.exists():
        for _ in range(60):  # güncellemede uygulamanın kapanmasını bekle
            try:
                target.rename(old)
                break
            except OSError:
                time.sleep(0.5)
        else:
            shutil.rmtree(staging, ignore_errors=True)
            raise RuntimeError("TekTıkla hâlâ açık. Kapatıp tekrar deneyin.")
    staging.rename(target)
    shutil.rmtree(old, ignore_errors=True)

    progress(0.92, "Kaldırıcı ve kayıt oluşturuluyor…")
    uninstaller = target / "uninstall.exe"
    shutil.copyfile(sys.executable, uninstaller)
    exe = target / APP_EXE
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
        for name, value in {
            "DisplayName": APP_NAME, "DisplayVersion": VERSION, "Publisher": PUBLISHER,
            "DisplayIcon": f"{exe},0", "InstallLocation": str(target),
            "UninstallString": f'"{uninstaller}" --uninstall',
            "QuietUninstallString": f'"{uninstaller}" --uninstall /SILENT',
        }.items():
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        size_kb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) // 1024
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, int(size_kb))

    progress(0.96, "Kısayollar oluşturuluyor…")
    START_MENU.mkdir(parents=True, exist_ok=True)
    make_shortcut(START_MENU / f"{APP_NAME}.lnk", exe)
    if desktop:
        make_shortcut(desktop_dir() / f"{APP_NAME}.lnk", exe)
    progress(1.0, "Kurulum tamamlandı")
    return exe


def uninstall(remove_data: bool) -> None:
    target = installed_dir() or DEFAULT_DIR
    if app_running(target):
        close_app()
        time.sleep(1)
    for link in (START_MENU / f"{APP_NAME}.lnk", desktop_dir() / f"{APP_NAME}.lnk"):
        link.unlink(missing_ok=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass
    if remove_data:
        for d in DATA_DIRS:
            shutil.rmtree(d, ignore_errors=True)
    # Kaldırıcı kendi klasöründen çalışıyor; klasörü, biz kapanıp dosya kilidi kalkınca silecek ayrı bir süreç
    # başlatıyoruz. Yol, Türkçe karakterler bozulmasın diye ortam değişkeniyle geçiyor.
    if target.name == APP_NAME and (target / APP_EXE).exists():
        script = ("for($i=0;$i -lt 30;$i++){Start-Sleep -Milliseconds 700;"
                  "Remove-Item -LiteralPath $env:TT_DIR -Recurse -Force -ErrorAction SilentlyContinue;"
                  "if(-not (Test-Path -LiteralPath $env:TT_DIR)){break}}")
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                          base64.b64encode(script.encode("utf-16-le")).decode()],
                         env=dict(os.environ, TT_DIR=str(target)), cwd=tempfile.gettempdir(),
                         # DETACHED_PROCESS değil: konsolsuz kalan PowerShell hiçbir şey yapmadan kapanıyor
                         creationflags=NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)


# ----------------------------------------------------------------------------- arayüz

class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} Kurulumu")
        self.configure(bg=BG)
        self.resizable(False, False)
        w, h = 580, 440
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{(self.winfo_screenheight() - h) // 3}")
        try:
            self.iconbitmap(str(resource("tektikla.ico")))
        except tk.TclError:
            pass
        self._dark_title()

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TekTikla.Horizontal.TProgressbar", troughcolor="#1E1E1E", background="#FFFFFF",
                        bordercolor="#1E1E1E", lightcolor="#FFFFFF", darkcolor="#FFFFFF", thickness=8)

        header = tk.Canvas(self, width=w, height=128, highlightthickness=0, bg=BG)
        header.pack()
        for y in range(128):  # koyu griden siyaha dikey degrade
            c = int(26 - 16 * y / 127)
            header.create_line(0, y, w, y, fill="#%02x%02x%02x" % (c, c, c))
        header.create_line(0, 127, w, 127, fill="#202020")
        text_x = 40
        try:
            self.logo = tk.PhotoImage(file=str(resource("logo72.png")))
            header.create_image(40, 64, image=self.logo, anchor="w")
            text_x = 130
        except tk.TclError:
            pass
        header.create_text(text_x, 50, text=APP_NAME, anchor="w", fill=TEXT, font=(FONT, 28, "bold"))
        header.create_text(text_x + 2, 88, text=f"Bütün sitelerden video indirici  ·  v{VERSION}", anchor="w",
                           fill=MUTED, font=(FONT, 11))

        body = tk.Frame(self, bg=BG, padx=40, pady=24)
        body.pack(fill="both", expand=True)
        existing = installed_dir()
        self.title_lbl = tk.Label(body, text="TekTıkla güncellenecek" if existing else "TekTıkla bilgisayarınıza kurulacak",
                                  bg=BG, fg=TEXT, font=(FONT, 15, "bold"), anchor="w")
        self.title_lbl.pack(fill="x")
        self.target = existing or DEFAULT_DIR
        self.path_row = row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(12, 6))
        # düğme önce yerleşir ki uzun bir yol onu pencereden dışarı itmesin
        self.change_btn = RoundButton(row, "Değiştir", self._pick_dir, width=104, height=36, font_size=10)
        self.change_btn.pack(side="right", padx=(10, 0))
        self.path_lbl = tk.Label(row, text=str(self.target), bg=PANEL, fg=MUTED, font=(FONT, 9), anchor="w",
                                 padx=12, pady=9, width=1)
        self.path_lbl.pack(side="left", fill="x", expand=True)

        self.desktop_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=True)
        self.checks = []
        for text, var in (("Masaüstüne kısayol oluştur", self.desktop_var),
                          ("Kurulumdan sonra TekTıkla'yı başlat", self.launch_var)):
            cb = tk.Checkbutton(body, text=text, variable=var, bg=BG, fg=TEXT, selectcolor="#1E1E1E",
                                activebackground=BG, activeforeground=TEXT, font=(FONT, 10), anchor="w",
                                bd=0, highlightthickness=0)
            cb.pack(fill="x", pady=(8, 0))
            self.checks.append(cb)

        self.bar = ttk.Progressbar(body, style="TekTikla.Horizontal.TProgressbar", maximum=1.0)
        self.status = tk.Label(body, text="", bg=BG, fg=MUTED, font=(FONT, 10), anchor="w", justify="left")

        foot = tk.Frame(self, bg=BG, padx=40, pady=22)
        foot.pack(fill="x", side="bottom")
        # iki düğme de aynı boyutta: "Bitir" de "Kur" kadar büyük ve belirgin
        self.main_btn = RoundButton(foot, "Güncelle" if existing else "Kur", self._start, kind="primary")
        self.main_btn.pack(side="right")
        self.cancel_btn = RoundButton(foot, "İptal", self.destroy)
        self.cancel_btn.pack(side="right", padx=(0, 12))
        self.exe: Path | None = None

        if not webview2_installed():
            self.after(400, self._warn_webview2)

    def _dark_title(self):
        try:
            import ctypes
            self.update()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:  # noqa: BLE001 - eski Windows'ta desteklenmeyebilir
            pass

    @staticmethod
    def _set_enabled(btn: RoundButton, on: bool) -> None:
        btn.set_enabled(on)

    def _pick_dir(self):
        path = filedialog.askdirectory(initialdir=str(self.target.parent), title="Kurulum klasörü")
        if path:
            self.target = Path(path) / APP_NAME
            self.path_lbl.configure(text=str(self.target))

    def _warn_webview2(self):
        if messagebox.askyesno(APP_NAME, "TekTıkla'nın arayüzü için Microsoft Edge WebView2 gerekiyor ve bu bilgisayarda "
                               "bulunamadı.\n\nİndirme sayfası açılsın mı? (Kurulumdan sonra da kurabilirsiniz.)"):
            webbrowser.open(WEBVIEW2_URL)

    def _start(self):
        if app_running(self.target):
            if not messagebox.askyesno(APP_NAME, "TekTıkla şu anda açık. Kapatılıp kuruluma devam edilsin mi?"):
                return
            close_app()
            time.sleep(1)
        for w in (self.main_btn, self.cancel_btn, self.change_btn):
            self._set_enabled(w, False)
        for cb in self.checks:
            cb.configure(state="disabled")
        self.bar.pack(fill="x", pady=(18, 6))
        self.status.pack(fill="x")
        desktop = self.desktop_var.get()

        def progress(frac, text):
            self.after(0, lambda: (self.bar.configure(value=frac), self.status.configure(text=text)))

        def work():
            try:
                self.exe = install(self.target, desktop, progress)
                self.after(0, self._done)
            except Exception as e:  # noqa: BLE001
                self.after(0, lambda: self._failed(str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _done(self):
        self.title_lbl.configure(text="✓  Kurulum tamamlandı")
        self.path_row.pack_forget()
        self.checks[0].pack_forget()  # kısayol seçimi artık geçmişte kaldı; "başlat" seçeneği kalsın
        self.checks[1].configure(state="normal", text="TekTıkla'yı şimdi başlat")
        self.bar.pack_forget()
        self.status.configure(fg=TEXT, text="TekTıkla, Başlat menüsünde" +
                              (" ve masaüstünde hazır." if self.desktop_var.get() else " hazır."))
        self.status.pack(fill="x", pady=(10, 4), after=self.title_lbl)
        self.cancel_btn.pack_forget()
        self.main_btn.configure_text("Bitir")
        self.main_btn.action = self._finish
        self._set_enabled(self.main_btn, True)

    def _finish(self):
        if self.launch_var.get() and self.exe:
            subprocess.Popen([str(self.exe)], cwd=str(self.exe.parent), creationflags=subprocess.DETACHED_PROCESS)
        self.destroy()

    def _failed(self, message):
        messagebox.showerror(APP_NAME, f"Kurulum başarısız oldu:\n\n{message}")
        for w in (self.main_btn, self.cancel_btn, self.change_btn):
            self._set_enabled(w, True)
        for cb in self.checks:
            cb.configure(state="normal")


def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]
    silent = "/silent" in args or "/verysilent" in args
    if "--uninstall" in args:
        if silent:
            uninstall(remove_data=False)
            return
        root = tk.Tk()
        root.withdraw()
        if messagebox.askyesno(APP_NAME, "TekTıkla bilgisayarınızdan kaldırılsın mı?"):
            remove_data = messagebox.askyesno(APP_NAME, "Ayarlar, indirme geçmişi ve indirilen bileşenler (FFmpeg) de "
                                              "silinsin mi?\n\nİndirdiğiniz videolar silinmez.")
            uninstall(remove_data)
            messagebox.showinfo(APP_NAME, "TekTıkla kaldırıldı.")
        root.destroy()
        return
    if silent:  # uygulama içi güncelleme: sessizce kur ve TekTıkla'yı yeniden aç
        target = installed_dir() or DEFAULT_DIR
        exe = install(target, desktop=(desktop_dir() / f"{APP_NAME}.lnk").exists(), progress=lambda f, t: None)
        subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=subprocess.DETACHED_PROCESS)
        return
    Wizard().mainloop()


if __name__ == "__main__":
    main()
