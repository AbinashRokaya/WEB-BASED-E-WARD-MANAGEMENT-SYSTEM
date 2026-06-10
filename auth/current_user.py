from fastapi import Depends, HTTPException, status,Cookie
from fastapi.security import OAuth2PasswordBearer
from auth.jwt import verify_token
from schema.user_schema import TokenData,Action,Permission_Role,RoleSchema
from typing import Annotated

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/login")

from typing import Annotated
from fastapi import Cookie

def get_current_user(
    access_token: Annotated[str | None, Cookie()] = None
):
    
    if access_token is None:
        raise HTTPException(
            status_code=401,
            detail="Token missing"
        )

    payload = verify_token(token=access_token)

    user_name = payload.get("user_name")
    user_email = payload.get("user_email")
    user_id = payload.get("user_id")
    user_role = payload.get("user_role")
    

    return TokenData(
        user_name=user_name,
        user_email=user_email,
        user_id=user_id,
        user_role=user_role
    )


def require_permission(action:Action):
    def dependency(user=Depends(get_current_user)):
        role=user.user_role
        if action not in Permission_Role.get(RoleSchema(role),set()):
             raise HTTPException(
                status_code=403,
                detail=f"{role} is not allowed to perform '{action}'"
            )
        return user
    return dependency