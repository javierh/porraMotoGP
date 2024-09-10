# porraMotoGP

## Project Description

This project is a Telegram bot designed to manage betting pools for MotoGP races. Users can place their bets via the bot, and it will keep track of all bets and results. This bot download all the data from the MotoGP API and store it in json files.

## Technologies Used

- Python
- Telegram Bot API

## Dependencies

To run this project, you need the following dependencies:

- `python-telegram-bot`
- `requests`

You can install the required Python packages using pip:

```bash
pip install python-telegram-bot requests
```

## Usage for a new season
Call the API endpoint 
```bash
https://api.motogp.pulselive.com/motogp/v1/results/seasons
```
to get the list of all the seasons available. Then, copy the season ID to your config.json file.

