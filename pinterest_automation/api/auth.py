from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from pinterest_automation.config.settings import settings


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce API key authentication on all endpoints."""
    
    # Paths that don't require authentication
    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/media", "/ws", "/api/health"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip auth if no API key configured (dev mode)
        if not settings.api_key:
            return await call_next(request)
        
        # Skip auth for exempt paths
        path = request.url.path
        if path in self.EXEMPT_PATHS or any(path.startswith(p) for p in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Check API key in header
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Missing API key. Include X-API-Key header."
            )
        
        if api_key != settings.api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key."
            )
        
        return await call_next(request)
