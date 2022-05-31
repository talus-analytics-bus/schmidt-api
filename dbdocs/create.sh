#!/bin/sh
# Generate database docs using SchemaSpy
JAVA_PATH=${1:-"java"} # the first argument is the path to the Java executable
CONFIG_PATH=${2:-"./config/config.file"}
"$JAVA_PATH" -jar ./schemaspy/schemaspy-6.1.0.jar -configFile "$CONFIG_PATH" -vizjs
