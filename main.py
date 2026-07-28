import os
import re
import json
import random
import requests
import urllib.parse
from google import genai

# ==========================================
# 1. ENVIRONMENT VARIABLES (SECRETS)
# ==========================================
BLOG_ID = os.getenv("BLOG_ID")
CLIENT_ID = os.getenv("BLOGGER_CLIENT_ID")
CLIENT_SECRET = os.getenv("BLOGGER_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("BLOGGER_REFRESH_TOKEN")
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]

# Post Categories (Sequential Rotation)
CATEGORIES = [
    "Personal Finance",
    "Finance Book Summary",
    "Finance News",
    "World Viral News"
]

STATE_FILE = "state.json"

# ==========================================
# 2. CATEGORY ROTATION LOGIC
# ==========================================
def get_next_category():
    print("[INFO] Checking category state...")
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                data = json.load(f)
                last_index = data.get("last_index", -1)
            except json.JSONDecodeError:
                last_index = -1
    else:
        last_index = -1
    
    next_index = (last_index + 1) % len(CATEGORIES)
    
    with open(STATE_FILE, "w") as f:
        json.dump({"last_index": next_index}, f)
        
    selected_category = CATEGORIES[next_index]
    print(f"[INFO] Selected Category for this run: {selected_category}")
    return selected_category

# ==========================================
# 3. GOOGLE BLOGGER AUTHENTICATION
# ==========================================
def get_blogger_access_token():
    print("[INFO] Generating Blogger Access Token...")
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        print("[SUCCESS] Access Token generated successfully.")
        return response.json().get("access_token")
    else:
        raise Exception(f"[ERROR] Failed to refresh Access Token: {response.text}")

# ==========================================
# 4. GEMINI API CLIENT ROTATION
# ==========================================
def get_working_gemini_client():
    print("[INFO] Initializing Gemini API Client...")
    for key in GEMINI_KEYS:
        try:
            client = genai.Client(api_key=key)
            # Test request
            client.models.generate_content(
                model='gemini-1.5-flash',
                contents='Ping'
            )
            print(f"[SUCCESS] Connected to Gemini API successfully with key ending in ...{key[-4:]}")
            return client
        except Exception as e:
            print(f"[WARNING] API Key failed. Trying next... Error: {e}")
            continue
    raise Exception("[ERROR] All provided Gemini API keys failed or rate limit reached.")

# ==========================================
# 5. GENERATE SEO CONTENT (ENGLISH)
# ==========================================
def generate_seo_content(category, client):
    print(f"[INFO] Generating SEO Content for category: {category}...")
    prompt = f"""
    You are an expert SEO content creator and blogger.
    Create a highly engaging, original, and fully SEO-optimized blog post for the category: "{category}".
    Language MUST be ENGLISH.

    Return ONLY a single valid JSON object (no markdown wrapping, no extra text) with the following structure:
    {{
        "title": "A compelling, keyword-rich title in English",
        "meta_description": "Under 150 characters meta description in English",
        "image_prompt": "Detailed English prompt to generate a high quality blog banner image related to the topic",
        "content_html": "Full blog post in English using HTML tags like <h2>, <h3>, <p>, <ul>, <li>, <strong>. Minimum 800 words."
    }}
    """
    
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=prompt
    )
    raw_text = response.text.strip()
    
    # Clean markdown JSON formatting if present
    cleaned_json = re.sub(r"^```json\s*|```$", "", raw_text, flags=re.MULTILINE).strip()
    
    try:
        data = json.loads(cleaned_json)
        print("[SUCCESS] Content generated successfully.")
        return data
    except json.JSONDecodeError as e:
        raise Exception(f"[ERROR] Failed to parse Gemini response as JSON. Response: {cleaned_json}")

# ==========================================
# 6. GENERATE IMAGE URL (POLLINATIONS AI)
# ==========================================
def generate_image_url(image_prompt):
    print("[INFO] Generating Banner Image URL...")
    encoded_prompt = urllib.parse.quote(image_prompt)
    seed = random.randint(1000, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=630&seed={seed}&nologo=true"
    print(f"[INFO] Image URL ready: {image_url}")
    return image_url

# ==========================================
# 7. PUBLISH TO BLOGGER
# ==========================================
def post_to_blogger(title, content_html, category, access_token, image_url):
    print("[INFO] Publishing post to Blogger...")
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Wrap the image and content
    full_content = f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <img src="{image_url}" alt="{title}" style="max-width: 100%; height: auto; border-radius: 8px;" />
    </div>
    {content_html}
    """

    payload = {
        "kind": "blogger#post",
        "title": title,
        "content": full_content,
        "labels": [category]
    }

    res = requests.post(url, json=payload, headers=headers)
    if res.status_code == 200:
        print(f"[SUCCESS] Post published successfully!")
        print(f"Title: {title}")
        print(f"URL: {res.json().get('url')}")
    else:
        raise Exception(f"[ERROR] Failed to post on Blogger: {res.text}")

# ==========================================
# 8. MAIN EXECUTION
# ==========================================
def main():
    print("="*50)
    print("   BLOGGER AUTOMATION SCRIPT STARTED   ")
    print("="*50)
    
    try:
        # Step 1: Get Category
        selected_category = get_next_category()
        
        # Step 2: Initialize Gemini
        client = get_working_gemini_client()

        # Step 3: Generate Content
        post_data = generate_seo_content(selected_category, client)

        # Step 4: Generate Image
        image_url = generate_image_url(post_data.get("image_prompt", selected_category))

        # Step 5: Get Auth Token
        access_token = get_blogger_access_token()
        
        # Step 6: Publish
        post_to_blogger(
            title=post_data["title"],
            content_html=post_data["content_html"],
            category=selected_category,
            access_token=access_token,
            image_url=image_url
        )
        
        print("\n[COMPLETED] Automation finished successfully.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")

if __name__ == "__main__":
    main()
    
