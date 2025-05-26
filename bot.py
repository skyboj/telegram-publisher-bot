import os
import logging
import json
from datetime import datetime, timedelta
import pytz
import re
from typing import Dict, Any
import psutil
import sys

# Third-party imports
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from openai import OpenAI

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

class ArticleGenerator:
    def __init__(self):
        """Initialize the ArticleGenerator with API clients and configuration."""
        # Initialize OpenAI client
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # WordPress configuration
        self.wp_site_url = os.getenv('WORDPRESS_SITE_URL').rstrip('/')
        self.wp_oauth_token = os.getenv('WORDPRESS_OAUTH_TOKEN')
        
        # For WordPress.com sites, we use the public-api.wordpress.com endpoint
        if '.wordpress.com' in self.wp_site_url:
            site_name = self.wp_site_url.split('//')[1].split('.')[0]
            self.wp_api_base = f"https://public-api.wordpress.com/wp/v2/sites/{site_name}.wordpress.com"
        else:
            self.wp_api_base = f"{self.wp_site_url}/wp-json/wp/v2"
        
        # Get WordPress categories and convert to integers
        try:
            self.wp_categories = [int(cat.strip()) for cat in os.getenv('WORDPRESS_CATEGORIES', '').split(',') if cat.strip().isdigit()]
            if not self.wp_categories:
                logger.warning("No valid category IDs found in WORDPRESS_CATEGORIES")
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing WordPress categories: {str(e)}")
            self.wp_categories = []
        
        # Unsplash configuration
        self.unsplash_access_key = os.getenv('UNSPLASH_ACCESS_KEY')
        
        # QLOGA app URL
        self.qloga_app_url = "https://play.google.com/store/apps/details?id=eac.qloga.android"
        
        logger.info(f"ArticleGenerator initialized with WordPress API: {self.wp_api_base}")
        logger.info(f"Using WordPress categories: {self.wp_categories}")

    def _format_qloga_mentions(self, text: str) -> str:
        """Format all mentions of QLOGA to be uppercase and linked to the app store."""
        # Pattern matches 'qloga', 'Qloga', 'QLOGA' in any case
        pattern = re.compile(r'qloga', re.IGNORECASE)
        
        def replace_func(match):
            # Convert to uppercase and add link
            return f'<a href="{self.qloga_app_url}">QLOGA</a>'
        
        return pattern.sub(replace_func, text)

    async def generate_article(self, topic: str) -> Dict[str, str]:
        """Generate an article using OpenAI API."""
        try:
            logger.info(f"Generating article for topic: {topic}")
            
            # Define the function for structured output
            functions = [{
                "name": "create_article",
                "description": "Create an SEO-optimized article",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "SEO-optimized title (maximum 60 characters)"
                        },
                        "subtitle": {
                            "type": "string",
                            "description": "Compelling subtitle (maximum 120 characters)"
                        },
                        "content": {
                            "type": "string",
                            "description": "HTML formatted content with proper headings, paragraphs, and lists"
                        }
                    },
                    "required": ["title", "subtitle", "content"]
                }
            }]

            prompt = f"""Write a medium-length, SEO-optimized article about {topic} in British English. 
            Focus on Scotland (especially Edinburgh and surrounding areas).
            
            The content should be well-structured with:
            - An engaging introduction
            - 2-3 main sections with subheadings
            - A strong conclusion
            - Relevant local information about Scotland/Edinburgh
            - SEO-optimized content
            - Proper HTML formatting with <h2>, <p>, <ul> tags etc.
            
            If mentioning QLOGA, ensure it's relevant to the context."""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional content writer specializing in Scottish topics."},
                    {"role": "user", "content": prompt}
                ],
                functions=functions,
                function_call={"name": "create_article"},
                temperature=0.7,
                max_tokens=4000
            )

            # Extract the function call arguments
            article = json.loads(response.choices[0].message.function_call.arguments)
            
            # Format QLOGA mentions in title, subtitle, and content
            article['title'] = self._format_qloga_mentions(article['title'])
            article['subtitle'] = self._format_qloga_mentions(article['subtitle'])
            article['content'] = self._format_qloga_mentions(article['content'])
            
            # Validate and trim content if needed
            if len(article['title']) > 60:
                article['title'] = article['title'][:57] + "..."
            if len(article['subtitle']) > 120:
                article['subtitle'] = article['subtitle'][:117] + "..."

            return article

        except Exception as e:
            logger.error(f"Error generating article: {str(e)}")
            raise

    async def generate_image(self, topic: str) -> str:
        """Generate an image description and find a matching image on Unsplash."""
        try:
            logger.info(f"Generating image for topic: {topic}")
            
            # Generate image description using OpenAI
            prompt = f"""Generate a short, specific description for an image that would be perfect for an article about {topic}.
            The image should be relevant to Scotland, particularly Edinburgh.
            Make the description specific enough for a stock photo search.
            Return only the description, no additional text."""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional photographer focusing on Scottish landscapes and culture."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=100
            )

            image_description = response.choices[0].message.content.strip()
            logger.info(f"Generated image description: {image_description}")

            # Search Unsplash for matching image
            unsplash_url = "https://api.unsplash.com/search/photos"
            params = {
                'query': image_description,
                'client_id': self.unsplash_access_key,
                'per_page': 1
            }

            response = requests.get(unsplash_url, params=params)
            response.raise_for_status()

            results = response.json().get('results', [])
            if not results:
                raise ValueError("No matching images found on Unsplash")

            image_url = results[0]['urls']['regular']
            logger.info(f"Found image URL: {image_url}")
            return image_url

        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            raise

    async def _get_scheduled_posts(self) -> list:
        """Get all scheduled posts from WordPress."""
        try:
            headers = {
                'Authorization': f'Bearer {self.wp_oauth_token}',
                'Content-Type': 'application/json'
            }
            
            # Get posts with 'future' status (scheduled)
            response = requests.get(
                f"{self.wp_api_base}/posts",
                headers=headers,
                params={
                    'status': 'future',
                    'per_page': 100  # Maximum number of posts to retrieve
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get scheduled posts. Status: {response.status_code}, Response: {response.text}")
                return []
                
            return response.json()
        except Exception as e:
            logger.error(f"Error getting scheduled posts: {str(e)}")
            return []

    async def _find_next_available_date(self) -> datetime:
        """Find the next available date for publication at 6:03 AM Edinburgh time."""
        edinburgh_tz = pytz.timezone('Europe/London')
        now = datetime.now(edinburgh_tz)
        
        # Start checking from tomorrow
        check_date = now + timedelta(days=1)
        check_date = check_date.replace(hour=6, minute=3, second=0, microsecond=0)
        
        # Get all scheduled posts
        scheduled_posts = await self._get_scheduled_posts()
        scheduled_dates = []
        
        # Extract scheduled dates
        for post in scheduled_posts:
            try:
                # WordPress returns dates in UTC
                post_date = datetime.fromisoformat(post['date_gmt'].replace('Z', '+00:00'))
                post_date = post_date.astimezone(edinburgh_tz)
                scheduled_dates.append(post_date.date())
            except (KeyError, ValueError) as e:
                logger.error(f"Error parsing post date: {str(e)}")
                continue
        
        # Find the next available date
        while check_date.date() in scheduled_dates:
            check_date += timedelta(days=1)
            check_date = check_date.replace(hour=6, minute=3, second=0, microsecond=0)
        
        return check_date

    async def publish_to_wordpress(self, article: Dict[str, str], image_url: str) -> str:
        """Publish the article and image to WordPress."""
        try:
            logger.info("Starting WordPress publication process")

            # Download image
            image_response = requests.get(image_url, timeout=10)
            image_response.raise_for_status()

            # Prepare image file
            image_filename = f"article-image-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
            
            # Headers for WordPress API
            headers = {
                'Authorization': f'Bearer {self.wp_oauth_token}',
                'Content-Type': 'application/json'
            }

            # For media upload, we need different headers
            media_headers = {
                'Authorization': f'Bearer {self.wp_oauth_token}',
                'Content-Type': 'image/jpeg',
                'Content-Disposition': f'attachment; filename={image_filename}'
            }

            # Upload image using the binary content directly
            image_upload_response = requests.post(
                f"{self.wp_api_base}/media",
                headers=media_headers,
                data=image_response.content
            )
            
            if image_upload_response.status_code != 201:
                logger.error(f"Failed to upload image. Status: {image_upload_response.status_code}, Response: {image_upload_response.text}")
                raise Exception(f"Failed to upload image: {image_upload_response.text}")
                
            image_data = image_upload_response.json()
            image_id = image_data['id']
            
            # Prepare article content with image
            content = f"""<figure class="wp-block-image">
                <img src="{image_data['source_url']}" alt="{article['title']}"/>
            </figure>

            {article['content']}"""

            # Prepare post data
            post_data = {
                'title': article['title'],
                'content': content,
                'status': 'future',
                'featured_media': image_id
            }

            # Add categories only if we have valid ones
            if self.wp_categories:
                post_data['categories'] = self.wp_categories

            # Find next available publication date
            publication_date = await self._find_next_available_date()
            logger.info(f"Scheduling post for: {publication_date.isoformat()}")
            
            # Convert to UTC for WordPress
            post_data['date_gmt'] = publication_date.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%S')

            # Create post
            post_response = requests.post(
                f"{self.wp_api_base}/posts",
                headers=headers,
                json=post_data
            )
            
            if post_response.status_code not in [200, 201]:
                logger.error(f"Failed to create post. Status: {post_response.status_code}, Response: {post_response.text}")
                raise Exception(f"Failed to create post: {post_response.text}")

            post_data = post_response.json()
            return post_data.get('link', post_data.get('URL', ''))

        except Exception as e:
            logger.error(f"Error publishing to WordPress: {str(e)}")
            raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    welcome_message = """👋 Welcome to the Article Generator Bot!

I can help you create and publish articles about various topics, optimized for Scotland and Edinburgh.

Simply send me a topic, and I will:
1. Generate an SEO-optimized article
2. Find a relevant image
3. Publish it to WordPress

Try it now - just send me a topic! 📝"""
    
    await update.message.reply_text(welcome_message)

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming topic messages."""
    try:
        topic = update.message.text.strip()
        await update.message.reply_text("🎨 Starting article generation process...")

        # Create article generator
        generator = ArticleGenerator()

        # Generate article
        await update.message.reply_text("📝 Generating article content...")
        article = await generator.generate_article(topic)

        # Generate image
        await update.message.reply_text("🖼 Finding a perfect image...")
        image_url = await generator.generate_image(topic)

        # Publish to WordPress
        await update.message.reply_text("🌐 Publishing to WordPress...")
        post_url = await generator.publish_to_wordpress(article, image_url)

        # Get the scheduled publication date
        publication_date = await generator._find_next_available_date()
        formatted_date = publication_date.strftime("%d %B %Y")

        # Send success message
        success_message = f"""✅ Article published successfully!

📑 Title: {article['title']}
🔗 URL: {post_url}

The article is scheduled for publication on {formatted_date} at 6:03 AM Edinburgh time."""

        await update.message.reply_text(success_message)

    except Exception as e:
        error_message = f"❌ Sorry, something went wrong: {str(e)}"
        logger.error(f"Error processing topic: {str(e)}")
        await update.message.reply_text(error_message)

async def kill_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kill all running instances of the bot."""
    try:
        current_pid = os.getpid()
        killed_processes = []
        
        # Find all Python processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip the current process
                if proc.pid == current_pid:
                    continue
                    
                # Check if it's a Python process running this bot file
                cmdline = proc.cmdline()
                if len(cmdline) >= 2 and 'python' in cmdline[0].lower() and 'bot.py' in cmdline[1]:
                    proc.terminate()  # Send SIGTERM
                    killed_processes.append(proc.pid)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if killed_processes:
            await update.message.reply_text(f"🔪 Killed {len(killed_processes)} bot processes: {', '.join(map(str, killed_processes))}")
        else:
            await update.message.reply_text("✅ No other bot processes found running")

        # Exit the current process
        await update.message.reply_text("👋 Shutting down current bot instance...")
        sys.exit(0)

    except Exception as e:
        error_message = f"❌ Error killing processes: {str(e)}"
        logger.error(error_message)
        await update.message.reply_text(error_message)

def main() -> None:
    """Start the bot."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize bot
        application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("kill", kill_bot))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))

        # Start the bot
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == '__main__':
    main()
