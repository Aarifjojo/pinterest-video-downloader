from flask import Flask, render_template, request, jsonify
import requests
import re
import json
import os
import random
import time
from urllib.parse import unquote
from fake_useragent import UserAgent
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='pinterest_downloader.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Initialize UserAgent
try:
    ua = UserAgent(fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
except:
    ua = None

def random_user_agent():
    """Return a random user agent string"""
    if ua:
        return ua.random
    else:
        # Fallback user agents if fake_useragent fails
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        ]
        return random.choice(user_agents)

# Free proxy list - you should update this regularly or use a proxy service
PROXY_LIST = []

def get_random_proxy():
    """Return a random proxy from the list if available"""
    if not PROXY_LIST:
        return None
    
    proxy = random.choice(PROXY_LIST)
    return {
        'http': proxy,
        'https': proxy
    }

# Rate limiting
RATE_LIMIT = {}
MAX_REQUESTS = 10  # Maximum requests per minute per IP
RATE_LIMIT_WINDOW = 60  # seconds

def is_rate_limited(ip):
    """Check if the IP is rate limited"""
    current_time = time.time()
    if ip in RATE_LIMIT:
        # Clean up old entries
        RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if current_time - t < RATE_LIMIT_WINDOW]
        
        # Check if rate limited
        if len(RATE_LIMIT[ip]) >= MAX_REQUESTS:
            return True
        
        # Add new request timestamp
        RATE_LIMIT[ip].append(current_time)
        return False
    else:
        # First request from this IP
        RATE_LIMIT[ip] = [current_time]
        return False

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def extract_thumbnail_url(html_content, video_url):
    """Extract thumbnail URL from Pinterest page"""
    # Try to find og:image meta tag (most reliable)
    og_image_pattern = r'<meta\s+property="og:image"\s+content="([^"]+)"'
    match = re.search(og_image_pattern, html_content)
    if match:
        return unquote(match.group(1))
    
    # Try to find twitter:image meta tag
    twitter_image_pattern = r'<meta\s+name="twitter:image"\s+content="([^"]+)"'
    match = re.search(twitter_image_pattern, html_content)
    if match:
        return unquote(match.group(1))
    
    # Try to find image in Pinterest-specific JSON data
    try:
        json_match = re.search(r'<script id="initial-state" type="application/json">(.*?)</script>', html_content)
        if json_match:
            data = json.loads(json_match.group(1))
            if 'resourceResponses' in data:
                for response in data['resourceResponses']:
                    if 'data' in response and 'images' in response['data']:
                        return response['data']['images']['orig']['url']
    except:
        pass
    
    # Try to extract from video URL
    if video_url and '.mp4' in video_url:
        # Try to convert video URL to image URL
        image_url = video_url.replace('.mp4', '.jpg')
        return image_url
    
    # If no thumbnail found, return None
    return None

@app.route('/download', methods=['POST'])
def download_video():
    try:
        url = request.form.get('url')
        
        if not url:
            return jsonify({'success': False, 'error': 'Please enter a Pinterest URL'})
        
        # Clean the URL
        url = url.strip()
        
        # Add protocol if missing
        if not url.startswith('http'):
            url = 'https://' + url
        
        # Simplified headers to avoid detection
        headers = {
            'User-Agent': random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/'
        }
        
        # Use a simple request without session to avoid complexity
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'error': f'Failed to fetch Pinterest page (Status code: {response.status_code})'})
        
        # Extract video URL using optimized patterns first
        html_content = response.text
        video_url = extract_video_url_fast(html_content)
        
        if not video_url:
            # Fall back to more comprehensive extraction only if needed
            video_url = extract_video_url(html_content)
        
        if not video_url:
            return jsonify({'success': False, 'error': 'No video found on this Pinterest page. Please make sure the URL contains a video.'})
        
        # Make sure the video URL is absolute
        if not video_url.startswith('http'):
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            else:
                video_url = 'https://' + video_url
        
        # Ensure we have an MP4 URL
        if not video_url.endswith('.mp4') and '.mp4' not in video_url:
            # Try to append .mp4 if it's missing
            if '?' in video_url:
                video_url = video_url.split('?')[0] + '.mp4'
            else:
                video_url = video_url + '.mp4'
        
        # Extract thumbnail URL
        thumbnail_url = extract_thumbnail_url(html_content, video_url)
        
        # Get basic video info without making additional requests
        video_info = {
            'size': 'Unknown',
            'type': 'video/mp4'  # Force MP4 type
        }
        
        # Log success for debugging
        print(f"Successfully extracted video URL: {video_url}")
        if thumbnail_url:
            print(f"Thumbnail URL: {thumbnail_url}")
        
        return jsonify({
            'success': True, 
            'video_url': video_url,
            'thumbnail_url': thumbnail_url,
            'video_info': video_info
        })
        
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return jsonify({'success': False, 'error': f'Error processing request: {str(e)}'})

def extract_video_url_fast(html_content):
    """A faster version that checks only the most common patterns first"""
    # Check for the most common video URL patterns with MP4 extension
    common_patterns = [
        r'(https://v\.pinimg\.com/[^"\']+\.mp4)',
        r'(https://i\.pinimg\.com/[^"\']+\.mp4)',
        r'(https://media\.giphy\.com/[^"\']+\.mp4)',
        r'(https://s\.pinimg\.com/[^"\']+\.mp4)',
        r'property="og:video" content="([^"]+\.mp4)"',
        r'<meta\s+name="twitter:player:stream"\s+content="([^"]+\.mp4)"'
    ]
    
    for pattern in common_patterns:
        match = re.search(pattern, html_content)
        if match:
            url = unquote(match.group(1))
            # Ensure it's an MP4 URL
            if '.mp4' in url:
                return url
    
    # Quick check for video in JSON data
    try:
        json_match = re.search(r'<script data-test-id="video-snippet" type="application/json">(.*?)</script>', html_content)
        if json_match:
            data = json.loads(json_match.group(1))
            if 'contentUrl' in data and '.mp4' in data['contentUrl']:
                return data['contentUrl']
    except:
        pass
    
    return None

def is_valid_pinterest_url(url):
    # More flexible pattern to accept various Pinterest URL formats
    pattern = r'^https?://(www\.)?(pinterest\.(com|ca|co\.uk|fr|de|ch|jp|au|in)|pin\.it).*'
    return bool(re.match(pattern, url))

def extract_video_url(html_content):
    # Compile patterns once for better performance
    video_patterns = [
        r'(https://v\.pinimg\.com/[^"\']+\.mp4)',
        r'(https://i\.pinimg\.com/[^"\']+\.mp4)',
        r'(https://media\.giphy\.com/[^"\']+\.mp4)',
        r'(https://i\.vimeocdn\.com/[^"\']+\.mp4)',
        r'(https://player\.vimeo\.com/[^"\']+\.mp4)',
        r'(https://s\.pinimg\.com/[^"\']+\.mp4)',
        r'(https://[^"\']+\.pinimg\.com/[^"\']+\.mp4)'
    ]
    
    # Compile patterns once
    compiled_patterns = [re.compile(pattern) for pattern in video_patterns]
    
    # Check all patterns
    for pattern in compiled_patterns:
        match = pattern.search(html_content)
        if match:
            return unquote(match.group(1))
    
    # Look for video tags directly with compiled patterns
    video_tag_patterns = [
        r'<video[^>]*>\s*<source[^>]*src="([^"]+)"',
        r'<video[^>]*src="([^"]+)"',
        r'property="og:video:secure_url" content="([^"]+)"',
        r'property="og:video" content="([^"]+)"',
        r'<meta\s+name="twitter:player:stream"\s+content="([^"]+)"'
    ]
    
    compiled_tag_patterns = [re.compile(pattern) for pattern in video_tag_patterns]
    
    for pattern in compiled_tag_patterns:
        match = pattern.search(html_content)
        if match:
            return unquote(match.group(1))
    
    # Look for JSON data more efficiently
    json_data_pattern = re.compile(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>')
    for match in json_data_pattern.finditer(html_content):
        try:
            data = json.loads(match.group(1))
            # Check for video URL in the JSON
            if isinstance(data, dict):
                if 'contentUrl' in data:
                    return data['contentUrl']
                elif 'video' in data and isinstance(data['video'], dict) and 'contentUrl' in data['video']:
                    return data['video']['contentUrl']
        except:
            continue
    
    return None

def find_video_url_in_json(data, depth=0, max_depth=10):
    """Recursively search for video URLs in JSON data"""
    if depth > max_depth:
        return None
    
    if isinstance(data, dict):
        # Check for common video URL keys
        for key in ['video_url', 'url', 'contentUrl', 'file_url', 'src']:
            if key in data and isinstance(data[key], str) and '.mp4' in data[key]:
                return data[key]
        
        # Check for video objects
        if 'videos' in data and isinstance(data['videos'], dict):
            for quality in ['max_quality', 'high_quality', 'medium_quality', 'low_quality']:
                if quality in data['videos'] and 'url' in data['videos'][quality]:
                    return data['videos'][quality]['url']
        
        # Check for video list
        if 'video_list' in data and isinstance(data['video_list'], dict):
            for quality, video_data in data['video_list'].items():
                if 'url' in video_data:
                    return video_data['url']
        
        # Recursively search in nested dictionaries
        for key, value in data.items():
            result = find_video_url_in_json(value, depth + 1, max_depth)
            if result:
                return result
    
    elif isinstance(data, list):
        # Recursively search in lists
        for item in data:
            result = find_video_url_in_json(item, depth + 1, max_depth)
            if result:
                return result
    
    return None

def get_video_info(video_url):
    """Get basic video info without making a request if possible"""
    try:
        response = requests.head(video_url, timeout=3)
        content_length = response.headers.get('Content-Length')
        content_type = response.headers.get('Content-Type')
        
        size_mb = round(int(content_length) / (1024 * 1024), 2) if content_length else "Unknown"
        
        return {
            'size': f"{size_mb} MB",
            'type': content_type or 'video/mp4'
        }
    except:
        return {
            'size': 'Unknown',
            'type': 'video/mp4'
        }

def randomize_request_params():
    """Randomize request parameters to avoid detection patterns"""
    # Random query parameters to add to URLs
    random_params = {
        '_': str(int(time.time() * 1000)),
        'rand': str(random.randint(1000, 9999))
    }
    
    # Random order of headers
    header_keys = [
        'User-Agent', 'Accept', 'Accept-Language', 'Accept-Encoding',
        'Connection', 'Upgrade-Insecure-Requests', 'Cache-Control'
    ]
    random.shuffle(header_keys)
    
    return random_params

# Use this function before making requests
random_params = randomize_request_params()

if __name__ == '__main__':
    # Run locally on your computer only
    app.run(host='127.0.0.1', port=5000, debug=False)