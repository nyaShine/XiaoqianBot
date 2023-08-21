#!/bin/sh

# Check for required environment variables
missing_env_var_flag=0
for var in DB_USER SQL_DB_PASS REDIS_DB_PASS FROM_EMAIL EMAIL_PASSWORD AES_KEY
do
    if [ -z "$(eval echo \$$var)" ]
    then
        echo "$var not set. Please set this environment variable and run this script again."
        missing_env_var_flag=1
    fi
done

# If any environment variable is not set, exit
if [ "$missing_env_var_flag" -eq 1 ]
then
    exit 1
fi

# Check if Redis is installed
if ! command -v redis-cli > /dev/null 2>&1
then
    echo "Redis not found. Please install Redis."
    exit 1
fi

# Check if MySQL is installed
if ! command -v mysql > /dev/null 2>&1
then
    echo "MySQL not found. Please install MySQL."
    exit 1
fi

# Find Python command
for cmd in python python3
do
    if command -v $cmd > /dev/null 2>&1
    then
        PYTHON_CMD=$cmd
        break
    fi
done

if [ -z "$PYTHON_CMD" ]
then
    echo "Python not found. Please install Python."
    exit 1
fi

$PYTHON_CMD check_requirements.py requirements.txt
if [ $? -eq 1 ]
then
    echo "Installing missing packages..."
    $PYTHON_CMD -m pip install -r requirements.txt
fi
$PYTHON_CMD main.py
