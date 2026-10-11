#!/usr/bin/env python3
"""Generate a 1920x1080 keybindings wallpaper from this machine's live Omarchy bindings.

Reads `omarchy menu keybindings --print`, validates every row of a curated sheet
against it, balances the sheet into columns, and renders a Tokyo Night PNG via
pango-view + ImageMagick.

Usage:
  keybindings-wallpaper.py                    # generate into ./dist
  keybindings-wallpaper.py --output PATH      # write the PNG to PATH
  keybindings-wallpaper.py --install          # generate, install into the current theme, apply

Dependencies (Arch): pango (pango-view), imagemagick, fontconfig-noto
"""
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "dist", "keybindings-wallpaper.png")
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

W, H = 1920, 1080
BG = "#1a1b26"
FG = "#c0caf5"
DIM = "#565f89"
KEY = "#7aa2f7"
LABEL = "#a9b1d6"
HEAD = "#ff9e64"
ACCENT = "#bb9af7"
FONT = "JetBrainsMono Nerd Font"
FONT_BOLD = "JetBrainsMono Nerd Font Bold"
MARGIN_X = 58
TOP = 136
BOTTOM = 52
GAP = 30
NCOL = 4

MODS = ["SUPER", "SHIFT", "CTRL", "ALT"]
MOD_LABEL = {"SUPER": "Super", "SHIFT": "Shift", "CTRL": "Ctrl", "ALT": "Alt"}
KEY_ALIAS = {
    "RETURN": "Return", "ESCAPE": "Esc", "DELETE": "Del", "SPACE": "Space",
    "TAB": "Tab", "PRINT": "Print", "BACKSPACE": "Backspace", "MINUS": "-",
    "EQUAL": "=", "SLASH": "/", "COMMA": ",", "PERIOD": ".", "HOME": "Home",
    "BRACKETLEFT": "[", "BRACKETRIGHT": "]", "Delete": "Del",
    "UP": "\u2191", "DOWN": "\u2193",
    "LEFT": "\u2190", "RIGHT": "\u2192", "mouse_down": "scroll down",
    "mouse_up": "scroll up", "LEFT MOUSE BUTTON": "LMB",
    "RIGHT MOUSE BUTTON": "RMB",
    "XF86AudioRaiseVolume": "vol up", "XF86AudioLowerVolume": "vol down",
    "XF86AudioMute": "mute", "XF86AudioMicMute": "mic mute",
    "XF86AudioPlay": "play", "XF86AudioPause": "pause", "XF86AudioNext": "next",
    "XF86AudioPrev": "prev", "XF86MonBrightnessUp": "bright up",
    "XF86MonBrightnessDown": "bright down", "XF86KbdBrightnessUp": "kbd bright up",
    "XF86KbdBrightnessDown": "kbd bright down", "XF86KbdLightOnOff": "kbd light",
    "XF86TouchpadToggle": "touchpad toggle", "XF86TouchpadOn": "touchpad on",
    "XF86TouchpadOff": "touchpad off", "XF86PowerOff": "power key",
    "XF86Calculator": "calc key", "XF86Eject": "eject",
}


def normalize(raw_key: str) -> str:
    """'SUPER SHIFT CTRL + SPACE' -> 'Super+Shift+Ctrl+Space'"""
    raw_key = raw_key.strip()
    head, _, tail = raw_key.partition("+")
    words = head.split()
    mods = [w for w in words if w in MODS]
    other = [w for w in words if w not in MODS]
    key = " ".join(other + ([tail.strip()] if tail.strip() else [])).strip()
    if key in KEY_ALIAS:
        key = KEY_ALIAS[key]
    elif len(key) == 1:
        key = key.upper()
    return "+".join([MOD_LABEL[m] for m in MODS if m in mods] + [key])


def live_bindings():
    out = subprocess.run(["omarchy", "menu", "keybindings", "--print"],
                        capture_output=True, text=True, check=True).stdout
    live = []
    for line in out.splitlines():
        if "\u2192" not in line:
            continue
        raw_key, _, desc = line.partition("\u2192")
        live.append((normalize(raw_key), desc.strip()))
    return live


def d(*keys):
    return list(keys)


DIGITS = "1234567890"
ARROWS = ["\u2191", "\u2193", "\u2190", "\u2192"]

# (display key, label, live keys it stands for)
SHEET = [
    ("核心", [
        ("Super+Space", "Omarchy 菜单", None),
        ("Super+Alt+Space", "应用菜单", None),
        ("Super+Esc", "系统菜单", None),
        ("Super+Return", "终端", None),
        ("Super+Shift+Return", "浏览器", None),
        ("Super+Shift+F", "文件管理器", None),
        ("Super+Shift+Alt+F", "文件管理器(当前目录)", None),
        ("Super+Shift+Ctrl+Space", "主题菜单", None),
        ("Super+Ctrl+Space", "壁纸切换", None),
        ("Super+Ctrl+O", "总菜单开关", None),
        ("Super+K", "键位速查", None),
        ("Super+Alt+K", "Tmux 键位", None),
        ("Super+Ctrl+K", "Herdr 键位", None),
        ("Super+Ctrl+L", "锁屏", None),
    ]),
    ("窗口", [
        ("Super+W", "关闭窗口", None),
        ("Ctrl+Alt+Del", "关闭所有窗口", None),
        ("Super+T", "浮动 / 平铺", None),
        ("Super+J", "切换分割方向", None),
        ("Super+O", "弹出为浮窗", None),
        ("Super+F", "全屏", None),
        ("Super+Alt+F", "全宽", None),
        ("Super+Ctrl+F", "平铺全屏", None),
        ("Super+L", "切换工作区布局", None),
        ("Super+P", "伪平铺窗口", None),
        ("Super+G", "窗口分组开关", None),
        ("Super+Backspace", "窗口透明度", None),
        ("Super+Shift+Backspace", "窗口间隙", None),
        ("Super+Ctrl+Backspace", "单窗口方形", None),
        ("Super+LMB", "拖动窗口", None),
        ("Super+RMB", "缩放窗口", None),
        ("Super+Home", "恢复窗口宽度", None),
        ("Super+Alt+Home", "保存窗口宽度", None),
        ("Super+S", "暂存区开关", None),
        ("Super+Alt+S", "移入暂存区", None),
    ]),
    ("焦点 / 导航", [
        ("Super+" + "".join(ARROWS), "聚焦方向窗口",
         d(*[f"Super+{a}" for a in ARROWS])),
        ("Super+Shift+" + "".join(ARROWS), "交换窗口位置",
         d(*[f"Super+Shift+{a}" for a in ARROWS])),
        ("Super+滚轮", "滚动工作区", d("Super+scroll down", "Super+scroll up")),
        ("Alt+Tab", "下一窗口", None),
        ("Shift+Alt+Tab", "上一窗口", None),
        ("Ctrl+Alt+Tab", "下一显示器", None),
        ("Shift+Ctrl+Alt+Tab", "上一显示器", None),
        ("Super+Tab", "下一工作区", None),
        ("Super+Shift+Tab", "上一工作区", None),
        ("Super+Ctrl+Tab", "回到上次工作区", None),
    ]),
    ("工作区", [
        ("Super+1..0", "切换到工作区 1-10", d(*[f"Super+{n}" for n in DIGITS])),
        ("Super+Shift+1..0", "移窗口到工作区", d(*[f"Super+Shift+{n}" for n in DIGITS])),
        ("Super+Shift+Alt+1..0", "静默移窗口到工作区",
         d(*[f"Super+Shift+Alt+{n}" for n in DIGITS])),
        ("Super+Shift+Alt+" + "".join(ARROWS), "工作区移到方向屏",
         d(*[f"Super+Shift+Alt+{a}" for a in ARROWS])),
    ]),
    ("窗口尺寸", [
        ("Super+- / =", "左缩 / 左扩", d("Super+-", "Super+=")),
        ("Super+Alt+- / =", "左向微调", d("Super+Alt+-", "Super+Alt+=")),
        ("Super+Ctrl+- / =", "左向大调", d("Super+Ctrl+-", "Super+Ctrl+=")),
        ("Super+Shift+- / =", "下缩 / 下扩", d("Super+Shift+-", "Super+Shift+=")),
        ("Super+Shift+Alt+- / =", "下向微调",
         d("Super+Shift+Alt+-", "Super+Shift+Alt+=")),
        ("Super+Shift+Ctrl+- / =", "下向大调",
         d("Super+Shift+Ctrl+-", "Super+Shift+Ctrl+=")),
    ]),
    ("窗口分组", [
        ("Super+Alt+Tab", "组内下一窗口", None),
        ("Super+Shift+Alt+Tab", "组内上一窗口", None),
        ("Super+Alt+1..5", "切到组内窗口 1-5", d(*[f"Super+Alt+{n}" for n in "12345"])),
        ("Super+Alt+" + "".join(ARROWS), "移入方向组",
         d(*[f"Super+Alt+{a}" for a in ARROWS])),
        ("Super+Alt+G", "移出分组", None),
        ("Super+Ctrl+\u2190 / \u2192", "组内焦点移动",
         d("Super+Ctrl+\u2190", "Super+Ctrl+\u2192")),
    ]),
    ("剪贴板 / 捕获", [
        ("Super+C / V / X", "复制 / 粘贴 / 剪切", d("Super+C", "Super+V", "Super+X")),
        ("Super+Ctrl+V", "剪贴板历史", None),
        ("Super+Ctrl+E", "Emoji 选择", None),
        ("Print", "截图", None),
        ("Alt+Print", "录屏", None),
        ("Super+Print", "屏幕取色", None),
        ("Super+Ctrl+Print", "截图 OCR 取字", None),
        ("Super+Ctrl+C", "捕获菜单", None),
        ("Super+Ctrl+S", "分享", None),
        ("Super+Ctrl+.", "视频转码", None),
        ("Shift+Alt+D", "下载网页视频", None),
        ("Shift+Alt+L", "复制网页 URL", None),
        ("Super+Alt+[ / ]", "摄像头画中画", d("Super+Alt+[", "Super+Alt+]")),
    ]),
    ("系统 / 面板", [
        ("Super+Ctrl+A", "音量", None),
        ("Super+Ctrl+B", "蓝牙", None),
        ("Super+Ctrl+W", "网络", None),
        ("Super+Ctrl+P", "电源", None),
        ("Super+Ctrl+D", "显示器", None),
        ("Super+Ctrl+H", "硬件", None),
        ("Super+Ctrl+Q", "计算器", None),
        ("Super+Ctrl+T", "活动", None),
        ("Super+Ctrl+N", "夜灯", None),
        ("Super+Ctrl+I", "空闲锁定", None),
        ("Super+Ctrl+Z", "放大", None),
        ("Super+Ctrl+Alt+Z", "重置缩放", None),
        ("Super+/", "放大输出", None),
        ("Super+Alt+/", "缩小输出", None),
        ("Super+Ctrl+Del", "笔记本内屏开关", None),
        ("Super+Ctrl+Alt+Del", "镜像笔记本屏", None),
        ("Super+Shift+Space", "顶栏开关", None),
        ("Super+Ctrl+1..9", "顶栏面板 1-9", d(*[f"Super+Ctrl+{n}" for n in "123456789"])),
    ]),
    ("提醒 / 通知", [
        ("Super+Ctrl+R", "设置提醒", None),
        ("Super+Ctrl+Alt+R", "查看提醒", None),
        ("Super+Shift+Ctrl+R", "清除提醒", None),
        ("Super+Ctrl+Alt+D", "日历", None),
        ("Super+Shift+C", "日历 (网页)", None),
        ("Super+Ctrl+Alt+T", "显示时间", None),
        ("Super+Ctrl+Alt+B", "剩余电量", None),
        ("Super+Ctrl+Alt+W", "天气", None),
        ("Super+,", "关闭最近通知", None),
        ("Super+Alt+,", "重播最近通知", None),
        ("Super+Shift+,", "关闭全部通知", None),
        ("Super+Shift+Alt+,", "通知历史", None),
        ("Super+Ctrl+,", "通知静音", None),
    ]),
    ("应用", [
        ("Super+Shift+A", "ChatGPT", None),
        ("Super+Shift+Alt+A", "Grok", None),
        ("Super+Shift+Ctrl+A", "Agent", None),
        ("Super+Shift+E", "邮件", None),
        ("Super+Shift+Alt+E", "新邮件", None),
        ("Super+Shift+G", "Signal", None),
        ("Super+Shift+Ctrl+G", "Google Messages", None),
        ("Super+Shift+Alt+G", "WhatsApp", None),
        ("Super+Shift+M", "音乐", None),
        ("Super+Shift+Alt+M", "音乐 TUI", None),
        ("Super+Shift+N", "编辑器", None),
        ("Super+Shift+O", "Obsidian", None),
        ("Super+Shift+W", "Omawrite", None),
        ("Super+Shift+P", "Google Photos", None),
        ("Super+Shift+S", "Google Maps", None),
        ("Super+Shift+X", "X", None),
        ("Super+Shift+Alt+X", "发 X 帖", None),
        ("Super+Shift+Y", "YouTube", None),
        ("Super+Shift+/", "密码", None),
        ("Super+Shift+D", "Docker", None),
        ("Super+Shift+B", "浏览器", None),
        ("Super+Shift+Alt+B", "隐私浏览器", None),
    ]),
    ("功能键", [
        ("音量键 \u00b1", "音量加 / 减", d("vol up", "vol down")),
        ("Alt+音量键 \u00b1", "精细音量", d("Alt+vol up", "Alt+vol down")),
        ("静音键", "静音", d("mute")),
        ("Shift+静音键", "切换音频输出", d("Shift+mute")),
        ("麦静音键", "麦克风静音", d("mic mute")),
        ("播放键", "播放 / 暂停", d("play", "pause")),
        ("上/下一首", "上一首 / 下一首", d("prev", "next")),
        ("Shift+播放键", "切换媒体源", d("Shift+play", "Shift+pause")),
        ("亮度键 \u00b1", "亮度加 / 减", d("bright up", "bright down")),
        ("Alt+亮度键 \u00b1", "精细亮度", d("Alt+bright up", "Alt+bright down")),
        ("Shift+亮度键 \u00b1", "最亮 / 最暗",
         d("Shift+bright up", "Shift+bright down")),
        ("背光键 \u00b1", "键盘背光加 / 减", d("kbd bright up", "kbd bright down")),
        ("背光灯键", "背光循环", d("kbd light")),
        ("触摸板键", "触摸板开关",
         d("touchpad toggle", "touchpad on", "touchpad off")),
        ("电源键", "电源菜单", d("power key")),
        ("计算器键", "计算器", d("calc key")),
        ("弹出键", "弹出介质", d("eject")),
    ]),
]


# ------------------------------------------------------------------- metrics
def cells(text: str) -> float:
    """Advance width in em units (narrow 0.6, wide/CJK 1.0)."""
    return sum(1.0 if unicodedata.east_asian_width(c) in ("W", "F") else 0.6
               for c in text)


def render(text_path, out_png, line_spacing):
    subprocess.run([
        "pango-view", "-q", "--markup", f"--font={FONT}",
        f"--line-spacing={line_spacing}", "--spacing=0", "--margin=0",
        "--background=transparent", "--dpi=96",
        f"--output={out_png}", text_path,
    ], check=True, capture_output=True)


def png_size(path):
    out = subprocess.run(["identify", "-format", "%w %h", path],
                        capture_output=True, text=True, check=True).stdout
    w, h = out.split()
    return int(w), int(h)


def validate(valid):
    """Warn about any sheet row whose live keys are unknown; return counts."""
    checked = missing = 0
    for _, rows in SHEET:
        for key, _label, expansion in rows:
            targets = expansion if expansion else [key]
            for t in targets:
                checked += 1
                if t not in valid:
                    missing += 1
                    print(f"  ! 实时绑定中不存在: {key} -> {t}", file=sys.stderr)
    return checked, missing


def balanced_columns():
    """Split SHEET groups into NCOL contiguous columns, minimising the tallest."""
    blocks = [(g, len(r) + 1) for g, r in SHEET]
    n, k = len(blocks), NCOL
    INF = float("inf")
    # dp[i][j] = (max_rows, sum_sq) for blocks[:i] split into j columns
    dp = {(0, 0): (0, 0)}
    choice = {}
    for j in range(1, k + 1):
        for i in range(1, n + 1):
            best = None
            for p in range(j - 1, i):
                prev = dp.get((p, j - 1))
                if prev is None:
                    continue
                rows = sum(c for _, c in blocks[p:i])
                cand = (max(prev[0], rows), prev[1] + rows * rows)
                if best is None or cand < best[0]:
                    best = (cand, p)
            if best:
                dp[(i, j)] = best[0]
                choice[(i, j)] = best[1]
    if (n, k) not in dp:
        return [SHEET]
    cols, i = [], n
    for j in range(k, 0, -1):
        p = choice[(i, j)]
        cols.append(SHEET[p:i])
        i = p
    return list(reversed(cols))


def build(font_size, label_cells):
    key_w = max(cells(k) for _, rows in SHEET for k, _, _ in rows)
    rows_per_col = max(sum(1 + len(r) for _, r in col) for col in balanced_columns())
    avail_h = H - TOP - BOTTOM
    pitch = avail_h / rows_per_col
    font_px = font_size * 4 / 3
    cols = []
    widest = 0.0
    for col in balanced_columns():
        lines = []
        for group, rows in col:
            lines.append(f'<span font_desc="{FONT_BOLD} {font_size}" '
                        f'foreground="{HEAD}">{group}</span>')
            for key, label, _ in rows:
                while cells(label) > label_cells:
                    label = label[:-1]
                pad = " " * max(0, round((key_w - cells(key)) / 0.6))
                lines.append(f'<span foreground="{KEY}">{pad}{key}</span>  '
                            f'<span foreground="{LABEL}">{label}</span>')
                widest = max(widest, key_w + 1.2 + cells(label))
        cols.append(lines)
    return cols, widest * font_px, pitch, font_px


def choose_layout():
    for size in (13, 12, 11, 10, 9):
        cols, col_w, pitch, font_px = build(size, 20.0)
        total = col_w * len(cols) + GAP * (len(cols) - 1)
        leading_ok = pitch - font_px >= 4.0
        if total <= W - 2 * MARGIN_X and pitch >= font_px * 1.15 and leading_ok:
            return size, cols, col_w, total, pitch, font_px
    return size, cols, col_w, total, pitch, font_px


def main():
    args = sys.argv[1:]
    install = "--install" in args
    out_path = None
    for i, a in enumerate(args):
        if a == "--output" and i + 1 < len(args):
            out_path = args[i + 1]
    live = live_bindings()
    valid = {k for k, _ in live}
    print(f"实时绑定 {len(live)} 条 / {len(valid)} 个唯一键")
    checked, missing = validate(valid)
    print(f"校验 {checked} 个键位引用，缺失 {missing}")

    size, cols, col_w, total, pitch, font_px = choose_layout()
    print(f"字号 {size}pt ({font_px:.0f}px) · {len(cols)} 列 · 列宽 ~{col_w:.0f}px · "
          f"行距 {pitch:.1f}px")
    if total > W - 2 * MARGIN_X:
        print(f"  ! 内容总宽 {total:.0f}px 超出可用宽度", file=sys.stderr)

    tmp = tempfile.mkdtemp(prefix="kbwall-")
    try:
        probe = os.path.join(tmp, "probe.txt")
        with open(probe, "w") as f:
            f.write("\n".join(cols[0][:4]))
        probe_png = os.path.join(tmp, "probe.png")
        render(probe, probe_png, 1.0)
        _, ph = png_size(probe_png)
        factor = max(0.8, pitch / (ph / 4))
        print(f"  自然行高 {ph / 4:.1f}px -> line-spacing {factor:.3f}")

        col_pngs = []
        for i, lines in enumerate(cols):
            txt = os.path.join(tmp, f"col{i}.txt")
            png = os.path.join(tmp, f"col{i}.png")
            with open(txt, "w") as f:
                f.write("\n".join(lines))
            render(txt, png, factor)
            col_pngs.append(png)

        widths = [png_size(p)[0] for p in col_pngs]
        real_total = sum(widths) + GAP * (len(widths) - 1)
        x = max(MARGIN_X, (W - real_total) // 2)
        canvas = os.path.join(tmp, "canvas.png")
        cmd = ["magick", "-size", f"{W}x{H}", f"xc:{BG}",
               "-fill", ACCENT, "-draw", f"rectangle 0,0 {W},4"]
        for p, w in zip(col_pngs, widths):
            cmd += [p, "-geometry", f"+{x}+{TOP}", "-composite"]
            x += w + GAP
        cmd.append(canvas)
        subprocess.run(cmd, check=True)

        title = os.path.join(tmp, "title.txt")
        with open(title, "w") as f:
            f.write(f'<span font_desc="{FONT_BOLD} 34" foreground="{FG}">OMARCHY</span>'
                    f'<span font_desc="{FONT_BOLD} 34" foreground="{KEY}"> KEYBINDINGS</span>\n'
                    f'<span font_desc="{FONT} 14" foreground="{DIM}">'
                    f'本机实时生效绑定 · {len(live)} 条 · Super / Cmd 键 · '
                    f'与本机 bindings.lua 一致</span>')
        title_png = os.path.join(tmp, "title.png")
        render(title, title_png, 1.25)

        foot = os.path.join(tmp, "foot.txt")
        with open(foot, "w") as f:
            f.write(f'<span font_desc="{FONT} 12" foreground="{DIM}">'
                    f'完整实时键位表:  Super + K      自定义绑定:  ~/.config/hypr/bindings.lua'
                    f'</span>')
        foot_png = os.path.join(tmp, "foot.png")
        render(foot, foot_png, 1.0)
        fw, fh = png_size(foot_png)

        out = os.path.abspath(out_path or DEFAULT_OUTPUT)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run([
            "magick", canvas,
            title_png, "-geometry", f"+{MARGIN_X}+34", "-composite",
            foot_png, "-geometry", f"+{(W - fw) // 2}+{H - fh - 16}", "-composite",
            "-strip", "-quality", "95", out,
        ], check=True)
        print(f"生成: {out}  {png_size(out)[0]}x{png_size(out)[1]}  "
              f"{os.path.getsize(out) / 1024:.0f} KB")

        if install:
            theme = open(os.path.expanduser(
                "~/.local/state/omarchy/current/theme.name")).read().strip()
            dest_dir = os.path.expanduser(f"~/.config/omarchy/backgrounds/{theme}")
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, "keybindings.png")
            shutil.copy2(out, dest)
            print(f"已安装: {dest}")
            subprocess.run(["omarchy", "theme", "bg", "set", dest], check=True)
            print("已应用为当前壁纸")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
