from api.routing.routes import api
from flask_restplus import fields

ItemFilter = api.model(
    "ItemFilter",
    {
        "years": fields.List(
            cls_or_instance=fields.String(),
            example=["2020"],
            description="Define a list of years, or provide a single-element list"
            " with the value `range_YYYY_YYYY` where you replace YYYY with a"
            " start year and an end year.",
        ),
        "key_topics": fields.List(
            cls_or_instance=fields.String(),
            example=["Medical preparedness / emergency response"],
            description="One or more of: 'Disease surveillance / detection',"
            " 'International aid / collaboration',"
            " 'Medical preparedness / emergency response',"
            " 'Other', 'Strategic planning', 'Threat / risk awareness'",
        ),
        "covid_tags": fields.List(
            cls_or_instance=fields.String(),
            example=["Risk and policy communication"],
            description="COVID-relevant tags. One or more of: 'Antimicrobial resistance (AMR)', 'Coverage of healthcare costs', 'Crisis standards of care', 'Direct financial relief', 'Disease characteristics and outcomes', 'Economic impacts and support', 'Employment regulations', 'EUAs and medical authorizations', 'Healthcare capacity', 'Healthcare worker impacts and support', 'Health disparities and disproportionate impacts', 'Hospital acquired infections', 'Intentional biological attacks', 'Intergovernmental policy and international governance', 'International financing', 'Key public health emergency response plans', 'Laboratory biosafety and biosecurity', 'Laboratory capacity', 'Legal frameworks for public health emergencies', 'Long term care facilities and nursing homes', 'Medical countermeasures', 'N/A', 'Non-COVID health impacts', 'Nonpharmaceutical interventions', 'Origin of SARS-CoV-2', 'Pandemic preparedness and history', 'Prisons, correctional facilities, and jails', 'Public health data requirements and systems', 'Response frameworks', 'Risk and policy communication', 'School closures and reopening', 'Sub-national or local public health policies', 'Supply shortages and supply chain impacts', 'Testing and contact tracing', 'Travel and repatriation'",
        ),
        "event.name": fields.List(
            cls_or_instance=fields.String(),
            example=["COVID-19"],
            description="Name of public health event. One or more of: '2001 Anthrax attacks (Amerithrax)', '2003 SARS', '2005 H5N1', '2009 H1N1', '2013 MERS', '2014-2016 Ebola (West Africa)', '2016 Zika', '2018-2020 Ebola (DRC)', 'COVID-19', 'N/A'",
        ),
        "type_of_record": fields.List(
            cls_or_instance=fields.String(),
            example=["Report"],
            description="One or more of: 'Executive order', 'Government action', 'Journal paper', 'Report', 'Simulation or Exercise', 'Situation report', 'Strategy / Implementation plan', 'UN process document'",
        ),
        "funder.name": fields.List(
            cls_or_instance=fields.String(),
            example=["Funder not specified"],
            description="One or more names of a funder of Items",
        ),
        "author.id": fields.List(
            cls_or_instance=fields.String(),
            example=[184],
            description="One or more Author IDs",
        ),
        "author.type_of_authoring_organization": fields.List(
            cls_or_instance=fields.String(),
            example=["Non-governmental organization"],
            description="One or more of: 'Academic', 'Academic journal', 'Intergovernmental organization', 'Local government', 'National / federal government', 'Non-governmental organization', 'Other', 'Private sector'",
        ),
    },
)

# {
#     "filters": {
#         "years": ["2020"],
#         "key_topics": ["Medical preparedness / emergency response"],
#         "covid_tags": ["Risk and policy communication"],
#         "event.name": ["COVID-19"],
#         "type_of_record": ["Report"],
#         "funder.name": ["Funder not specified"],
#         "author.id": [184],
#         "author.type_of_authoring_organization": [
#             "Non-governmental organization"
#         ],
#     }
# }


ItemBody = api.model(
    "ItemBody",
    {
        "filters": fields.Nested(ItemFilter),
    },
)


SearchResponse = api.model(
    "SearchResponse",
    {
        "page": fields.Integer(),
        "pagesize": fields.Integer(),
        "num_pages": fields.Integer(),
        "total": fields.Integer(
            description="The total number of Items (not just on this page)"
        ),
        "num": fields.Integer(description="Same as `total`"),
        "data": fields.List(cls_or_instance=fields.Arbitrary(), example=[{}]),
    },
)
