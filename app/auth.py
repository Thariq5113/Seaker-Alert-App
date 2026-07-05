"""
Minimal role-based access control (RBAC):

- Viewer role: implicit, anyone with the dashboard URL can view metrics,
  history, and alerts (read-only) — no login required.
- Admin role: required to change thresholds. Uses HTTP Basic Auth, which
  the browser handles natively (a login popup appears automatically the
  first time an admin action is attempted).

This is intentionally lightweight — no user database, no sessions — but
it is a real, working access boundary between "can view" and "can
reconfigure", which is what the assignment's bonus asks for.
"""
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from . import config

security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, config.ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, config.ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin credentials required to modify thresholds",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username