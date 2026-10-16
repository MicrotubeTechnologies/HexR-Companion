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
    "by Microtube Technologies": "Microtube Technologies 出品",
    "Test": "测试",
    "Headsets": "头显",
    "Quick test": "快速测试",
    "Gloves": "手套",
    "app {version}": "版本 {version}",
    "Help & docs": "帮助与文档",
    "no glove": "无手套",
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
    "connected": "已连接",
    "not connected": "未连接",
    "Disconnect": "断开连接",
    "Error: {error}": "错误：{error}",
    "battery {level}": "电量 {level}",
    "Stop": "停止",

    # -- connecting a glove
    "Connect a HEXR glove": "连接 HEXR 手套",
    "Power on the arm module and press scan. Left and right are separate devices — connect "
    "either, or both. Testing starts as soon as one connects.":
        "打开臂部模块的电源，然后点击扫描。左右手套是两个独立的设备——可以只连一只，也可以两只都连。"
        "连上一只就会开始测试。",
    "Connect the other glove, check battery and pressure, or disconnect.":
        "连接另一只手套、查看电量和压力，或断开连接。",
    "Scan for HEXR": "扫描 HEXR",
    "Scan for gloves": "扫描手套",
    "Bluetooth ready": "蓝牙已就绪",
    "No gloves yet. Press scan with the arm module switched on.":
        "还没有手套。请先打开臂部模块，再点击扫描。",
    "Device": "设备",
    "Hand": "手",
    "Address": "地址",
    "Signal": "信号",
    "Listening for gloves…": "正在搜索手套…",
    "Found {n}": "找到 {n} 只",
    "Bluetooth unavailable — {error}": "蓝牙不可用——{error}",
    "Nothing found. Is the arm module switched on?": "未找到手套。臂部模块打开了吗？",
    "Connected · streaming": "已连接 · 正在传输数据",

    # -- testing
    "Test the haptics": "测试触觉反馈",
    "Pick channels, set the strength, and trigger. Release vents them again — nothing switches "
    "itself off.":
        "选择通道、设定强度，然后点击触发。点击释放即可泄压——通道不会自行关闭。",
    "Channels": "通道",
    "None": "全不选",
    "Select all": "全选",
    "Mode": "模式",
    "Pressure": "压力",
    "steady squeeze": "持续挤压",
    "Vibration": "振动",
    "oscillating": "往复振荡",
    "Intensity": "强度",
    "Ramp speed": "加压速度",
    "Frequency": "频率",
    "Peak ratio": "峰值占比",
    "Under {hz} Hz the glove vibrates pneumatically — the pressure target is pulsed.":
        "低于 {hz} Hz 时，手套以气动方式振动——压力目标值按节拍脉动。",
    "At {hz} Hz and above the pressure loop is off and the channel's motor is driven directly.":
        "{hz} Hz 及以上时，压力闭环关闭，直接驱动该通道的电机。",
    "Trigger": "触发",
    "Release": "释放",
    "All off": "全部关闭",
    "Live from the glove": "手套实时数据",
    "No glove connected": "未连接手套",
    "no telemetry": "无遥测数据",
    "Battery": "电量",
    "Source": "气源",
    "This glove reports absolute pressure; readings are converted to gauge kPa.":
        "这只手套报告的是绝对压力，读数已换算为表压（kPa）。",

    # -- the quick test
    "Drives every channel to full for two seconds and reports what each one reached. Take the "
    "glove off first.":
        "将所有通道加压至满载并保持两秒，然后报告每个通道达到的压力。请先摘下手套。",
    "Glove to test": "待测手套",
    "Run quick test": "开始快速测试",
    "Channel": "通道",
    "Peak": "峰值",
    "Time to peak": "达峰时间",
    "Verdict": "结论",
    "Good": "良好",
    "Poor": "偏弱",
    "Fail": "失效",
    "Stopped": "已停止",
    "Connect a glove first": "请先连接手套",
    "That glove is not sending telemetry — nothing to measure":
        "这只手套没有发送遥测数据——无法测量",
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
    "{n} of 6 channels failed": "6 个通道中有 {n} 个失效",
    "Source reached {kpa} kPa, so supply is fine — a channel reading nothing with a healthy "
    "source is a blocked line, a valve that never opened, or a dead indenter. {breakdown}.":
        "气源达到 {kpa} kPa，供气正常——气源正常而通道没有读数，说明管路堵塞、阀门没有打开，"
        "或压头损坏。{breakdown}。",
    "{n} of 6 channels poor": "6 个通道中有 {n} 个偏弱",
    "Source reached {kpa} kPa. Every channel moved, but not all of them reached full pressure — "
    "check the tubing on the weak ones. {breakdown}.":
        "气源达到 {kpa} kPa。每个通道都有动作，但并非全部达到满压——请检查较弱通道的管路。"
        "{breakdown}。",
    "All 6 channels good": "6 个通道全部良好",
    "Source reached {kpa} kPa.": "气源达到 {kpa} kPa。",

    # -- headsets
    "Every HEXR headset on this network. Connect its gloves, change its scene and watch what "
    "the wearer sees, without taking the headset off them.":
        "此网络上的所有 HEXR 头显。无需让佩戴者摘下头显，就能连接其手套、切换场景，"
        "并观看佩戴者看到的画面。",
    "Add": "添加",
    "Headset address": "头显地址",
    "No headsets yet. Each one needs a HEXR app with HexR Remote running, on the same network "
    "as this computer. If one is running and still does not appear, Windows may be blocking it: "
    "allow HEXR Companion on private networks in Windows Security, make sure this network is set "
    "to Private, or type the headset's address above.":
        "还没有头显。每台头显都需要运行带有 HexR Remote 的 HEXR 应用，并与这台电脑处于同一网络。"
        "如果应用已在运行却仍未出现，可能是 Windows 阻止了它：请在 Windows 安全中心允许 "
        "HEXR Companion 访问专用网络，确认此网络已设为“专用”，或在上方输入头显的地址。",
    "Headset": "头显",
    "App · scene": "应用 · 场景",
    "State": "状态",
    "L": "左",
    "R": "右",
    "Open": "打开",
    "1 headset on this network": "此网络上有 1 台头显",
    "{n} headsets on this network": "此网络上有 {n} 台头显",
    "Listening for headsets…": "正在搜索头显…",
    "connecting": "连接中",
    "unreachable": "无法连接",
    "asleep": "休眠",
    "ready": "就绪",
    "Forget": "移除",
    "Save name": "保存名称",
    "Name": "名称",
    "headset {pct}%": "头显 {pct}%",
    "{n} controllers": "{n} 个手柄",
    "Not connected to this headset. Trying again…": "未连接到此头显，正在重试…",
    "Not connected to this headset right now.": "当前未连接到此头显。",
    "Nobody is wearing this headset, so it is asleep and refuses commands. Someone has to put "
    "it on first.":
        "此头显无人佩戴，处于休眠状态，不会执行命令。需要先有人戴上它。",
    "Gloves, through the headset": "手套（经由头显）",
    "Release all": "全部释放",
    "No glove handler in this app": "此应用没有手套处理程序",
    "This computer has a glove for this hand; disconnect it here first.":
        "这台电脑已连接这只手的手套，请先在这里断开。",
    "Scene": "场景",
    "Wearer": "佩戴者",
    "Recenter": "重新定位",
    "Recentered.": "已重新定位。",
    "Puts the wearer back on the scene's starting spot, facing its front.":
        "让佩戴者回到场景的起始位置，并面向场景正前方。",
    "This app cannot be recentered from here: it needs HexR 0.11.0 or newer, with Allow "
    "Recenter on.":
        "无法从这里重新定位此应用：它需要 HexR 0.11.0 或更高版本，并开启 Allow Recenter。",
    "View": "画面",
    "Watch": "观看",
    "Watch (shared now)": "观看（正在共享）",
    "Stop watching": "停止观看",
    "This app does not share its view.": "此应用不共享画面。",
    "Not shared. Watch asks the wearer to allow it in the headset.":
        "未共享。点击“观看”会请佩戴者在头显中允许共享。",
    "Waiting for the wearer to allow screen sharing in the headset…":
        "正在等待佩戴者在头显中允许屏幕共享…",
    "Shared · {w}×{h}": "正在共享 · {w}×{h}",
    " · {n} watching": " · {n} 人在看",
    "The wearer said no. Watch asks again.": "佩戴者拒绝了。点击“观看”可再次请求。",
    "This headset cannot share its view.": "此头显无法共享画面。",
    "Sharing failed.": "共享失败。",
    "Connecting to the view…": "正在连接画面…",
    "Cannot listen for headsets on UDP {port}: {error}": "无法在 UDP {port} 端口上搜索头显：{error}",
    "This build cannot show a headset's view: it was made without PyAV.":
        "此版本无法显示头显画面：构建时没有包含 PyAV。",
    "Could not reach the view: {error}": "无法连接到画面：{error}",
    "The view stopped: {error}": "画面已中断：{error}",
    "The view could not be decoded: {error}": "无法解码画面：{error}",
}
