import os
import re
import json
import random
import requests
import urllib.parse
import google.generativeai as genai

# --- ১. এনভায়রনমেন্ট ভেরিয়েবল (Secrets) ---
BLOG_ID = os.getenv("BLOG_ID")
CLIENT_ID = os.getenv("BLOGGER_CLIENT_ID")
CLIENT_SECRET = os.getenv("BLOGGER_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("BLOGGER_REFRESH_TOKEN")
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]

# ক্যাটাগরির লিস্ট (সিরিয়াল অনুযায়ী চলবে)
CATEGORIES = [
    "Personal Finance",
    "Finance Book Summary",
    "Finance News",
    "World Viral News"
]

STATE_FILE = "state.json"

# --- ২. সিরিয়াল অনুযায়ী পরবর্তী ক্যাটাগরি নির্বাচন ---
def get_next_category():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            last_index = data.get("last_index", -1)
    else:
        last_index = -1
    
    # পরবর্তী ক্যাটাগরি ইনডেক্স বের করা
    next_index = (last_index + 1) % len(CATEGORIES)
    
    # নতুন ইনডেক্স ফাইলে সেভ করা
    with open(STATE_FILE, "w") as f:
        json.dump({"last_index": next_index}, f)
        
    selected_category = CATEGORIES[next_index]
    print(f"Selected Category for this run: {selected_category}")
    return selected_category

# --- ৩. Blogger Access Token তৈরি করা ---
def get_blogger_access_token():
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        raise Exception(f"Failed to refresh Access Token: {response.text}")

# --- ৪. Gemini API কানেকশন ও রোটেশন ---
def get_working_gemini_model():
    for key in GEMINI_KEYS:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            # টেস্ট রিকোয়েস্ট করে দেখা API কাজ করছে কিনা
            model.generate_content("Ping")
            print(f"Connected to Gemini API successfully.")
            return model
        except Exception as e:
            print(f"API Key failed. Trying next... Error: {e}")
            continue
    raise Exception("All provided Gemini API keys failed or rate limit reached.")

# --- ৫. SEO কনটেন্ট ও ইমেজের প্রম্পট জেনারেট ---
def generate_seo_content(category, model):
    prompt = f"""
    You are an expert SEO content creator and blogger.
    Create a highly engaging, original, and fully SEO-optimized blog post for the category: "{category}".
    Language MUST be ENGLISH.

    Return ONLY a single valid JSON object (no markdown wrapping, no extra text) with the following structure:
    {{
        "title": "A compelling, keyword-rich title",
        "meta_description": "Under 150 characters meta description",
        "image_prompt": "Detailed English prompt to generate a high quality blog banner image related to the topic",
        "content_html": "Full blog post using HTML tags like <h2>, <h3>, <p>, <ul>, <li>, <strong>. Minimum 800 words."
    }}
    """
    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    
    # JSON ফরম্যাট ক্লিন করা
    cleaned_json = re.sub(r"^```json\s*|```$", "", raw_text, flags=re.MULTILINE).strip()
    return json.loads(cleaned_json)

# --- ৬. Pollinations AI দিয়ে অটোমেটিক ইমেজ জেনারেট ---
def generate_image_url(image_prompt):
    encoded_prompt = urllib.parse.quote(image_prompt)
    seed = random.randint(1000, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=630&seed={seed}&nologo=true"
    return image_url

# --- ৭. ব্লগারে পোস্ট পাবলিশ করা ---
def post_to_blogger(title, content_html, category, access_token, image_url):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # কনটেন্টের একদম উপরে ইমেজ বসানো
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
        print(f"Successfully published post: '{title}' in '{category}'")
    else:
        raise Exception(f"Failed to post on Blogger: {res.text}")

# --- ৮. মেইন ফাংশন ---
def main():
    print("Starting Blog Automation...")
    
    selected_category = get_next_category()
    model = get_working_gemini_model()

    print("Generating SEO Content...")
    post_data = generate_seo_content(selected_category, model)

    print("Generating Image URL...")
    image_url = generate_image_url(post_data.get("image_prompt", selected_category))

    print("Publishing to Blogger...")
    access_token = get_blogger_access_token()
    post_to_blogger(
        title=post_data["title"],
        content_html=post_data["content_html"],
        category=selected_category,
        access_token=access_token,
        image_url=image_url
    )
    print("Task Completed Successfully!")

if __name__ == "__main__":
    main()

