"""
貓貓黑名單客戶端 世界上最可愛的貓貓做的黑名單管理工具
可以輕鬆調用API
Made by kusanagi_akane(!草薙明音) 2026 all rights reserved.
"""

import requests
import json
import os
import sys
import base64
import logging
from typing import Optional, Any
from datetime import datetime, timezone

# ── 路徑常數 ──────────────────────────────────────────────
def _get_app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _get_resource_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(_get_app_base_dir(), relative_path)


BASE_DIR = _get_app_base_dir()
SESSION_FILE = os.path.join(BASE_DIR, "session.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_FILE = os.path.join(DATA_DIR, "actions.log")

os.makedirs(DATA_DIR, exist_ok=True)

# ── 日誌 ─────────────────────────────────────────────────
logger = logging.getLogger("BlacklistClient")

# ── 例外 ──────────────────────────────────────────────

class APIError(Exception):
    """API 回傳非 2xx 狀態碼時拋出"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[HTTP {status_code}] {detail}")


class AuthError(Exception):
    """未登入或 Token 無效時拋出"""
    pass


# ── 簡易 Token 混淆 ─────────────

def _encode_token(token: str) -> str:
    return base64.b64encode(token.encode()).decode()

def _decode_token(encoded: str) -> str:
    return base64.b64decode(encoded.encode()).decode()


# ── 主客戶端 ──────────────────────────────────────────────

class BlacklistClient:
    """黑名單 API 用戶端，封裝所有遠端操作。"""

    # 請求逾時
    DEFAULT_TIMEOUT = 15
    # 失敗自動重試次數
    MAX_RETRIES = 2

    def __init__(self, config_path: Optional[str] = None):
        config_path = config_path or (CONFIG_FILE if os.path.exists(CONFIG_FILE) else _get_resource_path("config.json"))
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise FileNotFoundError(f"無法讀取設定檔 {config_path}: {e}")

        self.base_url: str = config.get("base_url", "").rstrip("/")
        if not self.base_url:
            raise ValueError("config.json 缺少 base_url")

        self.timeout: int = config.get("timeout", self.DEFAULT_TIMEOUT)
        self.token: Optional[str] = self._load_token()

    # ── Token 管理 ────────────────────────────────────────

    def _load_token(self) -> Optional[str]:
        """從 session 檔載入 Token（Base64）"""
        if not os.path.exists(SESSION_FILE):
            return None
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            encoded = data.get("token")
            if encoded:
                return _decode_token(encoded)
        except Exception:
            logger.warning("session.json 損壞，已忽略")
        return None

    def save_token(self, token: str) -> None:
        """儲存 Token（Base64 編碼後寫入）"""
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"token": _encode_token(token)}, f)
        self.token = token

    def logout(self) -> None:
        """登出：清除本地 Token"""
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        self.token = None

    @property
    def is_logged_in(self) -> bool:
        return self.token is not None

    # ── 連線測試 ──────────────────────────────────────────

    def test_connection(self) -> bool:
        """測試 API 伺服器是否可達"""
        try:
            resp = requests.get(
                f"{self.base_url}/",
                timeout=self.timeout
            )
            return resp.status_code < 500
        except requests.RequestException:
            return False

    # ── HTTP Core ─────────────────────────────────────────

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        if not self.token:
            raise AuthError("尚未登入，請先輸入 API Token")

        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["X-API-Key"] = self.token
        kwargs.setdefault("timeout", self.timeout)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = requests.request(method, url, headers=headers, **kwargs)

                if resp.status_code == 401:
                    raise AuthError("Token 無效或已失效，請重新登入")
                if resp.status_code == 403:
                    raise AuthError("權限不足，此 Token 無法執行此操作")
                if resp.status_code >= 400:
                    detail = resp.text[:300] if resp.text else "No detail"
                    raise APIError(resp.status_code, detail)

                if resp.text.strip():
                    return resp.json()
                return {"status": "ok"}

            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                logger.warning(f"請求失敗 (第 {attempt} 次): {e}")
                if attempt >= self.MAX_RETRIES:
                    break
            except (AuthError, APIError):
                raise

        raise ConnectionError(f"無法連線至伺服器（已重試 {self.MAX_RETRIES} 次）：{last_error}")

    # ── 自動備份 ──────────────────────────────────────────

    def backup(self) -> Optional[str]:
        """備份目前黑名單，回傳備份檔路徑"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_path = os.path.join(DATA_DIR, f"backup-{timestamp}.json")
        try:
            data = self.get_all()
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"備份成功: {backup_path}")
            return backup_path
        except Exception as e:
            logger.warning(f"備份失敗: {e}")
            return None

    def _log_action(self, action: str, user_id: Optional[str] = None) -> None:
        """記錄操作日誌"""
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "user_id": user_id,
        }
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"日誌寫入失敗: {e}")

    # ── API 操作 ──────────────────────────────────────────

    def get_all(self) -> Any:
        """取得完整黑名單"""
        return self._request("GET", "/blacklist")

    def get_user(self, user_id: str) -> Any:
        """查詢單一使用者"""
        if not user_id or not user_id.strip():
            raise ValueError("使用者 ID 不得為空")
        return self._request("GET", f"/blacklist?id={user_id.strip()}")

    def add_user(self, user_id: str, by: str, mode: str = "block", reason: str = "") -> Any:
        """新增使用者至黑名單"""
        if not user_id or not user_id.strip():
            raise ValueError("使用者 ID 不得為空")
        if not by or not by.strip():
            raise ValueError("操作者 (by) 不得為空")
        if mode not in ("block", "global_ban"):
            raise ValueError(f"無效模式 '{mode}'，可用: block / global_ban")

        params = {"by": by.strip(), "mode": mode, "reason": reason}
        res = self._request("POST", f"/blacklist/{user_id.strip()}", params=params)
        self.backup()
        self._log_action("add", user_id.strip())
        return res

    def remove_user(self, user_id: str) -> Any:
        """從黑名單移除使用者"""
        if not user_id or not user_id.strip():
            raise ValueError("使用者 ID 不得為空")
        res = self._request("DELETE", f"/blacklist/{user_id.strip()}")
        self.backup()
        self._log_action("remove", user_id.strip())
        return res

    def override(self, data: dict) -> Any:
        """覆蓋整份黑名單資料"""
        if not isinstance(data, (dict, list)):
            raise ValueError("覆蓋資料必須為 dict 或 list")
        res = self._request("PUT", "/blacklist/override", json=data)
        self.backup()
        self._log_action("override")
        return res

    def save_to_file(self, data: Any, filepath: str) -> None:
        """將資料匯出為 JSON 檔案"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        self._log_action("export")
