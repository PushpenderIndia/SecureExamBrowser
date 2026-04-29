from __future__ import annotations

from typing import List

from .models import ProhibitedProcess

_BROWSER_DESC = (
    "This stops video conferencing and screen sharing, "
    "without having to quit the browser."
)

_MACOS_PROCESSES: List[ProhibitedProcess] = [
    ProhibitedProcess("Adium", "com.adiumX.adiumX", True, False),
    ProhibitedProcess("Alfred*", "com.runningwithcrayons.Alfred*", True, False),
    ProhibitedProcess("AnyDesk", "com.philandro.anydesk", True, True),
    ProhibitedProcess("AnyGPT", "me.tanmay.AnyGPT", False, True),
    ProhibitedProcess("Brave Browser Helper", "", True, True, description=_BROWSER_DESC),
    ProhibitedProcess("Camtasia*", "com.techsmith.camtasia*", True, False),
    ProhibitedProcess("Chicken", "com.geekspiff.chickenofthevnc", True, False),
    ProhibitedProcess("Chicken", "net.sourceforge.chicken", True, False),
    ProhibitedProcess(
        "Chrome Remote Desktop Host",
        "com.google.chrome.remote_desktop.native-messaging-host",
        True, True,
    ),
    ProhibitedProcess("Chromium Helper", "", True, True, description=_BROWSER_DESC),
    ProhibitedProcess(
        "DataDetectorsViewService", "com.apple.DataDetectorsViewService", False, True,
    ),
    ProhibitedProcess("Discord", "com.hnc.Discord*", True, False),
    ProhibitedProcess("Discord Lite", "com.dosdude1.Discord-Lite", True, False),
    ProhibitedProcess("Element (Riot)", "im.riot.app", True, False),
    ProhibitedProcess("FaceTime", "com.apple.FaceTime", True, False),
    ProhibitedProcess(
        "plugin-container", "org.mozilla.plugincontainer", True, True,
        description=(
            "Firefox: This stops video conferencing and screen sharing, "
            "without having to quit the browser. Users have to restore "
            "their open tabs afterwards though."
        ),
    ),
    ProhibitedProcess("Google Chrome Helper", "", True, True, description=_BROWSER_DESC),
    ProhibitedProcess("GoToMeeting", "com.logmein.GoToMeeting", True, False),
    ProhibitedProcess("Guilded", "com.electron.guilded", True, False),
    ProhibitedProcess("Join.me", "com.logmein.join.me", True, False),
    ProhibitedProcess(
        "Keyboard Viewer (Assistive Control)",
        "com.apple.inputmethod.AssistiveControl",
        False, True,
    ),
    ProhibitedProcess("Messages", "com.apple.iChat", True, False),
    ProhibitedProcess("Messages", "com.apple.MobileSMS", True, False),
    ProhibitedProcess("Microsoft Communicator", "com.microsoft.Communicator", True, False),
    ProhibitedProcess("Microsoft Edge Helper", "", True, True, description=_BROWSER_DESC),
    ProhibitedProcess("Microsoft Lync", "com.microsoft.Lync", True, False),
    ProhibitedProcess("MSTeams", "com.microsoft.teams2", True, False),
    ProhibitedProcess("Opera Helper", "", True, True, description=_BROWSER_DESC),
    ProhibitedProcess(
        "Safari/WebKit Networking", "com.apple.WebKit.Networking", True, True,
        description=_BROWSER_DESC,
    ),
    ProhibitedProcess("Screenconnect", "com.elsitech.screenconnect.client", True, False),
    ProhibitedProcess("Skype", "com.skype.skype", True, False),
    ProhibitedProcess("Skype for Business", "com.microsoft.SkypeForBusiness", True, False),
    ProhibitedProcess("Slack", "com.tinyspeck.slackmacgap", True, False),
    ProhibitedProcess("SolsticeClient", "com.mersive.solstice.client", True, False),
    ProhibitedProcess("Swiftcord", "io.cryptoalgo.swiftcord", True, False),
    ProhibitedProcess("Teams", "com.microsoft.teams", True, False),
    ProhibitedProcess("TeamViewer", "com.teamviewer.TeamViewer", True, False),
    ProhibitedProcess("TeamViewer", "com.TeamViewer.TeamViewer", True, False),
    ProhibitedProcess("Telegram", "ru.keepcoder.Telegram", True, False),
    ProhibitedProcess("Universal Control", "com.apple.universalcontrol", True, True),
    ProhibitedProcess("Vivaldi Helper", "", True, True, description=_BROWSER_DESC),
    ProhibitedProcess("VLC", "org.videolan.vlc", True, False),
    ProhibitedProcess(
        "vncserver", "", True, False,
        description="The user will have to deactivate/uninstall RealVNC server to use SEB.",
    ),
    ProhibitedProcess("Voxa", "lol.peril.voxa", True, False),
    ProhibitedProcess("webexmta", "com.cisco.webex.webexmta", True, False),
    ProhibitedProcess("zoom.us", "us.zoom.xos", True, False),
]

_WINDOWS_EXECUTABLES = [
    "AA_v3.exe", "AeroAdmin.exe", "beamyourscreen-host.exe",
    "CamPlay.exe", "Camtasia.exe", "CamtasiaStudio.exe",
    "Camtasia_Studio.exe", "CamRecorder.exe", "CamtasiaUtl.exe",
    "chromoting.exe", "CiscoCollabHost.exe", "CiscoWebExStart.exe",
    "Discord.exe", "DiscordPTB.exe", "DiscordCanary.exe",
    "Element.exe", "g2mcomm.exe", "g2mlauncher.exe", "g2mstart.exe",
    "GotoMeetingWinStore.exe", "Guilded.exe",
    "join.me.exe", "join.me.sentinel.exe",
    "Microsoft.Media.player.exe", "Mikogo-host.exe", "MS-teams.exe",
    "obs32.exe", "obs64.exe", "pcmontask.exe", "ptoneclk.exe",
    "RemotePCDesktop.exe", "remoting_host.exe",
    "RPCService.exe", "RPCSuite.exe", "sethc.exe",
    "Skype.exe", "SkypeApp.exe", "SkypeHost.exe",
    "slack.exe", "spotify.exe", "SRServer.exe", "strwinclt.exe",
    "Teams.exe", "TeamViewer.exe", "Telegram.exe",
    "VLC.exe", "vncserver.exe", "vncviewer.exe", "vncserverui.exe",
    "webexmta.exe", "Zoom.exe",
]

_MACOS_EXTRA_PROCESSES: List[ProhibitedProcess] = [
    ProhibitedProcess("AutoFill", "com.apple.AutoFillPanelService", True, True),
    ProhibitedProcess("Chrome", "com.google.chrome", True, False),
    ProhibitedProcess("iTerm2", "com.googlecode.iterm2", False, False),
    ProhibitedProcess("Terminal", "com.apple.Terminal", False, False),
]


def build_prohibited_processes() -> List[ProhibitedProcess]:
    """Return the full 101-entry prohibited process list (macOS + Windows)."""
    procs = list(_MACOS_PROCESSES)
    for exe in _WINDOWS_EXECUTABLES:
        procs.append(
            ProhibitedProcess(
                exe, "", True, False,
                os_type=1, current_user=True, original_name=exe,
            )
        )
    procs.extend(_MACOS_EXTRA_PROCESSES)
    return procs
