# Fooocus Telegram Bot

A Telegram bot interface for [Fooocus](https://github.com/lllyasviel/Fooocus) (via [Fooocus-API](https://github.com/mrhan1993/Fooocus-API)).

## Features

*   **Image Generation**: Generate images from text prompts directly in Telegram.
*   **Model Selection**: Browse and select available base models from your Fooocus instance.
*   **Localhost Support**: Automatically handles image downloads from local Fooocus instances to send to Telegram.

## Prerequisites

*   Python 3.8+
*   A running instance of **Fooocus** with **Fooocus-API** enabled.
    *   Typically run with `python main.py --nowebui`
*   A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd fooocus-tg-bot
    ```

2.  **Create a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**:
    *   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    *   Edit `.env` and add your `BOT_TOKEN`.
    *   Adjust `FOOOCUS_IP` and `FOOOCUS_PORT` if your API is not running on `127.0.0.1:8888`.

## Usage

1.  **Start the bot**:
    ```bash
    ./venv/bin/python bot.py
    ```

2.  **Commands**:
    *   `/start` - Welcome message and help.
    *   `/models` - Select a base model.
    *   `/generate <prompt>` - Generate an image.
    *   Simply sending text will also trigger generation.

## Troubleshooting

*   **Connection Refused**: Ensure Fooocus API is running. If running locally, ensure `FOOOCUS_IP` is set to `127.0.0.1` or `localhost`.
*   **Model Selection Fails**: Ensure you are running the latest version of the bot which uses index-based callbacks to avoid Telegram length limits.
