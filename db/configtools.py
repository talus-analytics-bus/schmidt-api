import os
import boto3
import base64
import logging
import json
from botocore.exceptions import ClientError
from typing import List


logger = logging.getLogger(__name__)


def get_secret(
    secret_name="schmidt_rds_secret",
    region_name="us-east-1",
    profile="default",
):
    """Retrieve an AWS Secret value, given valid connection parameters and
    assuming the server has access to a valid configuration profile.

    Parameters
    ----------
    secret_name : str
        The name of the secret to be retrieved from AWS Secrets.
    region_name : str
        The name of the region that secret is housed in.
    profile : str
        The name of the profile that should be used to connect to AWS Secrets.

    Returns
    -------
    dict
        The secret, as a set of key/value pairs.

    """

    # Create a Secrets Manager client using boto3
    if os.environ.get("PROD") == "true":

        session = boto3.session.Session()
    else:
        session = boto3.session.Session(profile_name=profile)

    client = session.client(service_name="secretsmanager", region_name=region_name)

    # attempt to retrieve the secret, and throw a series of exceptions if the
    # attempt fails. See link below for more information.
    # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.error(e)
        if e.response["Error"]["Code"] == "DecryptionFailureException":
            # Secrets Manager can't decrypt the protected secret text using the
            # provided KMS key.
            raise e
        elif e.response["Error"]["Code"] == "InternalServiceErrorException":
            # An error occurred on the server side.
            raise e
        elif e.response["Error"]["Code"] == "InvalidParameterException":
            # You provided an invalid value for a parameter.
            raise e
        elif e.response["Error"]["Code"] == "InvalidRequestException":
            # You provided a parameter value that is not valid for the
            # current state
            # of the resource.
            raise e
        elif e.response["Error"]["Code"] == "ResourceNotFoundException":
            # We can't find the resource that you asked for.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these
        # fields will be populated.
        if "SecretString" in get_secret_value_response:
            secret = get_secret_value_response["SecretString"]
            return secret
        else:
            decoded_binary_secret = base64.b64decode(
                get_secret_value_response["SecretBinary"]
            )
            return decoded_binary_secret


def get_config_from_env():
    d = dict()
    d["username"] = os.getenv("username")
    d["password"] = os.getenv("password")
    d["database"] = os.getenv("database")
    d["host"] = os.getenv("host")
    return d


def load_db_config():
    """Load database configuration from config file if available, return empty
    dict if not available

    Returns:
        dict: Configuration
    """

    # get conn params from env
    env_params = get_config_from_env()
    keys: List[str] = ["username", "password", "database", "host"]
    if not all(k in env_params for k in keys):
        raise ValueError(
            "Must define all env vars for PostgreSQL connection: " + ",".join(keys)
        )

    # get secret params
    secret = json.loads(
        get_secret(secret_name=(os.environ.get("SECRET_NAME", "schmidt_rds_secret")))
    )

    # overwrite secret params with env params
    overwrite_env_with_secret: bool = all(
        env_params[k] in (None, "")
        for k in env_params
        if k not in ("password", "database")
    )
    conn_params = {
        k: secret[k]
        if (overwrite_env_with_secret and k in secret) or env_params.get(k) is None
        else env_params[k]
        for k in keys
    }
    return conn_params
