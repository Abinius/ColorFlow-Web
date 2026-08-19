"""ColorFlow Key Store — API Key 生成 / 校验 / 撤销

存储格式：JSON 文件，默认 ~/.colorflow/keys.json
Key 格式：cf_sk_ + 32 位随机 hex
向后兼容：COLORFLOW_API_KEY 环境变量仍然有效
"""

import json
import os
import secrets
import threading
from datetime import datetime, timezone

# Key 文件默认路径
_DEFAULT_PATH = os.path.join(os.path.expanduser("~"), ".colorflow", "keys.json")

_lock = threading.Lock()


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class KeyStore:
    """线程安全的 API Key 管理器"""

    def __init__(self, path=None):
        self.path = path or _DEFAULT_PATH
        self._cache = None

    # ---- 文件读写 ----

    def _load(self):
        """从磁盘加载 key 列表，文件不存在时返回空列表"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return []

    def _save(self, keys):
        """原子写入 key 列表"""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(keys, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        # 收紧文件权限（仅当前用户可读写）
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        self._cache = keys

    def _flush(self):
        """强制从磁盘重新加载"""
        self._cache = None

    # ---- 公开 API ----

    def generate(self, name=""):
        """生成一个新 Key，返回明文（仅此一次可见）"""
        key = "cf_sk_" + secrets.token_hex(16)
        entry = {
            "key": key,
            "name": name.strip() or "未命名",
            "created_at": _now_iso(),
            "last_used": None,
        }
        with _lock:
            keys = self._load()
            keys.append(entry)
            self._save(keys)
        return entry

    def verify(self, raw_key):
        """校验 key 是否有效，返回 bool；有效时更新 last_used"""
        if not raw_key:
            return False
        with _lock:
            keys = self._load()
            for entry in keys:
                if secrets.compare_digest(
                    raw_key.encode("utf-8"), entry["key"].encode("utf-8")
                ):
                    entry["last_used"] = _now_iso()
                    self._save(keys)
                    return True
            return False

    def list_all(self):
        """列出所有 key（key 字段脱敏）"""
        with _lock:
            keys = self._load()
        result = []
        for entry in keys:
            k = entry["key"]
            masked = k[:8] + "****" + k[-4:] if len(k) > 12 else "****"
            result.append({
                "key_id": entry["key"],  # 用完整 key 作为 ID（撤销时需要）
                "key_masked": masked,
                "name": entry.get("name", ""),
                "created_at": entry.get("created_at", ""),
                "last_used": entry.get("last_used"),
            })
        return result

    def revoke(self, key_id):
        """撤销指定 key，返回 bool"""
        with _lock:
            keys = self._load()
            before = len(keys)
            keys = [k for k in keys if k["key"] != key_id]
            if len(keys) < before:
                self._save(keys)
                return True
            return False

    def has_any(self):
        """是否已有任何 key"""
        with _lock:
            return len(self._load()) > 0

    def bootstrap_from_env(self, env_key):
        """从环境变量 bootstrap 一个 legacy key（向后兼容）"""
        if not env_key:
            return
        with _lock:
            keys = self._load()
            # 避免重复
            if any(k["key"] == env_key for k in keys):
                return
            keys.append({
                "key": env_key,
                "name": "环境变量 (legacy)",
                "created_at": _now_iso(),
                "last_used": None,
            })
            self._save(keys)


# 全局单例
keystore = KeyStore()

# 启动时从环境变量 bootstrap
_env_key = os.getenv("COLORFLOW_API_KEY", "").strip()
if _env_key:
    keystore.bootstrap_from_env(_env_key)
