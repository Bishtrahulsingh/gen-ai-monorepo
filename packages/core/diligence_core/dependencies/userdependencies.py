from fastapi import Request, HTTPException
from starlette import status

from diligence_core.supabaseconfig import supabaseconfig


async def get_current_user(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not logged in")
    supabase_client = supabaseconfig.supabase_client
    current_user = await supabase_client.auth.get_user(access_token)
    return current_user.user