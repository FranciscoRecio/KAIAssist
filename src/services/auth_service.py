from typing import Optional
import os
from datetime import datetime, timedelta
import requests
import base64
from dotenv import load_dotenv

class KayakoAuthService:
    def __init__(self):
        load_dotenv()
        self.base_url = os.getenv('KAYAKO_BASE_URL')
        self.username = os.getenv('KAYAKO_USERNAME')
        self.password = os.getenv('KAYAKO_PASSWORD')
        self.session_id = None
        self.session_expiry = None
        self.csrf_token = None
        
    def get_session_id(self) -> Optional[str]:
        """Get a valid session ID, refreshing if necessary"""
        if not self.session_id or self._is_session_expired():
            self._refresh_session()
        return self.session_id
    
    def _is_session_expired(self) -> bool:
        """Check if the current session is expired or about to expire"""
        if not self.session_expiry:
            return True
        # Return True if session expires in less than 5 minutes
        return datetime.utcnow() + timedelta(minutes=5) >= self.session_expiry
    
    def _refresh_session(self) -> None:
        """Get a new session using basic auth"""
        auth_url = f"{self.base_url}/users"  # Kayako basic auth endpoint
        
        # Create basic auth header
        auth_string = f"{self.username}:{self.password}"
        auth_bytes = auth_string.encode('ascii')
        base64_auth = base64.b64encode(auth_bytes).decode('ascii')
        headers = {
            'Authorization': f'Basic {base64_auth}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(auth_url, headers=headers)
            response.raise_for_status()
            
            # Store CSRF token from response headers
            self.csrf_token = response.headers.get('X-CSRF-Token')
            if not self.csrf_token:
                print("Warning: No CSRF token in response")
            
            auth_data = response.json()
            if 'session_id' not in auth_data:
                raise Exception("No session ID in response")
                
            self.session_id = auth_data['session_id']
            # Set session expiry (assuming 24 hours if not provided)
            self.session_expiry = datetime.utcnow() + timedelta(hours=24)
            
        except Exception as e:
            print(f"Error refreshing Kayako session: {e}")
            self.session_id = None
            self.session_expiry = None
            self.csrf_token = None
            raise
    
    def get_auth_headers(self) -> dict:
        """Get headers needed for authenticated requests"""
        session_id = self.get_session_id()
        if not session_id:
            raise Exception("Failed to get valid session ID")
            
        headers = {
            'X-Session-ID': session_id,
            'Content-Type': 'application/json'
        }
        
        # Add CSRF token for POST/PUT/DELETE requests
        if self.csrf_token:
            headers['X-CSRF-Token'] = self.csrf_token
            
        return headers 