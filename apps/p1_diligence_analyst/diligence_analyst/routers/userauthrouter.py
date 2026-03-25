from fastapi import APIRouter, HTTPException, Response, Depends
from starlette import status
from supabase_auth.errors import AuthApiError
from diligence_core.schemas.userschema import UserAuth
from diligence_core.supabaseconfig import supabaseconfig

router = APIRouter(prefix="/auth")


@router.post("/register")
async def register_user(payload: UserAuth):
    email = payload.email
    password = payload.password

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and Password are required")

    client = supabaseconfig.supabase_client
    try:
        response = await client.auth.sign_up({
            "email": email,
            "password": password
        })

        if not response.user:
            raise HTTPException(status_code=400, detail="Registration failed")

    except AuthApiError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return {
        "message": "user registered successfully",
        "data": {
            "user_id": response.user.id
        }
    }


@router.post("/login")
async def login_user(payload: UserAuth,res: Response):
    email = payload.email
    password = payload.password

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and Password are required")

    client = supabaseconfig.supabase_client

    try:
        response = await client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not response.user or not response.session:
            raise HTTPException(status_code=401, detail="Authentication failed")

        res.set_cookie(
            key="access_token",
            value=response.session.access_token,
            httponly=True,
            samesite="Lax",
            secure=False,
            max_age=60*60*24
        )

        res.set_cookie(
            key="refresh_token",
            value=response.session.refresh_token,
            httponly=True,
            samesite="Lax",
            secure=False,
            max_age=60*60*24*7
        )

    except AuthApiError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    return {
        "message": "user logged in",
        "data": {
            "user_id": response.user.id
        }
    }