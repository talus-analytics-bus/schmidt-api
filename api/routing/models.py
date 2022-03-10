from api.routing.routes import api
from flask_restplus import fields
ItemFilter = api.model(
    "ItemFilter",
    {
        "key_topics": fields.List(
            cls_or_instance=fields.String(),
            example=["International aid / collaboration"],
        ),
        "covid_tags": fields.List(
            cls_or_instance=fields.String(),
            example=["Healthcare capacity"],
        ),
        
    },
)

# {
#   "filters": {
#     "author.type_of_authoring_organization": ["Non-governmental organization"],
#     "years": [2019],
#     "key_topics": ["Disease surveillance / detection"],
#     "covid_tags": ["Healthcare capacity"],
#     "author.id": [43],
#     "event.name": ["COVID-19"],
#     "funder.name": ["Centers for Disease Control and Prevention (US)"],
#     "type_of_record": ["Report"]
#   }
# }


ItemBody = api.model(
    "ItemBody",
    {
        "filters": fields.Nested(ItemFilter),
    },
)