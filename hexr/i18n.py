"""The app's two languages: English and Simplified Chinese.

English is written in the code as it always was, and is the key: `tr("Connect")` is the Chinese
for "Connect" when Chinese is picked, and "Connect" otherwise. A string with no translation still
shows, in English, rather than going blank; tests/test_i18n.py fails until every one has one.

Values go in as keyword arguments, `tr("Found {n}", n=3)`, never into the key with an f-string,
so the key stays the same text the table holds.

What the headset itself sends (an app's scene and command names, its error messages) arrives as
the app wrote it and is shown as it is.
"""

from __future__ import annotations

import locale
import sys

from . import settings

LANGUAGES = (("en", "English"), ("zh", "中文"))

_FILE = "settings.json"


def _system_language() -> str:
    """Chinese on a computer set up in Chinese, English anywhere else."""
    if sys.platform == "win32":
        try:
            import ctypes
            return "zh" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x04 \
                else "en"
        except Exception:
            pass
    try:
        code = locale.getlocale()[0] or ""
    except ValueError:
        code = ""
    return "zh" if code.lower().startswith(("zh", "chinese")) else "en"


def _initial() -> str:
    code = settings.load(_FILE).get("language")
    return code if code in dict(LANGUAGES) else _system_language()


_lang = _initial()


def language() -> str:
    return _lang


def set_language(code: str):
    """Switch, and remember the choice for the next run."""
    global _lang
    if code not in dict(LANGUAGES):
        return
    _lang = code
    data = settings.load(_FILE)
    data["language"] = code
    settings.save(_FILE, data)


def N_(text: str) -> str:
    """Marks English to translate where it is written down before the language
    is known (a screen's title, a table of labels); `tr()` translates it where
    it is shown."""
    return text


def tr(text: str, **values) -> str:
    if _lang == "zh" and text in ZH:
        # Tk wraps a line at its last space, and only between characters where there is none.
        # Chinese can break between any two characters, so one space early in a sentence ("所有
        # HEXR 头显") would end the line there; non-breaking spaces leave Tk to break it the
        # Chinese way. Only the template: values filled in keep their own spaces.
        text = ZH[text].replace(" ", " ")
    return text.format(**values) if values else text


# Simplified Chinese. Kept in the order a person meets the strings: the chrome, then each screen.
ZH: dict[str, str] = {
    # -- the window
    "Test": "测试",
    "Headsets": "头显",
    "Quick test": "快速测试",
    "Gloves": "手套",
    "Close": "关闭",

    # -- gloves, wherever they appear
    "Left": "左手",
    "Right": "右手",
    "{hand} glove": "{hand}手套",
    "Thumb": "拇指",
    "Index": "食指",
    "Middle": "中指",
    "Ring": "无名指",
    "Pinky": "小指",
    "Palm": "手掌",
    "Connect": "连接",
    "Connecting…": "正在连接…",
    "Connected": "已连接",
    "Not connected": "未连接",
    "Disconnect": "断开连接",
    "battery {level}": "电量 {level}",
    "Stop": "停止",

    # -- connecting a glove
    "Bluetooth unavailable — {error}": "蓝牙不可用——{error}",

    # -- testing
    "None": "全不选",
    "Pressure": "压力",
    "Vibration": "振动",
    "Intensity": "强度",
    "Ramp speed": "加压速度",
    "Frequency": "频率",
    "Peak ratio": "峰值占比",
    "Under {hz} Hz the glove vibrates pneumatically — the pressure target is pulsed.":
        "低于 {hz} Hz 时，手套以气动方式振动——压力目标值按节拍脉动。",
    "At {hz} Hz and above the pressure loop is off and the channel's motor is driven directly.":
        "{hz} Hz 及以上时，压力闭环关闭，直接驱动该通道的电机。",
    "no telemetry": "无遥测数据",
    "This glove reports absolute pressure; readings are converted to gauge kPa.":
        "这只手套报告的是绝对压力，读数已换算为表压（kPa）。",

    # -- the quick test
    "Channel": "通道",
    "Peak": "峰值",
    "Time to peak": "达峰时间",
    "Verdict": "结论",
    "Good": "良好",
    "Poor": "偏弱",
    "Fail": "失效",
    "Stopped": "已停止",
    "Connect a glove first": "请先连接手套",
    "Venting…": "正在泄压…",
    "Glove disconnected": "手套已断开",
    "Driving all channels…": "正在驱动所有通道…",
    "{good} good, {poor} poor, {failed} failed":
        "{good} 个良好，{poor} 个偏弱，{failed} 个失效",
    "Pump failed": "气泵故障",
    "The source never rose above {kpa} kPa, so no channel could have reached pressure. This is "
    "one fault in the pump or its supply, not six failed channels.":
        "气源压力始终没有超过 {kpa} kPa，所以没有任何通道能够达到压力。这是气泵或其供气的一处故障，"
        "而不是六个通道都坏了。",
    "Source reached {kpa} kPa, so supply is fine — a channel reading nothing with a healthy "
    "source is a blocked line, a valve that never opened, or a dead indenter. {breakdown}.":
        "气源达到 {kpa} kPa，供气正常——气源正常而通道没有读数，说明管路堵塞、阀门没有打开，"
        "或压头损坏。{breakdown}。",
    "Source reached {kpa} kPa. Every channel moved, but not all of them reached full pressure — "
    "check the tubing on the weak ones. {breakdown}.":
        "气源达到 {kpa} kPa。每个通道都有动作，但并非全部达到满压——请检查较弱通道的管路。"
        "{breakdown}。",
    "Source reached {kpa} kPa.": "气源达到 {kpa} kPa。",

    # -- headsets
    "Add": "添加",
    "Headset": "头显",
    "State": "状态",
    "L": "左",
    "R": "右",
    "Open": "打开",
    "connecting": "连接中",
    "unreachable": "无法连接",
    "asleep": "休眠",
    "ready": "就绪",
    "Forget": "移除",
    "headset {pct}%": "头显 {pct}%",
    "{n} controllers": "{n} 个手柄",
    "Not connected to this headset right now.": "当前未连接到此头显。",
    "Release all": "全部释放",
    "No glove handler in this app": "此应用没有手套处理程序",
    "This computer has a glove for this hand; disconnect it here first.":
        "这台电脑已连接这只手的手套，请先在这里断开。",
    "Scene": "场景",
    "Recenter": "重新定位",
    "View": "画面",
    "Watch": "观看",
    "Stop watching": "停止观看",
    "This app does not share its view.": "此应用不共享画面。",
    "Shared · {w}×{h}": "正在共享 · {w}×{h}",
    " · {n} watching": " · {n} 人在看",
    "This headset cannot share its view.": "此头显无法共享画面。",
    "Sharing failed.": "共享失败。",
    "Connecting to the view…": "正在连接画面…",
    "Record": "录制",
    "Full screen": "全屏",
    "Frame": "画幅",
    "Square": "方形",
    "Glove": "手套",
    "On": "开",
    "Off": "关",
    "Size": "大小",
    "Small": "小",
    "Medium": "中",
    "Large": "大",
    "Drag the picture up or down to frame it.": "上下拖动画面即可调整取景。",
    "Show in folder": "在文件夹中显示",
    "The glove could not be drawn: {error}": "无法绘制手套：{error}",
    "The glove shows the pressure the gloves measure. Update this app to HexR 0.10.2 or newer to "
    "show every touch and vibration as it is sent.":
        "手套显示的是手套测得的压力。将此应用更新到 HexR 0.10.2 或更高版本，"
        "即可实时显示每一次触碰和振动。",
    "REC {time}": "录制 {time}",
    "Saved {name}": "已保存 {name}",
    " · {n} frames dropped": " · 丢失 {n} 帧",
    "Recording failed: {error}": "录制失败：{error}",
    "No frames arrived while recording.": "录制期间没有收到画面。",
    "This build has no video encoder.": "此版本没有视频编码器。",
    "Esc to leave full screen · R to record · G for the glove · drag to frame":
        "Esc 退出全屏 · R 录制 · G 显示或隐藏手套 · 拖动调整取景",
    "Cannot listen for headsets on UDP {port}: {error}": "无法在 UDP {port} 端口上搜索头显：{error}",
    "This build cannot show a headset's view: it was made without PyAV.":
        "此版本无法显示头显画面：构建时没有包含 PyAV。",
    "Could not reach the view: {error}": "无法连接到画面：{error}",
    "The view stopped: {error}": "画面已中断：{error}",
    "The view could not be decoded: {error}": "无法解码画面：{error}",

    # -- the simpler screens
    "Help": "帮助",
    "Details": "详情",
    "Connect a glove": "连接手套",
    "Switch on the arm module.": "请打开臂部模块。",
    "Searching": "正在搜索",
    "Found": "已找到",
    "Could not connect": "无法连接",
    "Bluetooth unavailable": "蓝牙不可用",
    "Try again": "重试",
    "Tap a finger": "点按手指",
    "All": "全选",
    "Hold to feel": "按住感受",
    "Keep on": "保持开启",
    "Fine-tune": "微调",
    "Pulse": "脉冲",
    "Buzz": "嗡振",
    "Source {kpa} kPa": "气源 {kpa} kPa",
    "Take the glove off first.": "请先摘下手套。",
    "Run": "开始",
    "Run again": "再测一次",
    "All good": "全部良好",
    "{n} poor": "{n} 个偏弱",
    "{n} failed": "{n} 个失效",
    "No readings from this glove": "这只手套没有读数",
    "Searching for headsets": "正在搜索头显",
    "Same Wi-Fi as this computer.": "与本电脑连接同一 Wi-Fi。",
    "Add by address": "按地址添加",
    "App": "应用",
    "Rename": "重命名",
    "Offline": "离线",
    "Reconnecting…": "正在重新连接…",
    "Asleep": "休眠中",
    "Asleep. Put the headset on.": "休眠中，请戴上头显。",
    "Live": "直播中",
    "Waiting": "等待中",
    "Waiting for the wearer…": "正在等待佩戴者…",
    "Declined": "已拒绝",
    "The wearer said no.": "佩戴者拒绝了。",
    "No view": "无画面",
    "Failed": "失败",
    "Watch asks the wearer to share.": "点击“观看”会请佩戴者共享画面。",
    "Saving…": "正在保存…",
    "Needs HexR 0.11.0 with Allow Recenter.": "需要 HexR 0.11.0 并开启 Allow Recenter。",
}
