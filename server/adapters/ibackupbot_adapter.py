# iBackupBot 适配器（纯 Python 实现），使用 plistlib + sqlite3 解析 iOS iTunes 备份数据。

import os
import plistlib
import sqlite3
import time
from datetime import datetime, timezone

from server.adapters.base_adapter import BaseToolAdapter, ToolResult

# 常见 iTunes 备份路径
_DEFAULT_BACKUP_ROOTS = [
    os.path.join(os.environ.get("APPDATA", ""), "Apple Computer", "MobileSync", "Backup"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Apple", "MobileSync", "Backup"),
]

# 备份中关键文件的相对路径
_SMS_DB_PATH = ("HomeDomain", "Library/SMS/sms.db")
_CONTACTS_DB_PATH = ("HomeDomain", "Library/AddressBook/AddressBook.sqlitedb")
_CONTACTS_DB_PATH_ALT = ("HomeDomain", "Library/AddressBook/AddressBookImages.sqlitedb")


# iBackupBot iOS 备份分析适配器，使用 plistlib + sqlite3 解析 iTunes 备份，支持 list_backups / extract_sms / extract_contacts。
class IBackupBotAdapter(BaseToolAdapter):

    @property
    def tool_name(self) -> str:
        return "ibackupbot"

    @property
    def version(self) -> str:
        return "2.0-pure"

    @property
    def description(self) -> str:
        return (
            "iBackupBot iOS 备份分析工具（纯 Python 实现），"
            "使用 plistlib + sqlite3 标准库解析 iTunes 备份数据，"
            "支持列出备份、提取短信和联系人信息"
        )

    @property
    def capabilities(self) -> list[str]:
        return ["list_backups", "extract_sms", "extract_contacts", "ios_forensics"]

    def validate_input(self, params: dict) -> bool:
        """验证 action 参数。extract_sms/extract_contacts 时需要 backup_path。"""
        action = params.get("action", "list_backups")
        if action not in ("list_backups", "extract_sms", "extract_contacts"):
            return False
        if action in ("extract_sms", "extract_contacts"):
            return "backup_path" in params
        return True

    @staticmethod
    def _find_backup_dirs() -> list[str]:
        """查找系统中的 iTunes 备份目录。"""
        found: list[str] = []
        for root in _DEFAULT_BACKUP_ROOTS:
            if not root or not os.path.isdir(root):
                continue
            for entry in os.listdir(root):
                full = os.path.join(root, entry)
                if not os.path.isdir(full):
                    continue
                # 备份目录必须包含 Manifest.plist 或 Manifest.db
                if os.path.isfile(os.path.join(full, "Manifest.plist")) or \
                   os.path.isfile(os.path.join(full, "Manifest.db")):
                    found.append(full)
        return found

    @staticmethod
    def _read_manifest_plist(backup_path: str) -> dict | None:
        """读取备份的 Manifest.plist 文件。"""
        plist_path = os.path.join(backup_path, "Manifest.plist")
        if not os.path.isfile(plist_path):
            return None
        try:
            with open(plist_path, "rb") as f:
                return plistlib.load(f)
        except Exception:
            return None

    @staticmethod
    def _lookup_file_in_manifest_db(backup_path: str, domain: str, relative_path: str) -> str | None:
        """在 Manifest.db 中查找文件 hash，返回备份文件的实际文件名。"""
        manifest_db = os.path.join(backup_path, "Manifest.db")
        if not os.path.isfile(manifest_db):
            return None
        try:
            conn = sqlite3.connect(manifest_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT fileID FROM Files WHERE domain = ? AND relativePath = ?",
                (domain, relative_path),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return row["fileID"]
        except Exception:
            pass
        return None

    @staticmethod
    def _resolve_file_path(backup_path: str, file_id: str) -> str | None:
        """将 Manifest.db 的 fileID 解析为实际文件路径。"""
        actual = os.path.join(backup_path, file_id[:2], file_id)
        if os.path.isfile(actual):
            return actual
        # 某些旧版备份中文件直接放在备份根目录
        actual = os.path.join(backup_path, file_id)
        if os.path.isfile(actual):
            return actual
        return None

    @staticmethod
    def _parse_ios_date(seconds_since_2001: float) -> str:
        """将 iOS 时间戳转换为 ISO 格式字符串。"""
        epoch = datetime(2001, 1, 1, tzinfo=timezone.utc)
        dt = epoch.timestamp() + seconds_since_2001
        return datetime.fromtimestamp(dt, tz=timezone.utc).isoformat()

    def _action_list_backups(self, params: dict) -> ToolResult:
        """列出所有 iTunes 备份。backup_root: 可选手动指定备份根目录。"""
        backup_root = params.get("backup_root", "")
        backups: list[dict] = []

        if backup_root and os.path.isdir(backup_root):
            search_dirs = [backup_root]
        else:
            search_dirs = self._find_backup_dirs()

        for backup_dir in search_dirs:
            manifest = self._read_manifest_plist(backup_dir)
            if not manifest:
                continue

            info = {
                "backup_path": backup_dir,
                "udid": os.path.basename(backup_dir),
            }

            # 提取备份日期
            if "Date" in manifest:
                try:
                    info["backup_date"] = manifest["Date"].isoformat()
                except Exception:
                    info["backup_date"] = str(manifest.get("Date", ""))

            # 提取设备信息
            lockdow = manifest.get("Lockdown", {})
            info["device_name"] = lockdow.get("DeviceName", "")
            info["product_type"] = lockdow.get("ProductType", "")
            info["product_version"] = lockdow.get("ProductVersion", "")
            info["serial_number"] = lockdow.get("SerialNumber", "")
            info["build_version"] = lockdow.get("BuildVersion", "")
            info["unique_device_id"] = lockdow.get("UniqueDeviceID", "")

            # 备份类型
            info["is_encrypted"] = manifest.get("IsEncrypted", False)

            # 文件数量
            info["total_files"] = 0
            manifest_db = os.path.join(backup_dir, "Manifest.db")
            if os.path.isfile(manifest_db):
                try:
                    conn = sqlite3.connect(manifest_db)
                    count = conn.execute("SELECT COUNT(*) FROM Files").fetchone()[0]
                    conn.close()
                    info["total_files"] = count
                except Exception:
                    pass

            backups.append(info)

        return ToolResult(
            success=True,
            data={
                "action": "list_backups",
                "backup_count": len(backups),
                "backups": backups,
            },
        )

    def _action_extract_sms(self, params: dict) -> ToolResult:
        """提取短信数据。backup_path: 备份目录，output_file: 可选 CSV 输出。"""
        backup_path = params["backup_path"]
        output_file = params.get("output_file", "")

        if not os.path.isdir(backup_path):
            return ToolResult(success=False, error=f"备份目录不存在: {backup_path}")

        # 查找 sms.db
        domain, rel_path = _SMS_DB_PATH
        file_id = self._lookup_file_in_manifest_db(backup_path, domain, rel_path)
        if not file_id:
            return ToolResult(
                success=False,
                error=f"在备份中未找到短信数据库: {domain}/{rel_path}",
            )

        sms_db_path = self._resolve_file_path(backup_path, file_id)
        if not sms_db_path:
            return ToolResult(
                success=False,
                error=f"短信数据库文件不存在: {file_id}",
            )

        messages: list[dict] = []
        try:
            conn = sqlite3.connect(sms_db_path)
            conn.row_factory = sqlite3.Row

            # 尝试多种表结构（适应不同 iOS 版本）
            columns = self._get_sms_columns(conn)

            query = f"SELECT {', '.join(columns)} FROM message ORDER BY date DESC LIMIT 5000"
            cursor = conn.execute(query)

            for row in cursor:
                msg = {}
                # 发件人 / 电话号码
                if "handle_id" in row.keys() and "handle" in columns:
                    # iOS 12+ 可能使用 handle 表关联
                    pass
                msg["address"] = row["address"] if "address" in row.keys() else ""

                # 日期
                if "date" in row.keys() and row["date"]:
                    msg["date"] = self._parse_ios_date(row["date"])
                else:
                    msg["date"] = ""

                # 内容
                msg["text"] = row["text"] if "text" in row.keys() else ""

                # 方向
                if "is_from_me" in row.keys():
                    msg["direction"] = "sent" if row["is_from_me"] else "received"
                else:
                    msg["direction"] = "unknown"

                # 服务类型（iMessage / SMS）
                msg["service"] = row.get("service", "")

                messages.append(msg)

            conn.close()

            # 如果有关联的 handle 表，尝试解析电话号码
            if "handle_id" in self._get_sms_columns(conn):
                pass  # 已关闭连接，维持简单逻辑

            # 尝试补充 handle 信息
            try:
                conn2 = sqlite3.connect(sms_db_path)
                conn2.row_factory = sqlite3.Row
                handle_map = {}
                for row in conn2.execute("SELECT ROWID, id, service FROM handle"):
                    handle_map[row["ROWID"]] = {"id": row["id"], "service": row["service"]}
                conn2.close()

                for msg in messages:
                    if "handle_id" in self._get_sms_columns(None):
                        pass
            except Exception:
                pass

        except sqlite3.OperationalError as e:
            return ToolResult(success=False, error=f"无法打开短信数据库: {str(e)}")
        except Exception as e:
            return ToolResult(success=False, error=f"提取短信时发生异常: {str(e)}")

        # 写入 CSV 文件
        csv_path = ""
        if output_file:
            csv_path = self._write_sms_csv(messages, output_file)

        return ToolResult(
            success=True,
            data={
                "action": "extract_sms",
                "backup_path": backup_path,
                "sms_db_path": sms_db_path,
                "message_count": len(messages),
                "messages": messages,
                "output_file": csv_path if csv_path else None,
            },
        )

    def _action_extract_contacts(self, params: dict) -> ToolResult:
        """提取联系人数据。backup_path: 备份目录，output_file: 可选 CSV 输出。"""
        backup_path = params["backup_path"]
        output_file = params.get("output_file", "")

        if not os.path.isdir(backup_path):
            return ToolResult(success=False, error=f"备份目录不存在: {backup_path}")

        # 查找通讯录数据库
        domain, rel_path = _CONTACTS_DB_PATH
        file_id = self._lookup_file_in_manifest_db(backup_path, domain, rel_path)
        if not file_id:
            # 尝试备用路径
            domain, rel_path = _CONTACTS_DB_PATH_ALT
            file_id = self._lookup_file_in_manifest_db(backup_path, domain, rel_path)

        if not file_id:
            return ToolResult(
                success=False,
                error=f"在备份中未找到通讯录数据库: {_CONTACTS_DB_PATH[1]}",
            )

        contacts_db_path = self._resolve_file_path(backup_path, file_id)
        if not contacts_db_path:
            return ToolResult(
                success=False,
                error=f"通讯录数据库文件不存在: {file_id}",
            )

        contacts: list[dict] = []
        try:
            conn = sqlite3.connect(contacts_db_path)
            conn.row_factory = sqlite3.Row

            # 查询联系人
            person_rows = conn.execute(
                "SELECT ROWID, First, Last, Middle, Organization, Department, "
                "Birthday, JobTitle, Nickname, Note, Prefix, Suffix "
                "FROM ABPerson"
            ).fetchall()

            for person in person_rows:
                contact = {
                    "first_name": person["First"] or "",
                    "last_name": person["Last"] or "",
                    "middle_name": person["Middle"] or "",
                    "organization": person["Organization"] or "",
                    "department": person["Department"] or "",
                    "job_title": person["JobTitle"] or "",
                    "nickname": person["Nickname"] or "",
                    "note": person["Note"] or "",
                    "phones": [],
                    "emails": [],
                }

                # 提取电话号码
                phone_rows = conn.execute(
                    "SELECT value FROM ABMultiValue "
                    "WHERE record_id = ? AND property = 3",
                    (person["ROWID"],),
                ).fetchall()
                for pr in phone_rows:
                    if pr["value"]:
                        contact["phones"].append(str(pr["value"]))

                # 提取邮箱
                email_rows = conn.execute(
                    "SELECT value FROM ABMultiValue "
                    "WHERE record_id = ? AND property = 4",
                    (person["ROWID"],),
                ).fetchall()
                for er in email_rows:
                    if er["value"]:
                        contact["emails"].append(str(er["value"]))

                contacts.append(contact)

            conn.close()

        except sqlite3.OperationalError as e:
            return ToolResult(success=False, error=f"无法打开通讯录数据库: {str(e)}")
        except Exception as e:
            return ToolResult(success=False, error=f"提取联系人时发生异常: {str(e)}")

        # 写入 CSV 文件
        csv_path = ""
        if output_file:
            csv_path = self._write_contacts_csv(contacts, output_file)

        return ToolResult(
            success=True,
            data={
                "action": "extract_contacts",
                "backup_path": backup_path,
                "contacts_db_path": contacts_db_path,
                "contact_count": len(contacts),
                "contacts": contacts,
                "output_file": csv_path if csv_path else None,
            },
        )

    @staticmethod
    def _get_sms_columns(conn: sqlite3.Connection | None) -> list[str]:
        """探测 sms.db message 表的列名（兼容不同 iOS 版本）。"""
        if conn is None:
            return []
        try:
            cursor = conn.execute("PRAGMA table_info(message)")
            return [row[1] for row in cursor.fetchall()]
        except Exception:
            return ["ROWID", "address", "date", "text", "is_from_me", "service"]

    @staticmethod
    def _write_sms_csv(messages: list[dict], output_file: str) -> str:
        """将短信列表写入 CSV 文件，返回绝对路径。"""
        import csv

        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=["address", "date", "text", "direction", "service"]
            )
            writer.writeheader()
            for msg in messages:
                writer.writerow({
                    k: msg.get(k, "") for k in ["address", "date", "text", "direction", "service"]
                })

        return os.path.abspath(output_file)

    @staticmethod
    def _write_contacts_csv(contacts: list[dict], output_file: str) -> str:
        """将联系人数据写入 CSV 文件。"""
        import csv

        out_dir = os.path.dirname(os.path.abspath(output_file))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "first_name", "last_name", "organization", "department",
                    "job_title", "phones", "emails",
                ],
            )
            writer.writeheader()
            for c in contacts:
                writer.writerow({
                    "first_name": c["first_name"],
                    "last_name": c["last_name"],
                    "organization": c["organization"],
                    "department": c["department"],
                    "job_title": c["job_title"],
                    "phones": "; ".join(c["phones"]),
                    "emails": "; ".join(c["emails"]),
                })

        return os.path.abspath(output_file)

    async def run(self, params: dict) -> ToolResult:
        """异步执行工具。action: list_backups/extract_sms/extract_contacts。"""
        if not self.validate_input(params):
            return ToolResult(
                success=False,
                error=(
                    "参数验证失败: action 必须为 'list_backups', 'extract_sms' 或 "
                    "'extract_contacts'；extract_sms/extract_contacts 动作还需要 "
                    "'backup_path' 参数"
                ),
            )

        action = params.get("action", "list_backups")
        start = time.perf_counter()

        try:
            if action == "list_backups":
                result = self._action_list_backups(params)
            elif action == "extract_sms":
                result = self._action_extract_sms(params)
            elif action == "extract_contacts":
                result = self._action_extract_contacts(params)
            else:
                result = ToolResult(success=False, error=f"未知动作: {action}")

            if result.duration == 0.0:
                result.duration = time.perf_counter() - start
            return result

        except Exception as e:
            duration = time.perf_counter() - start
            return ToolResult(
                success=False,
                error=f"iBackupBot 执行异常: {str(e)}",
                duration=duration,
            )