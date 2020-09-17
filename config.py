##
# # API configuration file.
##

# Standard libraries
# import sys

# Third party libraries
from configparser import ConfigParser
# from argparse import ArgumentParser
from sqlalchemy import create_engine
import boto3
import json
import pprint
import os


# retrieve AWS Secret, used to define connection string for database in
# production mode
def get_secret(
    secret_name="talus_dev_rds_secret",
    region_name="us-west-1",
    profile='default'
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
    if os.environ.get('PROD') == 'true':
        session = boto3.session.Session()
    else:
        session = boto3.session.Session(profile_name=profile)

    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    # attempt to retrieve the secret, and throw a series of exceptions if the
    # attempt fails. See link below for more information.
    # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        print(e)
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the
            # provided KMS key.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the
            # current state
            # of the resource.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            raise e
    else:
        # Decrypts secret using the associated KMS CMK.
        # Depending on whether the secret is a string or binary, one of these
        # fields will be populated.
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return secret
        else:
            decoded_binary_secret = base64.b64decode(
                get_secret_value_response['SecretBinary']
            )
            return decoded_binary_secret

#


class Config:
    """Config class, instantiated in api/setup.py.

    Parameters
    ----------
    config_file : type
        Description of parameter `config_file`.

    Attributes
    ----------
    db : type
        Description of attribute `db`.
    engine : type
        Description of attribute `engine`.
    debug : type
        Description of attribute `debug`.

    """

    def __init__(self, config_file):

        # Create a new config parser and read the config file passed to Config
        # instance.
        cfg = ConfigParser()
        cfg.read(config_file)

        no_config = (len(cfg) == 1 and len(cfg['DEFAULT']) == 0)
        self.db = dict()
        if os.environ.get('PROD') != 'true' and not no_config:
            # if not no_config:
            for d in cfg['DEFAULT']:
                self.db[d] = cfg['DEFAULT'].get(d)
        else:
            secret = json.loads(get_secret())
            self.db['username'] = secret['username']
            self.db['host'] = secret['host']
            self.db['password'] = secret['password']
            self.db['database'] = 'schmidt'

        # Define database engine based on db connection parameters.
        self.engine = create_engine(f"postgresql+psycopg2://{self.db['username']}:{self.db['password']}@{self.db['host']}:5432/{self.db['database']}",
                                    use_batch_mode=True)

        # Debug mode is not used.
        self.debug = False

    # Instance methods
    # To string
    def __str__(self):
        return pprint.pformat(self.__dict__)

    # Get item from config file (basically, a key-value pair)
    def __getitem__(self, key):
        return self.__dict__[key]

    # Set item from config file
    def __setitem__(self, key, value):
        self.__dict__[key] = value

    # # Define argument parser to collect command line arguments from the user,
    # # if provided.
    # @staticmethod
    # def collect_arguments():
    #     parser = ArgumentParser(description='Test', add_help=False)
    #     parser.add_argument('-h', '--pg-host')
    #     parser.add_argument('-p', '--pg-port', type=int)
    #     parser.add_argument('-d', '--pg-dbname')
    #     parser.add_argument('-u', '--pg-user')
    #     parser.add_argument('-w', '--pg-password')
    #     parser.add_argument('--help', action='help', help="""Please check the file config.py
    #                         for a list of command line arguments.""")
    #
    #     return parser.parse_args()
