from fastapi import Request, HTTPException
from starlette import status
from diligence_core.supabaseconfig import supabaseconfig


async def verify_jwt_token(request:Request):
    supabase = supabaseconfig.supabase_client
    if request and request.headers:
        access_token = (
                request.cookies.get('access_token') or
                request.cookies.get('sb-access-token')
        )

        if not access_token:
            # check authorization header for token
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                access_token = auth_header[7:]

        if access_token:
            try:
                payload = await supabase.auth.get_claims(access_token)
                return {"user":payload.get('claims').get('user_metadata'),"access_token":access_token}
            except Exception:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="token expired or invalid")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="access token is missing")
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="something went wrong")

