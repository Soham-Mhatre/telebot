# Gemini API Validation Script with Model Listing
import os
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()

# Get environment variables
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
FIREBASE_DATABASE_URL = os.environ.get('FIREBASE_DATABASE_URL')

def initialize_firebase():
    """Initialize Firebase app if not already initialized"""
    try:
        # Check if we already have an initialized app
        if not firebase_admin._apps:
            # Options for initialization
            options = {}
            
            # Add database URL if provided
            if FIREBASE_DATABASE_URL:
                options['databaseURL'] = FIREBASE_DATABASE_URL
            
            firebase_admin.initialize_app(options=options)
        
        print("Firebase initialized successfully")
        return True
    except Exception as e:
        print(f"Firebase initialization error: {str(e)}")
        return False

def list_available_models():
    """List all available Gemini models for the API key"""
    try:
        print("Listing available models...")
        genai.configure(api_key=GEMINI_API_KEY)
        
        # List available models
        models = genai.list_models()
        print("Available models:")
        available_models = []
        
        for model in models:
            print(f"- {model.name}")
            available_models.append(model.name)
            
        return available_models
    except Exception as e:
        print(f"Error listing models: {str(e)}")
        return []

def validate_gemini_api_key(model_name=None):
    """Validate Gemini API key by making a test request"""
    try:
        # Check if API key is available
        if not GEMINI_API_KEY:
            print("Error: GEMINI_API_KEY environment variable is not set")
            return {
                "success": False,
                "message": "API key not found in environment variables",
                "error": "Missing GEMINI_API_KEY"
            }
            
        print("Attempting to validate Gemini API key...")
        
        # Configure the Gemini API with your key
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Try different model names if none is specified
        models_to_try = []
        
        if model_name:
            models_to_try = [model_name]
        else:
            # Get available models
            available_models = list_available_models()
            
            # If we have available models, use those
            if available_models:
                models_to_try = available_models
            else:
                # Common model variations to try if listing fails
                models_to_try = [
                    'gemini-pro',
                    'gemini-1.0-pro',
                    'gemini-1.5-pro',
                    'gemini-1.5-flash',
                    'models/gemini-pro'
                ]
        
        # Try each model until one works
        last_error = None
        for model_name in models_to_try:
            try:
                print(f"Trying model: {model_name}")
                
                # Get a generative model
                model = genai.GenerativeModel(model_name)
                
                # Simple test prompt
                prompt = "Respond with 'API key is valid' if you receive this message."
                
                # Generate content as a test
                response = model.generate_content(prompt)
                text = response.text
                
                print(f"API Test Response: {text}")
                print(f"Gemini API key is valid and working correctly with model: {model_name}")
                
                return {
                    "success": True,
                    "message": "API key is valid",
                    "model": model_name,
                    "response": text
                }
                
            except Exception as e:
                last_error = str(e)
                print(f"Failed with model {model_name}: {last_error}")
                continue
        
        # If we get here, all models failed
        print("Could not find a working model with your API key.")
        return {
            "success": False,
            "message": "API key validation failed with all models",
            "error": last_error
        }
        
    except Exception as e:
        error_message = str(e)
        print(f"Error validating Gemini API key: {error_message}")
        
        # Check for specific error messages that indicate API key issues
        if any(keyword in error_message.lower() for keyword in ["api key not valid", "invalid", "unauthorized"]):
            print("Your API key appears to be invalid or has insufficient permissions.")
        
        return {
            "success": False,
            "message": "API key validation failed",
            "error": error_message
        }

def check_environment_variables():
    """Check if all required environment variables are set"""
    missing_vars = []
    
    if not GEMINI_API_KEY:
        missing_vars.append("GEMINI_API_KEY")
    
    if not FIREBASE_DATABASE_URL:
        missing_vars.append("FIREBASE_DATABASE_URL")
    
    if missing_vars:
        print(f"Warning: The following environment variables are missing: {', '.join(missing_vars)}")
        return False
    
    print("All required environment variables are set")
    return True

def main():
    """Main function to run the validation"""
    # Check environment variables
    env_check = check_environment_variables()
    if not env_check:
        print("Please set all required environment variables before running this script")
        return
    
    # Initialize Firebase
    firebase_initialized = initialize_firebase()
    
    # List available models
    available_models = list_available_models()
    
    # Validate Gemini API key
    result = validate_gemini_api_key()
    
    if result["success"]:
        print(f"Validation successful: {result['message']} with model {result.get('model')}")
        
        # Optional: Store result in Firebase if Firebase is initialized
        if firebase_initialized:
            try:
                db = firestore.client()
                db.collection('api_validations').document('gemini_api').set({
                    'timestamp': firestore.SERVER_TIMESTAMP,
                    'valid': True,
                    'model': result.get('model'),
                    'response': result.get('response')
                })
                print("Validation result stored in Firebase")
            except Exception as e:
                print(f"Failed to store result in Firebase: {str(e)}")
    else:
        print(f"Validation failed: {result.get('error', 'Unknown error')}")
        print("\nPossible issues:")
        print("1. Your API key might not have access to Gemini models")
        print("2. The Gemini API naming convention might have changed")
        print("3. The Gemini API might not be enabled for your project")
        print("4. You might need to enable billing for your Google Cloud project")
        print("\nSuggested actions:")
        print("1. Check the Google Cloud Console to ensure the Generative Language API is enabled")
        print("2. Verify the API key has appropriate permissions")
        print("3. Try creating a new API key in the Google Cloud Console")

# If running as a script
if __name__ == "__main__":
    main()