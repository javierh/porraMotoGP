#!/bin/bash

echo "Importing riders..."
python3 get_pilots.py

echo "Importing circuits... (this can take a while)"
python3 get_circuits.py

echo "Importing sessions..."
python3 get_sessions.py

echo "Importing results..."
python3 get_results.py

echo "Importing mrgrid..."
python3 get_mrgrid.py

echo "Data import completed."
