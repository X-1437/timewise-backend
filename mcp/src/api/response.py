from typing import Any


def ok(data: Any, message: str = "操作成功") -> dict:
    return {"success": True, "data": data, "message": message, "error_code": None}


def fail(message: str, error_code: str) -> dict:
    return {"success": False, "data": None, "message": message, "error_code": error_code}
