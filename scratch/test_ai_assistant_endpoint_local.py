import sys
import os
print("Importing modules...")
from dotenv import load_dotenv

sys.path.append('/Users/emin/ProgrammingProjects/celmak/celmakstok')
print("Loading .env file...")
load_dotenv('/Users/emin/ProgrammingProjects/celmak/celmakstok/.env')

print("Creating app...")
from app import create_app, db
app = create_app()
app.config['GEMINI_API_KEY'] = '' # Force local fallback

from app.models import User, Product

print("Entering app context...")
with app.app_context():
    print("Querying admin user...")
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("Admin user not found!")
        sys.exit(1)

    print("Testing /reports/ai-assistant/ask locally using Flask test client...")
    client = app.test_client()
    
    print("Setting session...")
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin.id)
        sess['_fresh'] = True

    print("Sending POST request...")
    response = client.post('/reports/ai-assistant/ask', json={
        'query': '10 adet #3752 üretmek istesem maliyeti ne olur?',
        'history': []
    })
    
    print("Request finished!")
    print("Status Code:", response.status_code)
    print("Response JSON:", response.get_json())
