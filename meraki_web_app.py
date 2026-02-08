from flask import Flask, redirect, request, session, render_template
import requests
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

meraki_web_app = Flask(__name__)
meraki_web_app.secret_key = os.urandom(24)  # Secret key for session management

# Configuration
CLIENT_ID = os.getenv('MERAKI_CLIENT_ID')
CLIENT_SECRET = os.getenv('MERAKI_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('MERAKI_REDIRECT_URI')
SCOPES = 'dashboard:general:config:read'
AUTHORIZATION_BASE_URL = 'https://as.meraki.com/oauth/authorize'
TOKEN_URL = 'https://as.meraki.com/oauth/token'

@meraki_web_app.route('/')
def index():
    return render_template('index.html')

@meraki_web_app.route('/authurl')
def authurl():
    state = "time" + datetime.now().strftime("%Y%m%dT%H%M%S")
    authorization_args = f"response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPES}&state={state}"
    authorization_url = f"{AUTHORIZATION_BASE_URL}?{authorization_args}" # Ensure URL is properly encoded
    session['authorization_url'] = authorization_url
    return render_template('authurl.html', authurl=authorization_url)

@meraki_web_app.route('/connect')
def connect():
    authorization_url = session.get('authorization_url')
    print (authorization_url)
    return redirect(authorization_url)

@meraki_web_app.route('/callback')
def callback():
    code = request.args.get('code')
    session['code'] = code
    if not code:
        return "Error: No code provided"
    
    return render_template('authcode.html', authcode=code)

@meraki_web_app.route('/generate_access_token')
def generate_access_token():    
    try:
        # Exchange authorization code for access token
        code = session.get('code')
        token_response = requests.post(
            TOKEN_URL,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            auth=(CLIENT_ID, CLIENT_SECRET),
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'scope': SCOPES,
            }
        )
        
        token_response.raise_for_status()  # Raise an error for bad responses
        
        tokens = token_response.json()
        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']
        token_expiry = datetime.now(timezone.utc) + timedelta(minutes=60)
        
        # Store tokens securely
        session['access_token'] = access_token
        session['refresh_token'] = refresh_token
        session['token_expiry'] = token_expiry

        return render_template('tokens.html', access_token=access_token, refresh_token=refresh_token, token_expiry=token_expiry)
    
    except requests.exceptions.RequestException as e:
        return f"Error obtaining token: {str(e)}"
    
@meraki_web_app.route('/organizations')
def organizations():
    access_token = session.get('access_token')
    token_expiry = session.get('token_expiry')

    if not access_token or datetime.now(timezone.utc) >= token_expiry:
        return redirect('/refresh')
    
    try:
        #fetch organizations
        response = requests.get(
            'https://api.meraki.com/api/v1/organizations',
            headers={
                'Authorization': f'Bearer {access_token}'
            }
        )
        response.raise_for_status()
        organizations = response.json()

        return render_template('organizations.html', organizations=organizations)
    except requests.exceptions.RequestException as e:
        return f"API call error: {str(e)}"


@meraki_web_app.route('/networks')
def networks():
    org = request.args.get('org')
    access_token = session.get('access_token')
    token_expiry = session.get('token_expiry')

    if not access_token or datetime.now(timezone.utc) >= token_expiry:
        return redirect('/refresh')
    
    try:
        #fetch organizations
        response = requests.get(
            f'https://api.meraki.com/api/v1/organizations/{org}/networks',
            headers={
                'Authorization': f'Bearer {access_token}'
            }
        )
        response.raise_for_status()
        networks = response.json()

        return render_template('networks.html', networks=networks)
    except requests.exceptions.RequestException as e:
        return f"API call error: {str(e)}"


@meraki_web_app.route('/refresh')
def refresh():
    try:
        refresh_token = session.get('refresh_token')
        
        if not refresh_token:
            return "No refresh token available"

        # Refresh the access token
        refresh_response = requests.post(
            TOKEN_URL,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            auth=(CLIENT_ID, CLIENT_SECRET),
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            }
        )
        
        refresh_response.raise_for_status()
        
        tokens = refresh_response.json()
        session['access_token'] = tokens['access_token']
        session['refresh_token'] = tokens['refresh_token']
        session['token_expiry'] = datetime.now() + timedelta(minutes=60)

        return redirect('/organizations')

    except requests.exceptions.RequestException as e:
        return f"Error refreshing token: {str(e)}"

if __name__ == '__main__':
      meraki_web_app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        threaded=True)
