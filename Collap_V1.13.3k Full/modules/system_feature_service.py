"""Các quyết định điều hướng theo trạng thái tính năng hệ thống."""
from __future__ import annotations


def post_login_endpoint(features: dict, is_admin: bool = False) -> str:
    if is_admin:
        return "admin"
    return "dashboard" if features.get("dashboard_enabled", False) else "ranking"


def dashboard_is_enabled(features: dict) -> bool:
    return bool(features.get("dashboard_enabled", False))
