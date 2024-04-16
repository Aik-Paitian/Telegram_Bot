# Canvas Coursework Bot

## Introduction
This Python-based bot is designed to facilitate students and educators from Glendale Community College and Los Angeles Community College by automating the retrieval of course assignments and due dates from the Canvas platform. It leverages the Canvas API with OAuth2 authentication and utilizes multithreading to enhance efficiency.

## Key Features
- **OAuth2 Authentication**: Securely connects to Canvas API to fetch user-specific data.
- **Efficient Multithreading**: Handles multiple users’ requests in parallel, providing quick responses.
- **Scheduled Notifications**: Sends out due date reminders for assignments and course grades below a threshold, directly through Telegram.
- **Support for Multiple Schools**: Configured to work with both Glendale Community College and Los Angeles Community College.

## How it Works
- The bot interacts with users via Telegram, providing an interface to request assignment details and course grades.
- Users can select from predefined query options to fetch assignments due within 24, 48 hours, or a week, and to check course grades.
- The bot efficiently processes these requests using asynchronous operations and Python's multithreading capabilities.

## Configuration
- A `tokens.json` file is used to store user information and authentication tokens for API access.

## Usage
1. Users interact with the bot on Telegram to request information about their coursework.
2. The bot receives the command and enqueues it for processing.
3. Parallel workers process the requests, fetching data from Canvas and replying to the user with relevant information.
4. Users receive notifications about assignments or grades that need attention.

## Requirements
- Python 3.x
- `httpx` library for HTTP requests in an async manner
- `apscheduler` library for job scheduling
- `pytz` library for timezone conversions
- `python-telegram-bot` library for Telegram bot interactions

To install the required libraries, use pip:

```terminal
pip install httpx apscheduler pytz python-telegram-bot
```
## Setup
To run the bot, you'll need to set up the following environment variables:
- `BOT_API`: Your Telegram bot API token.

Additionally, ensure your `tokens.json` file is populated with the correct user data and OAuth2 tokens for the Canvas API.

## Contributing
Contributions are welcome to support more features or colleges. Please feel free to fork the repository, make changes, and submit a pull request.

## Acknowledgements
Special thanks to Glendale Community College and Los Angeles Community College for providing the resources and API access that made this project possible.
