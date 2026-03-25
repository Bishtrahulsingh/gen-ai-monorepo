
from fastapi import APIRouter, Depends, HTTPException
from diligence_core.chunkingpipeline import read_pdf, create_chunks
from diligence_core.embeddings.embeddinggenerator import embed_context
from diligence_core.middlewares.authmiddleware import verify_jwt_token
from diligence_core.vectordb.qdrantConfig import update_or_insert_chunk
from ..schemas import DocumentCreate,DocumentOut
from diligence_core.supabaseconfig import supabaseconfig

router = APIRouter(prefix='/api/v1',tags=['documents'])

@router.post("/store/document",response_model=DocumentOut)
async def create_document(payload:DocumentCreate,userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']
    source = str(payload.source)
    supabase_client = supabaseconfig.supabase_client

    try:
        res = await (
            supabase_client
            .postgrest
            .auth(token)
            .from_('documents')
            .insert({
                'user_id': user['sub'],
                'title': payload.title,
                'company_id': str(payload.company_id),
                'doc_type': payload.doc_type,
                'source_url': source,
            }).execute())

        data = res.data[0]
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="failed to store document")

    chunks = await create_chunks(file_path=source, user_id=user['sub'], document_id=data.id, company_id=payload.company_id)
    context_embeddings = await embed_context(chunks)
    await update_or_insert_chunk('sec_filings',chunks=context_embeddings)

    return DocumentOut(
        id=data.id,
        company_id=data.company_id,
        title=data.title,
        doc_type=data.doc_type or None,
        source=data.source_url or None,
        created_at = data.created_at or None
    )