# Hashcat 适配器（纯 Python），基于 hashlib 实现哈希类型自动识别。

import hashlib
import re
import time

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# 哈希类型定义: (名称, 描述, 长度（字符数）, 正则模式, 十六进制字符集)
_HASH_TYPE_DEFINITIONS = [
    # 名称, 描述, 字符长度, 正则匹配, 是否仅十六进制
    {
        "name": "MD5",
        "description": "MD5 消息摘要算法（128-bit）",
        "length": 32,
        "pattern": re.compile(r"^[a-fA-F0-9]{32}$"),
        "hashcat_mode": 0,
    },
    {
        "name": "SHA-1",
        "description": "SHA-1 安全哈希算法（160-bit）",
        "length": 40,
        "pattern": re.compile(r"^[a-fA-F0-9]{40}$"),
        "hashcat_mode": 100,
    },
    {
        "name": "SHA-256",
        "description": "SHA-256 安全哈希算法（256-bit）",
        "length": 64,
        "pattern": re.compile(r"^[a-fA-F0-9]{64}$"),
        "hashcat_mode": 1400,
    },
    {
        "name": "SHA-512",
        "description": "SHA-512 安全哈希算法（512-bit）",
        "length": 128,
        "pattern": re.compile(r"^[a-fA-F0-9]{128}$"),
        "hashcat_mode": 1700,
    },
    {
        "name": "NTLM",
        "description": "Windows NTLM 哈希",
        "length": 32,
        "pattern": re.compile(r"^[a-fA-F0-9]{32}$"),
        "hashcat_mode": 1000,
        "note": "与 MD5 长度相同，需结合上下文区分",
    },
    {
        "name": "LM",
        "description": "Windows LM 哈希（已废弃，不区分大小写）",
        "length": 32,
        "pattern": re.compile(r"^[A-F0-9]{32}$"),
        "hashcat_mode": 3000,
        "note": "LM 哈希仅包含大写十六进制字符",
    },
    {
        "name": "SHA-384",
        "description": "SHA-384 安全哈希算法（384-bit）",
        "length": 96,
        "pattern": re.compile(r"^[a-fA-F0-9]{96}$"),
        "hashcat_mode": 10800,
    },
    {
        "name": "SHA-224",
        "description": "SHA-224 安全哈希算法（224-bit）",
        "length": 56,
        "pattern": re.compile(r"^[a-fA-F0-9]{56}$"),
        "hashcat_mode": 1300,
    },
    {
        "name": "MySQL 4.1+",
        "description": "MySQL 4.1+ 密码哈希（SHA-1 双哈希，带 * 前缀）",
        "length": 41,
        "pattern": re.compile(r"^\*[a-fA-F0-9]{40}$"),
        "hashcat_mode": 300,
    },
    {
        "name": "MySQL 3.x",
        "description": "MySQL 3.x 旧版密码哈希",
        "length": 16,
        "pattern": re.compile(r"^[a-fA-F0-9]{16}$"),
        "hashcat_mode": 200,
    },
    {
        "name": "MD5-Crypt ($1$)",
        "description": "MD5 Unix crypt 格式",
        "length": None,  # 可变长度
        "pattern": re.compile(r"^\$1\$[a-zA-Z0-9./]{1,8}\$[a-zA-Z0-9./]{22}$"),
        "hashcat_mode": 500,
    },
    {
        "name": "SHA-256-Crypt ($5$)",
        "description": "SHA-256 Unix crypt 格式",
        "length": None,
        "pattern": re.compile(r"^\$5\$[a-zA-Z0-9./]{1,16}\$[a-zA-Z0-9./]{43}$"),
        "hashcat_mode": 7400,
    },
    {
        "name": "SHA-512-Crypt ($6$)",
        "description": "SHA-512 Unix crypt 格式",
        "length": None,
        "pattern": re.compile(r"^\$6\$[a-zA-Z0-9./]{1,16}\$[a-zA-Z0-9./]{86}$"),
        "hashcat_mode": 1800,
    },
    {
        "name": "bcrypt ($2a$/2b$/2y$)",
        "description": "bcrypt 密码哈希",
        "length": None,
        "pattern": re.compile(r"^\$2[aby]\$\d{2}\$[a-zA-Z0-9./]{53}$"),
        "hashcat_mode": 3200,
    },
    {
        "name": "SHA-1 (Base64)",
        "description": "SHA-1 哈希（Base64 编码）",
        "length": 28,
        "pattern": re.compile(r"^[a-zA-Z0-9+/=]{27,28}$"),
        "hashcat_mode": 101,
    },
    {
        "name": "SHA-256 (Base64)",
        "description": "SHA-256 哈希（Base64 编码）",
        "length": 44,
        "pattern": re.compile(r"^[a-zA-Z0-9+/=]{43,44}$"),
        "hashcat_mode": 1410,
    },
    {
        "name": "Keccak-256",
        "description": "Keccak-256 / SHA-3-256（ETH 地址原始哈希）",
        "length": 64,
        "pattern": re.compile(r"^[a-fA-F0-9]{64}$"),
        "hashcat_mode": 17800,
        "note": "与 SHA-256 长度相同，需结合上下文区分",
    },
    {
        "name": "RIPEMD-160",
        "description": "RIPEMD-160 哈希（常用于比特币地址）",
        "length": 40,
        "pattern": re.compile(r"^[a-fA-F0-9]{40}$"),
        "hashcat_mode": 6000,
        "note": "与 SHA-1 长度相同，需结合上下文区分",
    },
    {
        "name": "Whirlpool",
        "description": "Whirlpool 哈希算法（512-bit）",
        "length": 128,
        "pattern": re.compile(r"^[a-fA-F0-9]{128}$"),
        "hashcat_mode": 6100,
        "note": "与 SHA-512 长度相同，需结合上下文区分",
    },
    {
        "name": "CRC32",
        "description": "CRC32 校验和（8 位十六进制）",
        "length": 8,
        "pattern": re.compile(r"^[a-fA-F0-9]{8}$"),
        "hashcat_mode": 11500,
    },
    {
        "name": "DES Crypt",
        "description": "DES Unix crypt 格式（13 字符）",
        "length": 13,
        "pattern": re.compile(r"^[a-zA-Z0-9./]{13}$"),
        "hashcat_mode": 1500,
    },
    {
        "name": "MD4",
        "description": "MD4 消息摘要算法（128-bit）",
        "length": 32,
        "pattern": re.compile(r"^[a-fA-F0-9]{32}$"),
        "hashcat_mode": 900,
        "note": "与 MD5/NTLM 长度相同，需结合上下文区分",
    },
    {
        "name": "Kerberos 5 TGS-REP",
        "description": "Kerberos 5 TGS-REP 哈希（$krb5tgs$ 前缀）",
        "length": None,
        "pattern": re.compile(r"^\$krb5tgs\$\d+\$"),
        "hashcat_mode": 13100,
    },
    {
        "name": "WPA/WPA2 PMKID",
        "description": "WPA/WPA2 PMKID 哈希",
        "length": None,
        "pattern": re.compile(r"^[a-fA-F0-9]{32}\*[a-fA-F0-9]{12}\*[a-fA-F0-9]{12}\*[a-fA-F0-9]{12}$"),
        "hashcat_mode": 22000,
    },
    {
        "name": "Ethereum Wallet",
        "description": "以太坊钱包密钥文件（JSON 格式）",
        "length": None,
        "pattern": re.compile(r'^\s*\{.*"crypto"|"Cipher"', re.DOTALL),
        "hashcat_mode": 15700,
    },
    {
        "name": "Bitcoin Wallet",
        "description": "比特币钱包密钥文件",
        "length": None,
        "pattern": re.compile(r'^\s*\{.*"encrypted_key"|"EncryptedKey"', re.DOTALL),
        "hashcat_mode": 11300,
    },
    {
        "name": "PDF 1.4-1.6",
        "description": "PDF 文档加密哈希（$pdf$ 前缀）",
        "length": None,
        "pattern": re.compile(r"^\$pdf\$\d+\*"),
        "hashcat_mode": 10500,
    },
    {
        "name": "ZIP (PKZIP)",
        "description": "ZIP 压缩包加密哈希（$zip2$ 前缀）",
        "length": None,
        "pattern": re.compile(r"^\$zip2\$"),
        "hashcat_mode": 13600,
    },
    {
        "name": "RAR5",
        "description": "RAR5 压缩包加密哈希（$rar5$ 前缀）",
        "length": None,
        "pattern": re.compile(r"^\$rar5\$"),
        "hashcat_mode": 13000,
    },
    {
        "name": "7-Zip",
        "description": "7-Zip 压缩包加密哈希（$7z$ 前缀）",
        "length": None,
        "pattern": re.compile(r"^\$7z\$"),
        "hashcat_mode": 11600,
    },
    {
        "name": "Office 2013",
        "description": "Microsoft Office 2013 文档加密",
        "length": None,
        "pattern": re.compile(r"^\$office\$"),
        "hashcat_mode": 9600,
    },
    {
        "name": "iTunes Backup",
        "description": "iTunes 备份加密哈希",
        "length": None,
        "pattern": re.compile(r"^\$itunes_backup\$"),
        "hashcat_mode": 14800,
    },
    {
        "name": "Android FDE",
        "description": "Android 全盘加密（FDE）哈希",
        "length": None,
        "pattern": re.compile(r"^\$fde\$"),
        "hashcat_mode": 8800,
    },
    {
        "name": "NetNTLMv1",
        "description": "NetNTLMv1 网络认证哈希",
        "length": None,
        "pattern": re.compile(r"^[A-Za-z0-9+/=]+::[A-Za-z0-9]+:"),
        "hashcat_mode": 5500,
    },
    {
        "name": "NetNTLMv2",
        "description": "NetNTLMv2 网络认证哈希",
        "length": None,
        "pattern": re.compile(r"^[A-Za-z0-9+/=]+::[A-Za-z0-9]+:[a-fA-F0-9]{16}:[a-fA-F0-9]+:"),
        "hashcat_mode": 5600,
    },
    {
        "name": "SSH Private Key",
        "description": "SSH 私钥加密哈希（$sshng$ 前缀）",
        "length": None,
        "pattern": re.compile(r"^\$sshng\$"),
        "hashcat_mode": 22911,
    },
    {
        "name": "DPAPI Masterkey",
        "description": "Windows DPAPI 主密钥（$DPAPImk$ 前缀）",
        "length": None,
        "pattern": re.compile(r"^\$DPAPImk\$"),
        "hashcat_mode": 15300,
    },
]

# 预计算常见字符串的哈希示例，用于对比演示
_SAMPLE_STRINGS = [
    "password",
    "123456",
    "admin",
    "hashcat",
    "forensics",
    "hello world",
    "qwerty",
    "letmein",
    "monkey",
    "dragon",
]


# 预计算常见字符串的多种哈希值，用于演示和对比。
def _compute_sample_hashes() -> list[dict]:
    results = []
    for text in _SAMPLE_STRINGS:
        entry = {
            "text": text,
            "md5": hashlib.md5(text.encode()).hexdigest(),
            "sha1": hashlib.sha1(text.encode()).hexdigest(),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "sha512": hashlib.sha512(text.encode()).hexdigest(),
        }
        results.append(entry)
    return results


# 哈希类型识别适配器，基于长度和格式识别 30+ 种哈希类型。注意：非破解器。
class HashcatAdapter(BaseToolAdapter):
    @property
    def tool_name(self) -> str:
        return "hashcat"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return (
            "Hashcat 哈希类型识别器（纯 Python 实现），"
            "基于长度和格式自动识别 30+ 种常见哈希类型。"
            "注意：这是识别器，不是破解器，实际破解需 GPU 加速并安装 hashcat 原版。"
        )

    @property
    def capabilities(self) -> list[str]:
        return ["hash_identification", "hash_analysis", "hash_samples"]

    # 验证输入参数：需要 hash 或 hash_value 参数。
    def validate_input(self, params: dict) -> bool:
        return "hash" in params or "hash_value" in params

    # 从参数中提取哈希值。
    def _get_hash_value(self, params: dict) -> str:
        return params.get("hash", params.get("hash_value", ""))

    # 根据哈希值识别可能的哈希类型，返回按优先级排序的匹配列表（精确格式匹配优先）。
    def _identify_hash_type(self, hash_value: str) -> list[dict]:
        stripped = hash_value.strip()
        matches = []

        # 第一阶段：精确格式匹配（带前缀的模式）
        exact_matches = []
        # 第二阶段：长度+十六进制匹配
        hex_matches = []

        for htype in _HASH_TYPE_DEFINITIONS:
            if htype["pattern"].match(stripped):
                match_info = {
                    "name": htype["name"],
                    "description": htype["description"],
                    "hashcat_mode": htype["hashcat_mode"],
                    "length": htype.get("length"),
                }
                if "note" in htype:
                    match_info["note"] = htype["note"]

                # 区分精确格式匹配和纯十六进制长度匹配
                if htype["length"] is None:
                    # 可变长度，基于前缀/格式匹配，优先级最高
                    exact_matches.append(match_info)
                else:
                    hex_matches.append(match_info)

        # 精确格式匹配排在最前
        matches = exact_matches + hex_matches
        return matches

    # 分析哈希值的详细特征，返回包含长度、字符集、十六进制比例等分析信息的字典。
    def _analyze_hash(self, hash_value: str) -> dict:
        stripped = hash_value.strip()

        hex_chars = set("0123456789abcdefABCDEF")
        lower_chars = set("abcdef")
        upper_chars = set("ABCDEF")
        digit_chars = set("0123456789")
        special_chars = set("$*./=+")

        total = len(stripped)
        hex_count = sum(1 for c in stripped if c in hex_chars)
        lower_count = sum(1 for c in stripped if c in lower_chars)
        upper_count = sum(1 for c in stripped if c in upper_chars)
        digit_count = sum(1 for c in stripped if c in digit_chars)
        special_count = sum(1 for c in stripped if c in special_chars)

        return {
            "total_length": total,
            "hex_char_count": hex_count,
            "hex_percent": round(hex_count / total * 100, 1) if total > 0 else 0,
            "all_hex": hex_count == total,
            "all_uppercase": upper_count == total,
            "all_lowercase": lower_count == total,
            "all_digits": digit_count == total,
            "has_special_chars": special_count > 0,
            "has_dollar_prefix": stripped.startswith("$"),
            "has_asterisk_prefix": stripped.startswith("*"),
            "mixed_case": lower_count > 0 and upper_count > 0,
            "starts_with": stripped[:4] if len(stripped) >= 4 else stripped,
        }

    # 执行哈希类型识别。需 hash 或 hash_value 参数，可选 action: identify/samples。
    async def run(self, params: dict) -> ToolResult:
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error="参数验证失败: 需要提供 hash 或 hash_value 参数"
            )

        start = time.perf_counter()
        action = params.get("action", "identify")

        try:
            if action == "samples":
                sample_hashes = _compute_sample_hashes()
                data = {
                    "action": "samples",
                    "sample_count": len(sample_hashes),
                    "samples": sample_hashes,
                    "note": "这些是常见字符串的哈希示例，用于对比参考。",
                }
            else:
                # action == "identify" (默认)
                hash_value = self._get_hash_value(params)
                if not hash_value or not hash_value.strip():
                    return ToolResult(
                        success=False,
                        error="哈希值为空，请提供有效的 hash 或 hash_value 参数"
                    )

                stripped = hash_value.strip()
                matches = self._identify_hash_type(stripped)
                analysis = self._analyze_hash(stripped)

                data = {
                    "action": "identify",
                    "hash_value": stripped,
                    "hash_length": len(stripped),
                    "hash_analysis": analysis,
                    "possible_types": matches,
                    "match_count": len(matches),
                    "identified": len(matches) > 0,
                    "disclaimer": (
                        "此工具仅识别哈希类型，不执行密码破解。"
                        "实际密码破解需要 GPU 加速，请安装 hashcat 原版工具。"
                        "hashcat 官网: https://hashcat.net/hashcat/"
                    ),
                }

                if len(matches) > 1:
                    data["warning"] = (
                        f"检测到 {len(matches)} 种可能的哈希类型，"
                        "请结合上下文（如来源系统、应用场景）进一步确认具体类型。"
                    )

            duration = time.perf_counter() - start
            return ToolResult(success=True, data=data, duration=duration)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"哈希识别执行异常: {str(e)}",
                duration=time.perf_counter() - start,
            )