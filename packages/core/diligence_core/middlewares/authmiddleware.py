from fastapi import Request, Response, HTTPException
from starlette import status
from diligence_core.supabaseconfig import supabaseconfig


async def verify_jwt_token(request: Request, response: Response):
    supabase = supabaseconfig.supabase_client
    access_token = (
        request.cookies.get('access_token') or
        request.cookies.get('sb-access-token')
    )

    if not access_token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            access_token = auth_header[7:]

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is missing"
        )
    try:
        payload = await supabase.auth.get_claims(access_token)
        return {
            "user": payload.get('claims').get('user_metadata'),
            "access_token": access_token
        }

    except Exception:
        refresh_token = request.cookies.get('refresh_token')

        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again."
            )

        try:
            refreshed = await supabase.auth.refresh_session(refresh_token)

            response.set_cookie(
                key="access_token",
                value=refreshed.session.access_token,
                httponly=True,
                samesite="Lax",
                secure=False,
                max_age=60 * 60 * 24
            )
            response.set_cookie(
                key="refresh_token",
                value=refreshed.session.refresh_token,
                httponly=True,
                samesite="Lax",
                secure=False,
                max_age=60 * 60 * 24 * 7
            )

            return {
                "user": refreshed.user.user_metadata,
                "access_token": refreshed.session.access_token
            }

        except Exception:
            response.delete_cookie("access_token")
            response.delete_cookie("refresh_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again."
            )