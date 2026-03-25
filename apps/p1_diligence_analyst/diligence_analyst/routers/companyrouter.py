import datetime
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.sql.annotation import Annotated

from diligence_core.middlewares.authmiddleware import verify_jwt_token
from diligence_core.supabaseconfig import supabaseconfig
from ..schemas import CompanyOut,CompanyCreate
router = APIRouter(prefix="/api/v1", tags=['company'])

@router.post('/company',response_model=CompanyOut)
async def create_company(payload:CompanyCreate,userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']

    if not user:
        raise HTTPException(status_code=401,detail="User does not exist")


    # {'email': 'bishtrahulsingh.dev.phone@gmail.com', 'email_verified': True, 'phone_verified': False,
    #  'sub': '2af5a9f1-24b9-4ee4-aad6-e6288f2b029d'} user looks like this
    supabase_client = supabaseconfig.supabase_client

    print(user)
    try:
        res = await (
            supabase_client
            .postgrest
            .auth(token)  # <-- this is the key fix
            .from_('companies')
            .insert({
                'user_id': user['sub'],
                'name': payload.name,
                'ticker': payload.ticker or None,
                'sector': payload.sector or None
            }).execute())
        data = res.data[0]
        return CompanyOut(
            id=data.get('id'),
            name=data.get('name'),
            created_at=data.get('created_at')
        )
    except Exception as e:
        raise HTTPException(status_code=400,detail=str(e))
