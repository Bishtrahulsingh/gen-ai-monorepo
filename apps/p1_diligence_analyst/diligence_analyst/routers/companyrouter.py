from fastapi import APIRouter, HTTPException
from fastapi.params import Depends

from diligence_core.chunkingpipeline.documenttochunk import create_chunks_for_structured_data
from diligence_core.edgarfilefetching.accesssecfilings import get_10_k_filing, FilingDetails
from diligence_core.embeddings.embeddinggenerator import embed_context
from diligence_core.middlewares.authmiddleware import verify_jwt_token
from diligence_core.supabaseconfig import supabaseconfig
from diligence_core.vectordb.qdrantConfig import update_or_insert_chunk
from ..schemas import CompanyOut,CompanyCreate
from ..schemas.companyschema import SearchAndStore

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
    try:
        res = await (
            supabase_client
            .postgrest
            .auth(token)
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

@router.post("/search/company")
async def search_company_and_store(payload:SearchAndStore,userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']
    supabase_client = supabaseconfig.supabase_client

    if not user:
        raise HTTPException(status_code=401,detail="User does not exist")

    data = await get_10_k_filing(payload.ticker, year=payload.year)

    for filing_data in data:

        ticker = payload.ticker
        fiscal_year = filing_data['metadata'].fiscal_year

        try:
            res = await (
                supabase_client
                .postgrest
                .auth(token)
                .from_("companies")
                .select("id")
                .eq("ticker", ticker.upper())
                .eq("fiscal_year", fiscal_year)
                .limit(1)
                .execute()
            )

            if res.data:
                continue
            chunks,keywords = await create_chunks_for_structured_data(metadata=filing_data['metadata'], sections=filing_data['sections'])

            context_embeddings = await embed_context(chunks)
            await update_or_insert_chunk('sec_filings', chunks=context_embeddings)

            await (
                supabase_client
                .postgrest
                .auth(token)
                .from_('companies')
                .insert({
                    'name': filing_data['metadata'].company_name,
                    'ticker': payload.ticker,
                    'fiscal_year' : filing_data['metadata'].fiscal_year,
                    'keywords':keywords
                }).execute())
        except Exception as e:
            raise Exception(str(e))

    return {"status": 200, "detail": "document stored successfully"}