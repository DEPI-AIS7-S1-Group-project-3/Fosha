"""Singletons live on app.state (created in main.create_app); routers get them
through these functions, and tests replace them with app.dependency_overrides."""
from fastapi import Request

from backend.config import Settings
from backend.services.analytics import Analytics
from backend.services.cache import TTLCache
from backend.services.chat import ChatService


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_cache(request: Request) -> TTLCache:
    return request.app.state.cache


def get_analytics(request: Request) -> Analytics:
    return request.app.state.analytics
