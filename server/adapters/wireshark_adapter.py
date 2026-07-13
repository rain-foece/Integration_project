"""Wireshark 适配器（纯 Python 实现）。

基于 scapy 库解析 PCAP 网络流量文件，无需外部可执行文件。
"""

import os
import time
from collections import Counter
from pathlib import Path

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# 尝试导入 scapy
_SCAPY_AVAILABLE = False
_SCAPY_IMPORT_ERROR = ""
try:
    from scapy.all import rdpcap, Packet, IP, TCP, UDP, ICMP, DNS, HTTP, Ether, IPv6, Raw
    from scapy.layers.http import HTTPRequest, HTTPResponse
    _SCAPY_AVAILABLE = True
except ImportError as e:
    _SCAPY_IMPORT_ERROR = str(e)
    # 尝试单独导入各层
    try:
        from scapy.all import rdpcap, Packet, IP, TCP, UDP, ICMP, Raw
        from scapy.all import Ether, IPv6
        _SCAPY_AVAILABLE = True
    except ImportError:
        pass


class WiresharkAdapter(BaseToolAdapter):
    """PCAP 网络流量分析适配器（纯 Python）。"""

    VALID_ACTIONS = ("pcap_summary", "pcap_parse", "protocol_stats", "extract_http")

    @property
    def tool_name(self) -> str:
        return "wireshark"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return "基于 scapy 的纯 Python 网络流量分析工具，支持 PCAP 解析、协议统计与 HTTP 提取"

    @property
    def capabilities(self) -> list[str]:
        return ["pcap_summary", "pcap_parse", "protocol_stats", "extract_http"]

    def __init__(self):
        pass

    def validate_input(self, params: dict) -> bool:
        """验证输入参数：必须包含 file_path 或 file。"""
        if "file_path" not in params and "file" not in params:
            return False
        action = params.get("action", "pcap_summary")
        return action in self.VALID_ACTIONS

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_file_path(params: dict) -> str:
        """从 params 中解析文件路径。"""
        return params.get("file_path") or params.get("file") or ""

    @staticmethod
    def _get_protocol_name(pkt: Packet) -> str:
        """推断数据包的主要协议名称。"""
        if pkt.haslayer(HTTPRequest) or pkt.haslayer(HTTPResponse):
            return "HTTP"
        if pkt.haslayer(DNS):
            return "DNS"
        if pkt.haslayer(ICMP):
            return "ICMP"
        if pkt.haslayer(TCP):
            return "TCP"
        if pkt.haslayer(UDP):
            return "UDP"
        if pkt.haslayer(IP):
            return "IP"
        if pkt.haslayer(IPv6):
            return "IPv6"
        if pkt.haslayer(Ether):
            return "Ethernet"
        return "Other"

    @staticmethod
    def _get_src_dst(pkt: Packet) -> tuple:
        """获取数据包的源地址和目标地址。"""
        src, dst = "-", "-"
        if pkt.haslayer(IP):
            src = pkt[IP].src
            dst = pkt[IP].dst
        elif pkt.haslayer(IPv6):
            src = pkt[IPv6].src
            dst = pkt[IPv6].dst
        elif pkt.haslayer(Ether):
            src = pkt[Ether].src
            dst = pkt[Ether].dst
        return (src, dst)

    @staticmethod
    def _get_packet_length(pkt: Packet) -> int:
        """获取数据包长度。"""
        return len(pkt)

    @staticmethod
    def _format_time(timestamp: float) -> str:
        """格式化时间戳为可读字符串。"""
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond:06d}"

    # ------------------------------------------------------------------
    # 功能实现
    # ------------------------------------------------------------------

    def _do_pcap_summary(self, packets: list[Packet], file_path: str) -> dict:
        """解析 PCAP 文件，输出总包数、时间范围、协议分布。"""
        total = len(packets)
        if total == 0:
            return {
                "action": "pcap_summary",
                "file_path": file_path,
                "total_packets": 0,
                "time_range": "N/A",
                "protocol_distribution": {},
            }

        timestamps = [float(pkt.time) for pkt in packets if hasattr(pkt, "time")]
        start_time = self._format_time(min(timestamps)) if timestamps else "N/A"
        end_time = self._format_time(max(timestamps)) if timestamps else "N/A"
        duration = max(timestamps) - min(timestamps) if timestamps else 0.0

        protocol_counter = Counter()
        for pkt in packets:
            protocol_counter[self._get_protocol_name(pkt)] += 1

        protocol_distribution = sorted(
            [{"protocol": proto, "count": cnt, "percentage": round(cnt / total * 100, 2)}
             for proto, cnt in protocol_counter.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        return {
            "action": "pcap_summary",
            "file_path": file_path,
            "total_packets": total,
            "time_range": {"start": start_time, "end": end_time, "duration_seconds": round(duration, 4)},
            "protocol_distribution": protocol_distribution,
        }

    def _do_pcap_parse(self, packets: list[Packet], file_path: str) -> dict:
        """解析 PCAP 文件，输出前 100 个包的详细信息。"""
        total = len(packets)
        limit = min(total, 100)

        parsed = []
        for i in range(limit):
            pkt = packets[i]
            src, dst = self._get_src_dst(pkt)
            proto = self._get_protocol_name(pkt)
            length = self._get_packet_length(pkt)
            timestamp = self._format_time(float(pkt.time)) if hasattr(pkt, "time") else "N/A"

            info = ""
            if pkt.haslayer(TCP):
                info = f"TCP {pkt[TCP].sport} -> {pkt[TCP].dport} [Flags: {pkt[TCP].flags}]"
            elif pkt.haslayer(UDP):
                info = f"UDP {pkt[UDP].sport} -> {pkt[UDP].dport}"
            elif pkt.haslayer(ICMP):
                info = f"ICMP type={pkt[ICMP].type} code={pkt[ICMP].code}"

            parsed.append({
                "index": i + 1,
                "timestamp": timestamp,
                "src": src,
                "dst": dst,
                "protocol": proto,
                "length": length,
                "info": info,
            })

        return {
            "action": "pcap_parse",
            "file_path": file_path,
            "total_packets": total,
            "displayed_packets": limit,
            "packets": parsed,
        }

    def _do_protocol_stats(self, packets: list[Packet], file_path: str) -> dict:
        """协议统计（各协议数量、占比）。"""
        total = len(packets)
        protocol_counter = Counter()
        for pkt in packets:
            protocol_counter[self._get_protocol_name(pkt)] += 1

        stats = []
        for proto, cnt in protocol_counter.most_common():
            stats.append({
                "protocol": proto,
                "count": cnt,
                "percentage": round(cnt / total * 100, 2) if total > 0 else 0.0,
            })

        return {
            "action": "protocol_stats",
            "file_path": file_path,
            "total_packets": total,
            "protocol_stats": stats,
        }

    def _do_extract_http(self, packets: list[Packet], file_path: str) -> dict:
        """提取 HTTP 请求/响应。"""
        requests = []
        responses = []

        for pkt in packets:
            try:
                if pkt.haslayer(HTTPRequest):
                    http = pkt[HTTPRequest]
                    req = {
                        "method": http.Method.decode() if isinstance(http.Method, bytes) else str(http.Method),
                        "host": http.Host.decode() if isinstance(http.Host, bytes) else str(http.Host) if hasattr(http, "Host") else "-",
                        "path": http.Path.decode() if isinstance(http.Path, bytes) else str(http.Path) if hasattr(http, "Path") else "-",
                        "user_agent": "-",
                    }
                    if hasattr(http, "User_Agent"):
                        req["user_agent"] = http.User_Agent.decode() if isinstance(http.User_Agent, bytes) else str(http.User_Agent)
                    if pkt.haslayer(IP):
                        req["src"] = pkt[IP].src
                        req["dst"] = pkt[IP].dst
                    requests.append(req)
                elif pkt.haslayer(HTTPResponse):
                    http = pkt[HTTPResponse]
                    resp = {
                        "status_code": http.Status_Code.decode() if isinstance(http.Status_Code, bytes) else str(http.Status_Code) if hasattr(http, "Status_Code") else "-",
                        "reason": http.Reason_Phrase.decode() if isinstance(http.Reason_Phrase, bytes) else str(http.Reason_Phrase) if hasattr(http, "Reason_Phrase") else "-",
                        "content_type": "-",
                    }
                    if hasattr(http, "Content_Type"):
                        resp["content_type"] = http.Content_Type.decode() if isinstance(http.Content_Type, bytes) else str(http.Content_Type)
                    if pkt.haslayer(IP):
                        resp["src"] = pkt[IP].src
                        resp["dst"] = pkt[IP].dst
                    responses.append(resp)
            except Exception:
                continue

        return {
            "action": "extract_http",
            "file_path": file_path,
            "total_http_requests": len(requests),
            "total_http_responses": len(responses),
            "http_requests": requests,
            "http_responses": responses,
        }

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def run(self, params: dict) -> ToolResult:
        """执行网络流量分析。"""
        if not _SCAPY_AVAILABLE:
            return ToolResult(
                success=False,
                error=(
                    "scapy 库未安装。请通过以下命令安装：\n"
                    "  pip install scapy\n\n"
                    "详细错误: " + _SCAPY_IMPORT_ERROR
                ),
            )

        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 缺少 file_path/file 参数，或 action 不支持"
            )

        file_path = self._resolve_file_path(params)
        if not file_path or not os.path.isfile(file_path):
            return ToolResult(
                success=False,
                error=f"PCAP 文件未找到: {file_path}"
            )

        action = params.get("action", "pcap_summary")
        start = time.perf_counter()

        try:
            # 读取 PCAP 文件
            packets = rdpcap(file_path)

            if action == "pcap_summary":
                data = self._do_pcap_summary(packets, file_path)
            elif action == "pcap_parse":
                data = self._do_pcap_parse(packets, file_path)
            elif action == "protocol_stats":
                data = self._do_protocol_stats(packets, file_path)
            elif action == "extract_http":
                data = self._do_extract_http(packets, file_path)
            else:
                data = self._do_pcap_summary(packets, file_path)

            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=round(duration, 4))

        except MemoryError:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error="PCAP 文件过大，内存不足。请尝试分割文件或使用过滤条件。",
                duration=round(duration, 4),
            )
        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"PCAP 解析异常: {str(e)}",
                duration=round(duration, 4),
            )