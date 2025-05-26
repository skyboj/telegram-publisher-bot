# Telegram Article Generator Bot

This bot helps you generate and publish articles to WordPress automatically. It uses OpenAI's GPT-3.5 for article generation and Unsplash for high-quality images. The bot is specifically optimized for content about Scotland, particularly Edinburgh and surrounding areas.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file based on `.env.example` and add your API keys:
- Get a Telegram bot token from @BotFather
- Get an OpenAI API key from https://platform.openai.com
- Get a WordPress OAuth token from your WordPress site
- Get an Unsplash access key from https://unsplash.com/developers

3. Configure WordPress settings in `.env`:
```
WORDPRESS_SITE_URL=your_wordpress_site_url
WORDPRESS_OAUTH_TOKEN=your_oauth_token
WORDPRESS_CATEGORIES=comma,separated,category,ids
```

4. Run the bot:
```bash
python bot.py
```

## Usage

1. Start a chat with your bot using the `/start` command
2. You can:
   - Send a single topic for one article
   - Send a numbered list of topics to process them sequentially

Example of a topic list:
```
1. Best Coffee Shops in Edinburgh
2. Hidden Gems of the Royal Mile
3. Day Trips from Edinburgh
4. Edinburgh's Secret Gardens
5. Best Viewpoints in the City
```

3. For each topic, the bot will:
   - Generate an SEO-optimized article using ChatGPT
   - Find a relevant image from Unsplash
   - Schedule publication on WordPress for 6:03 AM Edinburgh time
   - Send you the article URL and scheduled publication date

## Features

- Article generation with proper structure (title, subtitle, introduction, body, conclusion)
- SEO optimization for Scottish/Edinburgh content
- Automatic image selection from Unsplash
- WordPress integration with scheduled publishing
- Support for processing multiple topics in sequence
- Smart scheduling system (avoids scheduling conflicts)
- HTML formatting with proper WordPress blocks
- Comprehensive error handling and logging
- `/kill` command for managing bot instances

## Commands

- `/start` - Get welcome message and usage instructions
- `/kill` - Terminate all running bot instances (useful for updates)
