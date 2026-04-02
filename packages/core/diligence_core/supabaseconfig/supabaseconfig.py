from supabase import AsyncClient, acreate_client

from diligence_core import settings

supabase_client:AsyncClient = None
supabase_admin:AsyncClient = None

async def init_supabase():
    global supabase_client,supabase_admin

    if supabase_client is None:
        supabase_client =await acreate_client(settings.SUPABASE_URL,settings.SUPABASE_ANON_KEY)

    if supabase_admin is None:
        supabase_admin = await acreate_client(settings.SUPABASE_URL,settings.SUPABASE_ADMIN_KEY)
