import os
import json
import random
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ১. গিটহাব সিক্রেটস থেকে ক্রেডেনশিয়াল সংগ্রহ
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", "").split(",")
BLOG_ID = os.environ.get("BLOG_ID")
CLIENT_ID = os.environ.get("BLOGGER_CLIENT_ID")
CLIENT_SECRET = os.environ.get("BLOGGER_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("BLOGGER_REFRESH_TOKEN")

# ২. জেমিনি এপিআই কনফিগারেশন এবং কন্টেন্ট জেনারেশন
def generate_blog_post():
    if not GEMINI_API_KEYS or not GEMINI_API_KEYS[0]:
        print("Error: Gemini API Key পাওয়া যায়নি।")
        return None

    # যেকোনো একটি API Key ব্যবহার করা (যাতে Rate Limit না হয়)
    api_key = random.choice(GEMINI_API_KEYS).strip()
    genai.configure(api_key=api_key)

    # সঠিক মডেল নির্বাচন: gemini-1.5-flash
    model = genai.GenerativeModel('gemini-1.5-flash')

    # এসইও এবং ক্যাটাগরি (মেনু) অনুযায়ী প্রম্পট
    prompt = """
    Write a highly SEO-optimized and engaging blog post in English.
    The topic should be related to technology, finance, or internet tips (choose randomly).
    The post must be well-structured using proper HTML tags (<h2>, <h3>, <p>, <ul>, <li>, <strong>) for readability and SEO.
    Do NOT include <html>, <head>, or <body> tags, only the content.
    
    Also, generate 2-3 relevant tags/labels which will act as menu categories for the blog.

    Format the output STRICTLY as a JSON object with the following structure without any extra markdown formatting like ```json:
    {
        "title": "A Catchy, SEO-Optimized Title",
        "content": "The full HTML formatted content of the post",
        "labels": ["Category1", "Category2"]
    }
    """

    try:
        response = model.generate_content(prompt)
        # JSON ডেটা প্রসেস করা
        raw_text = response.text.strip()
        
        # যদি মডেল ভুল করে ```json যুক্ত করে দেয়, সেটি রিমুভ করার ব্যবস্থা
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        post_data = json.loads(raw_text.strip())
        return post_data
    except Exception as e:
        print(f"Error generating content: {e}")
        return None

# ৩. ব্লগার এপিআই এর মাধ্যমে পোস্ট পাবলিশ করা
def post_to_blogger(post_data):
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, BLOG_ID]):
        print("Error: Blogger API credentials missing.")
        return

    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    try:
        service = build('blogger', 'v3', credentials=creds)

        post_body = {
            "kind": "blogger#post",
            "title": post_data["title"],
            "content": post_data["content"],
            "labels": post_data["labels"] # এই লেবেলগুলোই ব্লগের মেনু বা ক্যাটাগরি হিসেবে কাজ করবে
        }

        request = service.posts().insert(blogId=BLOG_ID, body=post_body, isDraft=False)
        response = request.execute()
        print(f"✅ Post published successfully! Link: {response.get('url')}")
        print(f"✅ Categories/Menus added: {', '.join(post_data['labels'])}")

    except Exception as e:
        print(f"Error posting to Blogger: {e}")

# স্ক্রিপ্ট রান করা
if __name__ == "__main__":
    print("Starting Blogger Automation Script...")
    post_data = generate_blog_post()
    
    if post_data:
        print(f"Content generated successfully. Title: {post_data['title']}")
        print("Publishing to Blogger...")
        post_to_blogger(post_data)
    else:
        print("❌ Failed to generate content. Workflow stopped.")
    
