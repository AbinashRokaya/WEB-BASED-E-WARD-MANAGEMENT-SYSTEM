from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import OAuth2PasswordBearer
from auth.jwt import verify_token
from schema.user_schema import TokenData, Action, Permission_Role, RoleSchema
from typing import Annotated, Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/login")


def get_current_user(
    access_token: Annotated[Optional[str], Cookie()] = None
):
    if not access_token:
        raise HTTPException(status_code=401, detail="Token missing")

    try:
        payload = verify_token(token=access_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    

    return TokenData(
    user_id=payload.get("user_id"),
    user_name=payload.get("user_name"),
    user_phone_number=payload.get("user_phone_number"),
    user_citizenship_number=payload.get("user_citizenship_number"),
    user_provience=payload.get("user_provience"),
    user_district=payload.get("user_district"),
    user_municipality=payload.get("user_municipality"),
    user_ward_number=payload.get("user_ward_number"),
    user_role=payload.get("user_role"),
    user_ward_id=payload.get("user_ward_id")
)


def require_permission(action: Action):
    def dependency(user=Depends(get_current_user)):
        role_val = user.user_role
        try:
            role_enum = role_val if isinstance(role_val, RoleSchema) else RoleSchema(role_val)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user role in token")

        allowed = Permission_Role.get(role_enum, set())
        if action not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"{role_enum} is not allowed to perform '{action}'"
            )
        return user
    return dependency