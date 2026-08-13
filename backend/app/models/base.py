from typing import Optional
from beanie import Document, PydanticObjectId
from pydantic import Field


class AppDocument(Document):
    """
    Base class for every collection in this app.

    Why this exists: FastAPI's default JSON encoder (jsonable_encoder) serializes
    Pydantic models using field ALIASES by default. Beanie's Document base class
    defines its id field as `Field(alias="_id")` (so it maps correctly to Mongo's
    _id on the way in) — but that same alias then leaks out into every API
    response as "_id" instead of "id", unless we tell Pydantic to use a
    *different* alias specifically for serialization.

    Redeclaring the id field here with `serialization_alias="id"` keeps "_id"
    for reading from Mongo (via `alias`) while making every JSON response the
    frontend receives use "id" as expected. Every Document subclass in this
    app inherits from AppDocument instead of Document directly so this applies
    everywhere consistently.
    """
    id: Optional[PydanticObjectId] = Field(default=None, alias="_id", serialization_alias="id")
