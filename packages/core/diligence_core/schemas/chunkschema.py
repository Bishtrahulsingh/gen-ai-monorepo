from diligence_core.schemas.vectordbmetadataschema import MetadataSchema


class ChunkSchema(MetadataSchema):
    vector:list[float]