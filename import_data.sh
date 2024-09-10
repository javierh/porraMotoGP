#!/bin/bash

echo "Importing riders..."
python3 import_riders.py

echo "Importing circuits..."
python3 import_circuits.py

echo "Importing sessions..."
python3 import_sessions.py
