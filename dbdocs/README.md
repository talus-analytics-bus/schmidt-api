# [COVID AMP](https://covidamp.org/) database documentation
Interactive database documentation for the database that powers the [COVID Analysis and Mapping of Policies (AMP) site](https://covidamp.org).

## Getting started
Open the docs by cloning this repository to your device and opening the file [./docs/index.html](./docs/index.html) in a web browser.

## How do you make these docs?
Interactive documentation is currently generated automatically using the [SchemaSpy tool](https://schemaspy.org/) (v6.1).

## Updating the docs
Follow this checklist to update the docs found in directory `docs` using the [SchemaSpy tool](https://schemaspy.org/).
1. Download SchemaSpy as described at the [SchemaSpy site](https://schemaspy.org/).
1. Install the version of Java required by your version of SchemaSpy (see [SchemaSpy installation documentation](https://schemaspy.readthedocs.io/en/latest/installation.html))
1. Create file `config.file` based on `config-template.file` that populates the missing database connection values with the correct values, e.g., host (`host`), username (`u`), password (`p`).
1. Run shell script `create.sh` with shell command
    ```shell
    bash create.sh
    ```
1. When the script terminates, updated docs will be in the directory `docs`.

## How do I reuse this SchemaSpy-based system to document another database?
1. Make a copy of this repository
1. Install any required driver's JAR file to directory `jdbc` (this repository comes with a PostgreSQL driver)
1. Change parameters in your `./config/config.file` to point to the database you'd like to document
1. Delete the contents of directory `docs`
1. Run shell script `create.sh` with shell command
    ```shell
    bash create.sh
    ```
