## 🚀 Quick start

1.  **Clone the AWS database locally to use in development.**

    Get a shell script and database server password from one of the below individuals to clone the Schmidt AWS RDS database locally. It will return data much faster in development than the production database.

    - Mike (mvanmaele@talusanalytics.com)


2.  **Create a config.ini file.**

    Create a file `config.ini` in the root directory containing information to connect to your local database, similar to the following:

    ```
    [DEFAULT]
    username=mikevanmaele
    host=localhost
    password=
    database=schmidt
    ```


3.  **Install packages**

    Do `pipenv --python=3.7` and then `pipenv install -r requirements.txt` from the project root directory.


4. **Start API server**

    Do `run python application.py` from the project root directory. Check `localhost:5002` for the API server.
