from flask import Flask
from flask_cors import CORS
from flask_restplus import Api

from api.namespaces import namespaces

app = Flask(__name__)

# Allow Cross Origin Requests
CORS(app)

app.config["NAME"] = "Health Security Net API"
app.config["SWAGGER_UI_DOC_EXPANSION"] = "list"
app.config["SWAGGER_UI_REQUEST_DURATION"] = True
app.config["RESTPLUS_MASK_SWAGGER"] = False
app.config["pg_config"] = {}

# define API
api = Api(
    app,
    version="1.1.0",
    title="Health Security Net application programming interface"
    " (API) documentation",
    contact_url="https://healthsecuritynet.org",
    description=(
        """This API is consumed by the Health Security Net site"""
        """ at <a target="_blank" href="https://healthsecuritynet.org">"""
        """https://healthsecuritynet.org</a>.<br/><br/>Note: Response models are not currently publicly available, and only exist in the form of TypeScript interfaces in the frontend source code (non-public). If you have any accessibility issues or questions about the data, please contact us at <a href="https://healthsecuritynet.org/contact/">https://healthsecuritynet.org/contact/</a>."""
    ),
)

try:
    for ns in namespaces:
        api.add_namespace(ns)
except Exception:
    print(
        "Could not add namespaces, assuming they are already added"
        " and continuing"
    )
