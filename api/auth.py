"""
Simple authentication utilities for admin access.
"""

import os
import hashlib
import secrets
from typing import Optional
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# Simple authentication setup
security = HTTPBasic()

def get_admin_credentials() -> tuple[str, str]:
    """Get admin credentials from environment or use defaults."""
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "changeme123")
    return username, password

def verify_admin_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """Verify admin credentials."""
    admin_username, admin_password = get_admin_credentials()
    
    # Use constant-time comparison to prevent timing attacks
    username_correct = secrets.compare_digest(credentials.username, admin_username)
    password_correct = secrets.compare_digest(credentials.password, admin_password)
    
    if not (username_correct and password_correct):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

def require_admin_auth(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """Dependency to require admin authentication."""
    return verify_admin_credentials(credentials)

# Alternative: IP-based restriction
def get_allowed_admin_ips() -> list[str]:
    """Get allowed admin IP addresses from environment."""
    ips_str = os.getenv("ADMIN_ALLOWED_IPS", "127.0.0.1,::1")
    return [ip.strip() for ip in ips_str.split(",")]

def verify_admin_ip(request: Request) -> bool:
    """Verify request comes from allowed admin IP."""
    allowed_ips = get_allowed_admin_ips()
    client_ip = request.client.host if request.client else None
    
    if client_ip not in allowed_ips:
        raise HTTPException(
            status_code=403,
            detail="Access denied: IP not authorized for admin access"
        )
    return True

def require_admin_ip(request: Request) -> bool:
    """Dependency to require admin IP."""
    return verify_admin_ip(request)