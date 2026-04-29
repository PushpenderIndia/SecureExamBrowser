from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProhibitedProcess:
    executable: str
    identifier: str
    ignore_in_aac: bool
    strong_kill: bool
    os_type: int = 0        # 0 = macOS, 1 = Windows
    active: bool = True
    current_user: bool = False
    description: str = ""
    allowed_executables: str = ""
    original_name: str = ""
    user: str = ""
    window_handling_process: str = ""

    def to_dict(self) -> dict:
        return {
            "active": self.active,
            "allowedExecutables": self.allowed_executables,
            "currentUser": self.current_user,
            "description": self.description,
            "executable": self.executable,
            "identifier": self.identifier,
            "ignoreInAAC": self.ignore_in_aac,
            "originalName": self.original_name,
            "os": self.os_type,
            "strongKill": self.strong_kill,
            "user": self.user,
            "windowHandlingProcess": self.window_handling_process,
        }


class ProxyConfig:
    def __init__(self) -> None:
        self.auto_config_enabled = False
        self.auto_config_js = ""
        self.auto_config_url = ""
        self.auto_discovery_enabled = False
        self.exceptions_list: list = []
        self.exclude_simple_hostnames = False
        self.ftp_enable = False
        self.ftp_passive = True
        self.ftp_password = ""
        self.ftp_port = 21
        self.ftp_proxy = ""
        self.ftp_requires_password = False
        self.ftp_username = ""
        self.http_enable = False
        self.http_password = ""
        self.http_port = 80
        self.http_proxy = ""
        self.http_requires_password = False
        self.http_username = ""
        self.https_enable = False
        self.https_password = ""
        self.https_port = 443
        self.https_proxy = ""
        self.https_requires_password = False
        self.https_username = ""
        self.rtsp_enable = False
        self.rtsp_password = ""
        self.rtsp_port = 554
        self.rtsp_proxy = ""
        self.rtsp_requires_password = False
        self.rtsp_username = ""
        self.socks_enable = False
        self.socks_password = ""
        self.socks_port = 1080
        self.socks_proxy = ""
        self.socks_requires_password = False
        self.socks_username = ""

    def to_dict(self) -> dict:
        return {
            "AutoConfigurationEnabled": self.auto_config_enabled,
            "AutoConfigurationJavaScript": self.auto_config_js,
            "AutoConfigurationURL": self.auto_config_url,
            "AutoDiscoveryEnabled": self.auto_discovery_enabled,
            "ExceptionsList": self.exceptions_list,
            "ExcludeSimpleHostnames": self.exclude_simple_hostnames,
            "FTPEnable": self.ftp_enable,
            "FTPPassive": self.ftp_passive,
            "FTPPassword": self.ftp_password,
            "FTPPort": self.ftp_port,
            "FTPProxy": self.ftp_proxy,
            "FTPRequiresPassword": self.ftp_requires_password,
            "FTPUsername": self.ftp_username,
            "HTTPEnable": self.http_enable,
            "HTTPPassword": self.http_password,
            "HTTPPort": self.http_port,
            "HTTPProxy": self.http_proxy,
            "HTTPRequiresPassword": self.http_requires_password,
            "HTTPSEnable": self.https_enable,
            "HTTPSPassword": self.https_password,
            "HTTPSPort": self.https_port,
            "HTTPSProxy": self.https_proxy,
            "HTTPSRequiresPassword": self.https_requires_password,
            "HTTPSUsername": self.https_username,
            "HTTPUsername": self.http_username,
            "RTSPEnable": self.rtsp_enable,
            "RTSPPassword": self.rtsp_password,
            "RTSPPort": self.rtsp_port,
            "RTSPProxy": self.rtsp_proxy,
            "RTSPRequiresPassword": self.rtsp_requires_password,
            "RTSPUsername": self.rtsp_username,
            "SOCKSEnable": self.socks_enable,
            "SOCKSPassword": self.socks_password,
            "SOCKSPort": self.socks_port,
            "SOCKSProxy": self.socks_proxy,
            "SOCKSRequiresPassword": self.socks_requires_password,
            "SOCKSUsername": self.socks_username,
        }


class SEBServerConfig:
    def __init__(self) -> None:
        self.api_discovery = ""
        self.client_name = ""
        self.client_secret = ""
        self.institution = ""
        self.ping_interval = 1000

    def to_dict(self) -> dict:
        return {
            "apiDiscovery": self.api_discovery,
            "clientName": self.client_name,
            "clientSecret": self.client_secret,
            "institution": self.institution,
            "pingInterval": self.ping_interval,
        }
