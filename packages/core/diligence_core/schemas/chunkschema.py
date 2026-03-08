from pydantic import ConfigDict
from diligence_core.schemas.vectordbmetadataschema import MetadataSchema


class ChunkSchema(MetadataSchema):
    vector:list[float]
    model_config = ConfigDict(
        from_attributes=True
    )