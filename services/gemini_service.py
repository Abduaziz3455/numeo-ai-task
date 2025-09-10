from google import genai
from google.genai import types
from config import GEMINI_API_KEY
from models import EmailCategory
import re


class GeminiService:
    def __init__(self):
        # Initialize the new genai client
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = "gemini-2.5-flash"

    async def categorize_email(self, subject: str, body: str) -> EmailCategory:
        """Categorize email into question, refund, or other"""
        prompt = f"""
        Analyze this email and categorize it into one of these categories:
        1. "question" - if it's asking for help, information, or support
        2. "refund" - if it's requesting a refund or return
        3. "other" - if it's anything else (spam, nonsense, complaints not asking for refund)

        Email Subject: {subject}
        Email Body: {body}

        Respond with only one word: question, refund, or other
        """
        
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ]
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents
            )
            
            category_text = response.text.strip().lower()
            
            if "question" in category_text:
                return EmailCategory.QUESTION
            elif "refund" in category_text:
                return EmailCategory.REFUND
            else:
                return EmailCategory.OTHER
        except Exception as e:
            print(f"Error categorizing email: {e}")
            return EmailCategory.OTHER

    async def extract_order_id(self, email_body: str) -> str:
        """Extract order ID from email content"""
        prompt = f"""
        Extract the order ID from this email. Order IDs are typically alphanumeric codes like:
        - ORDER123, ORD-456, #789, etc.
        
        Email: {email_body}
        
        If you find an order ID, respond with just the order ID.
        If no order ID is found, respond with "NONE"
        """
        
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ]
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents
            )
            
            order_id = response.text.strip()
            
            if order_id != "NONE" and len(order_id) > 0:
                return order_id
        except Exception as e:
            print(f"Error extracting order ID with Gemini: {e}")
        
        # Fallback to regex patterns
        patterns = [
            r'order\s*#?\s*([a-zA-Z0-9]+)',
            r'order\s*id\s*:?\s*([a-zA-Z0-9]+)',
            r'#([a-zA-Z0-9]+)',
            r'([A-Z0-9]{6,})'  # Generic alphanumeric codes
        ]
        
        email_body_lower = email_body.lower()
        for pattern in patterns:
            matches = re.findall(pattern, email_body_lower, re.IGNORECASE)
            if matches:
                return matches[0].upper()
        
        return None

    async def generate_response(self, email_body: str, context: str = None) -> str:
        """Generate email response based on context"""
        base_prompt = f"Generate a professional customer service email response for this customer inquiry:\n\n{email_body}\n\n"
        
        if context:
            base_prompt += f"Additional context: {context}\n\n"
        
        base_prompt += "Keep the response concise, helpful, and professional."
        
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=base_prompt)]
                )
            ]
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents
            )
            
            return response.text.strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return "Thank you for contacting us. We have received your message and will get back to you soon."

    async def get_embedding(self, text: str) -> list:
        """Get embedding for text using Gemini embedding model"""
        try:
            # Use the new Gemini embedding API
            result = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",  # For storing documents
                    output_dimensionality=768  # Smaller dimension for efficiency
                )
            )
            
            # Extract the embedding values
            if result.embeddings and len(result.embeddings) > 0:
                return result.embeddings[0].values
            else:
                raise Exception("No embeddings returned")
                
        except Exception as e:
            print(f"Error getting embedding: {e}")
            # Return a dummy embedding if service fails
            return [0.0] * 768

    async def get_query_embedding(self, query: str) -> list:
        """Get embedding for search queries using optimized task type"""
        try:
            # Use RETRIEVAL_QUERY for search queries
            result = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=query,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",  # For search queries
                    output_dimensionality=768
                )
            )
            
            # Extract the embedding values
            if result.embeddings and len(result.embeddings) > 0:
                return result.embeddings[0].values
            else:
                raise Exception("No embeddings returned")
                
        except Exception as e:
            print(f"Error getting query embedding: {e}")
            # Return a dummy embedding if service fails
            return [0.0] * 768

    async def determine_importance(self, email_body: str) -> str:
        """Determine importance level of an email"""
        prompt = f"""
        Analyze this email and determine its importance level:
        - HIGH: Urgent complaints, legal issues, escalations, angry customers
        - MEDIUM: General inquiries, feedback, non-urgent issues
        - LOW: Spam, nonsense, promotional emails, obvious junk
        
        Email: {email_body}
        
        Respond with only: HIGH, MEDIUM, or LOW
        """
        
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ]
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents
            )
            
            importance_text = response.text.strip().upper()
            
            if "HIGH" in importance_text:
                return "HIGH"
            elif "MEDIUM" in importance_text:
                return "MEDIUM"
            else:
                return "LOW"
                
        except Exception as e:
            print(f"Error determining importance: {e}")
            return "MEDIUM"