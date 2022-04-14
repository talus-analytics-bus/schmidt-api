## 🚀 Quick start
Written by Mike Van Maele (mvanmaele@talusanalytics.com)

1.  **Clone the AWS database locally to use in development.**

    In the MacOS terminal, clone the current production database by doing
    ```
    bash sh/clone-db-schmidt.sh [YOUR_LOCAL_PG_USERNAME] schmidt schmidt-local
    ```



2.  **Create a config.ini file.**

    Create a file `config.ini` in the root directory containing information to connect to your local database, similar to the following:

    ```
    [DEFAULT]
    username=[YOUR_LOCAL_PG_USERNAME]
    host=localhost
    password=[YOUR_LOCAL_PG_PASS]
    database=schmidt-local
    ```


3.  **Install packages**

    - If using `pipenv` do `pipenv install --python=3.7.13 --dev --ignore-pipfile` to install Python packages and skip to the next section. Otherwise, continue.
    - Create a virtual environment for the project using `venv` (follow [this checklist](https://github.com/talus-analytics-bus/talus-intranet-react/wiki/Setting-up-a-Python-virtual-environment) for instructions if you're unsure).
    - Activate the virtual environment.
    - Install Python packages by doing `pip install -r requirements.txt`.


4. **Start API server**

    Do `pipenv run python application.py` from the project root directory. Check `localhost:5002` for the API server.
