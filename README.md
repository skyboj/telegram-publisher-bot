# Telegram Article Generator Bot

This bot helps you generate and publish articles to Medium automatically. It uses OpenAI's GPT-3.5 for article generation and DALL-E for image generation.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file based on `.env.example` and add your API keys:
- Get a Telegram bot token from @BotFather
- Get an OpenAI API key from https://platform.openai.com
- Get a Medium integration token from https://medium.com/me/settings/integrations

3. Run the bot:
```bash
python bot.py
```

## Usage

1. Start a chat with your bot
2. Send a topic for the article
3. The bot will:
   - Generate an article using ChatGPT
   - Create an image using DALL-E
   - Publish the article to Medium
   - Send you the link to the published article

## Features

- Article generation with proper structure (title, subtitle, introduction, body, conclusion)
- Automatic image generation
- HTML formatting for Medium
- Sequential processing (each step waits for the previous one to complete)
- Error handling and logging
