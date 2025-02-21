# schemas/preferences_schema.py
from marshmallow import Schema, fields

class PreferencesSchema(Schema):
    user_id = fields.Str(required=True)
    preferences = fields.Dict(required=True)

preferences_schema = PreferencesSchema()
