# MotoGP Prediction Bot

MotoGP Prediction Bot is a Telegram bot that allows users to make predictions for MotoGP races. The bot provides functionalities to manage predictions, view race schedules, and more.

## Features

- Make predictions for upcoming MotoGP races.
- View race schedules and results.
- Admin functionalities to update data.

## Changelog

### v1.3.0 (2025-03-07)

- Refactor code to improve readability and stability.
- Store user predictions in a google sheet.
- Users can bet on sprint and race separately.

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
- Google Sheet API key

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

4. Create your google_credentials.json file with the Google Sheet API key.

5. Upload the xlsx file to your Google Sheet and get the URL of the sheet to set it in the main.py file.

6. Set all the environment variables in the main.py file.

7. Run the bot:
    Using Python
    
    ```sh
    python3 main.py
    ```

# Porra MotoGP Bot

Bot de Telegram para gestionar porras de MotoGP.

## Requisitos

- Python 3.8 o superior
- MySQL 5.7 o superior
- Cuenta de Telegram

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:
```
