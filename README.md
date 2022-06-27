## 🚀 Quick start
Written by Mike Van Maele (mvanmaele@talusanalytics.com)

1.  **Clone the AWS database locally to use in development.**

    In the MacOS terminal, clone the current production database by doing
    ```
    bash sh/clone-db-schmidt.sh [YOUR_LOCAL_PG_USERNAME] schmidt schmidt-local
    ```



2.  **Create a `.env` file.**

    Create a file `.env` in the root directory containing information to connect to your local database, similar to the following:

    ```
    username=[local postgres username]
    host=localhost
    password=
    database=schmidt-local
    AIRTABLE_API_KEY=[your key]
    AIRTABLE_BASE_ID=appLd31oBE5L3Q3cs
    ```


3.  **Install packages**

    - If using `pipenv` do `pipenv install --python=3.7 --dev --ignore-pipfile` to install Python packages and skip to the next section. Otherwise, continue.
    - Create a virtual environment for the project using `venv` (follow [this checklist](https://github.com/talus-analytics-bus/talus-intranet-react/wiki/Setting-up-a-Python-virtual-environment) for instructions if you're unsure).
    - Activate the virtual environment.
    - Install Python packages by doing `pip install -r requirements.txt`.


4. **Start API server**

    Do `pipenv run python application.py` from the project root directory. Check `localhost:5002` for the API server.
