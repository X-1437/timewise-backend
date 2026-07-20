from bson import ObjectId


def to_object_id(value: str | ObjectId) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    return ObjectId(value)


def id_to_str(value: ObjectId | None) -> str | None:
    if value is None:
        return None
    return str(value)
