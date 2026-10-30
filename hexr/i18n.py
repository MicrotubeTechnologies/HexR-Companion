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
    "Find gloves": "查找手套",
    "Gloves found": "已找到的手套",
    "Update this app to HexR 0.10.6 or later to pick gloves.":
        "请将此应用更新到 HexR 0.10.6 或更高版本，才能选择手套。",
    "Any glove": "任意手套",
    "Looking for gloves…": "正在查找手套…",
    "Double-click to rename": "双击重命名",
    "Sound on": "声音：开",
    "Sound off": "声音：关",
    "This computer cannot play sound: {error}": "本电脑无法播放声音：{error}",
    "The headset's sound, played here while you watch. It needs the app's Share Sound on.":
        "观看时在本电脑上播放头显的声音。需要应用开启 Share Sound。",
    "Searching…": "正在查找…",
    "No gloves found. Switch them on, and disconnect them from other headsets.":
        "未找到手套。请打开手套，并从其他头显上断开连接。",

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
    "Trigger all": "全部触发",
    "Presses every finger and the palm for a second, to check the gloves work.":
        "所有手指和手掌按压一秒，用来检查手套是否正常工作。",
    "Needs HexR 0.10.6.": "需要 HexR 0.10.6。",
    "No glove handler in this app": "此应用没有手套处理程序",
    "This computer has a glove for this hand; disconnect it here first.":
        "这台电脑已连接这只手的手套，请先在这里断开。",
    "Recenter": "重新定位",
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
    "Off": "关",
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
    "Cannot listen for headsets on UDP {port}: {error}": "无法在 UDP {port} 端口上搜索头显：{error}",
    "This build cannot show a headset's view: it was made without PyAV.":
        "此版本无法显示头显画面：构建时没有包含 PyAV。",
    "Could not reach the view: {error}": "无法连接到画面：{error}",
    "The view stopped: {error}": "画面已中断：{error}",
    "The view could not be decoded: {error}": "无法解码画面：{error}",
    "Could not reach the sound: {error}": "无法连接到声音：{error}",
    "The sound stopped: {error}": "声音已中断：{error}",
    "The sound could not be decoded: {error}": "无法解码声音：{error}",
    "Sound shared": "正在共享声音",
    "This app sends no sound. Update it to HexR 0.10.5 or newer to record its sound.":
        "此应用不发送声音。将其更新到 HexR 0.10.5 或更高版本，即可录制声音。",

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
    "All": "全选",
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
    "Needs HexR 0.10.6 with Allow Recenter.": "需要 HexR 0.10.6 并开启 Allow Recenter。",

    # -- recordings, and the gloves beside the view
    "Esc to leave full screen · R to record": "按 Esc 退出全屏 · 按 R 录制",
    "Open in Recordings": "在录像中打开",
    "Click to disconnect": "点击断开",
    "Click to connect": "点击连接",
    "Double-click for full screen": "双击全屏",
    "Loading…": "加载中…",
    "Export failed: {error}": "导出失败：{error}",
    "Exporting… {pct}%": "正在导出… {pct}%",
    "Export again": "再次导出",
    "Export": "导出",
    "Exported · Show in folder": "已导出 · 在文件夹中显示",
    "Landscape": "横屏",
    "Portrait": "竖屏",
    "Recordings": "录像",
    "Open folder": "打开文件夹",
    "No recordings yet": "还没有录像",
    "Record a headset's view in Headsets.": '在“头显”中录制头显画面。',
    "Go to Headsets": "前往头显",
    "View only": "仅画面",
    "Exporting {shape}… {pct}%": "正在导出{shape}… {pct}%",
    "Exporting another recording… {pct}%": "正在导出另一段录像… {pct}%",
    "Air supply": "气源",
    "No readings": "无读数",
    "Set to": "设定",
    "Now": "当前",
    "Trigger": "触发",
    "Pick a finger": "选择手指",

    # -- APK sideload. What the headset itself shows (Allow, Unknown Sources) is given in English
    # too: a headset is often set up in English whatever the computer's language.
    "APK Sideload": "APK 侧载",
    "APK": "APK",
    "Install": "安装",
    "Plug in the headset": "插上头显",
    "Use a USB-C cable.": "使用 USB-C 数据线。",
    "Looking for a headset": "正在查找头显",
    "Not showing up?": "没有出现？",
    "Turn on Developer Mode in the Meta Horizon phone app.":
        "在 Meta Horizon 手机应用中开启开发者模式（Developer Mode）。",
    "Use a cable that carries data. Some only charge.": "使用能传输数据的线，有些线只能充电。",
    "Put the headset on and choose Allow.": "戴上头显，选择“允许”（Allow）。",
    "If the Mac asks to allow the accessory, choose Allow.": "如果 Mac 询问是否允许配件连接，请选择“允许”。",
    "Install Meta's Quest ADB driver.": "安装 Meta 的 Quest ADB 驱动程序。",
    "Pick a headset": "选择一台头显",
    "Ready": "就绪",
    "Put on the headset and choose Allow": "请戴上头显并选择“允许”（Allow）",
    "Tick Always allow from this computer.": "勾选“始终允许这台电脑”（Always allow from this computer）。",
    "Waiting for the headset…": "正在等待头显…",
    "Not responding. Unplug it and plug it in again.": "没有响应。请拔下后重新插入。",
    "adb is missing from this build, and none was found on this computer.":
        "此版本缺少 adb，这台电脑上也没有找到 adb。",
    "adb would not run: {error}": "adb 无法运行：{error}",
    "Choose the APK": "选择 APK",
    "Choose APK…": "选择 APK…",
    "Choose an APK": "选择 APK 文件",
    "Android app": "Android 应用",
    "All files": "所有文件",
    "Install on {name}": "安装到 {name}",
    "Change APK…": "更换 APK…",
    "Other headset": "其他头显",
    "Removing the old copy…": "正在卸载旧版本…",
    "Installing… {time}": "正在安装… {time}",
    "Installed": "已安装",
    "Find it in Library → Unknown Sources.": "在应用库（Library）→“未知来源”（Unknown Sources）中可以找到。",
    "Next headset? Plug it in.": "下一台头显？直接插上即可。",
    "A different build is on {name}. Uninstall it first? Its saved data will be lost.":
        "{name} 上有签名不同的版本。要先卸载吗？它保存的数据会丢失。",
    "A different build is on {name}. Uninstall it in the headset first.":
        "{name} 上有签名不同的版本。请先在头显中卸载它。",
    "Uninstall and install": "卸载后安装",
    "{name} has a newer version.": "{name} 上已有较新的版本。",
    "Install older version": "安装旧版本",
    "{name} is full. Free up space and try again.": "{name} 存储空间已满。请清理空间后重试。",
    "This app needs a newer headset system. Update {name} first.":
        "此应用需要更新的头显系统。请先更新 {name}。",
    "This APK is not made for this headset.": "此 APK 不适用于这台头显。",
    "This file is not a working APK.": "此文件不是有效的 APK。",
    "The APK has moved. Choose it again.": "APK 已被移动，请重新选择。",
    "{name} disconnected. Plug it in and try again.": "{name} 已断开。请重新连接后重试。",
    "Install failed: {error}": "安装失败：{error}",
}
