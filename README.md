# MotoGP Prediction Bot

MotoGP Prediction Bot is a Telegram bot that allows users to make predictions for MotoGP races. The bot provides functionalities to manage predictions, view race schedules, and more.

## Features

- Make predictions for upcoming MotoGP races.
- View race schedules and results.
- Admin functionalities to update data.

## Changelog

### v1.2.0 (2024-09-29)

- Correction on results calculation
- Correction on score calculation
- Exception handling on some files
- Added rules (and the command /rules) of the game to the bot
- Updated data.json with more information

### v1.1.0 (2024-09-16)

- Added Docker support with `Dockerfile` and `docker-compose.yml`.
- Implemented admin-only command `/update_data`.
- Improved error handling for missing sessions and races.
- Translated all texts to English.
- Added 

### v1.0.0 (2024-09-09)

- Initial release with basic functionalities:
  - Make predictions for races.
  - View race schedules.
  - Basic error handling.

## Requirements

- Python 3.9+
- Telegram Bot API token
- TimeZoneDB API key
- Google Maps API key

## Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/javierh/porraMotoGP.git
   cd porraMotoGP
   ```

2. Create a virtual environment and activate it:

   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the dependencies:

   ```sh
    pip install -r requirements.txt
    ```

4. Modify config_sample.json file with your configuration and rename to config.json

5. Run the import data script:

   ```sh
   bash import_data.sh
   ```

6. Run the bot:
    Using Python
    
    ```sh
    python3 main.py
    ```

Using Docker

   ```sh
   docker-compose build
   docker-compose up -d
   ```
