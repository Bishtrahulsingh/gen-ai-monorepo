from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from diligence_core.chunkingpipeline import read_pdf, create_chunks
from diligence_core.embeddings.embeddinggenerator import embed_context
from diligence_core.middlewares.authmiddleware import verify_jwt_token
from diligence_core.vectordb.qdrantConfig import update_or_insert_chunk
from ..schemas import DocumentCreate,DocumentOut
from diligence_core.supabaseconfig import supabaseconfig
from ..schemas.documentschema import StoredDocument, DocumentYearsRequest

router = APIRouter(prefix='/api/v1',tags=['documents'])

@router.post("/store/document",response_model=DocumentOut)
async def create_document(payload:DocumentCreate,userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']
    source = str(payload.source)
    supabase_client = supabaseconfig.supabase_client
    supabase_admin = supabaseconfig.supabase_admin
    try:
        company = await (
            supabase_admin
            .from_('companies')
            .select('ticker')
            .eq("id",payload.company_id)
            .limit(1)
            .execute()
        )

        ticker = company.data[0]['ticker']

        if not ticker:
            raise Exception('company not found')

        res = await (
            supabase_admin
            .from_('documents')
            .insert({
                'title': payload.title,
                'company_id': str(payload.company_id),
                'doc_type': payload.doc_type,
                'source_url': source,
                'fiscal_year': payload.fiscal_year,
                'ticker': ticker
            })
            .execute()
        )
        data = res.data[0]
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="failed to store document")

    chunks,headings = await create_chunks(file_path=source,ticker=ticker,fiscal_year=payload.fiscal_year, document_id=data['id'], company_id=payload.company_id)

    for chunk in chunks:
        print(chunk, end="\n-----------------------\n")
    context_embeddings = await embed_context(chunks)
    await update_or_insert_chunk('sec_filings',chunks=context_embeddings)
    await (
        supabase_admin
        .from_('documents')
        .update({'headings':headings})
        .eq('id',data['id'])
        .execute())

    return DocumentOut(
        id=data['id'],
        company_id=data['company_id'],
        title=data['title'],
        doc_type=data['doc_type'] or None,
        source=data['source_url'] or None,
        created_at = data['created_at'] or None
    )


@router.post('/storage/documents')
async def get_stored_documents(payload:StoredDocument, userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']

    if not user:
        raise Exception("user not logged in")

    supabase_admin = supabaseconfig.supabase_admin
    res = await (
        supabase_admin
        .from_('documents')
        .select('*')
        .eq('fiscal_year',payload.fiscal_year)
        .eq('ticker',payload.ticker)
        .execute()
    )

    return res.data

@router.post('/storage/documents/years')
async def get_year_of_stored_documents(payload:DocumentYearsRequest, userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']

    print("hello bro ")

    if not user:
        raise Exception("user not logged in")

    supabase_admin = supabaseconfig.supabase_admin
    res = await (
        supabase_admin
        .from_('documents')
        .select('fiscal_year')
        .eq('ticker',payload.ticker)
        .execute()
    )

    return list(set(item['fiscal_year'] for item in res.data))