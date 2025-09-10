from models import (
    User, Email, EmailCategory, UnhandledEmail, ImportanceLevel,
    Order, RefundRequest, NotFoundRefundRequest, RefundStatus
)
from services.gmail_service import GmailService
from services.gemini_service import GeminiService
from services.rag_service import RAGService
import re


class EmailProcessor:
    def __init__(self):
        self.gmail_service = GmailService()
        self.gemini_service = GeminiService()
        self.rag_service = RAGService()

    async def process_user_emails(self, user: User):
        """Process all unread emails for a user"""
        try:
            messages = await self.gmail_service.list_messages(user, 'is:unread')
            
            for message in messages:
                await self.process_single_email(user, message['id'])
                
        except Exception as e:
            print(f"Error processing emails for user {user.email}: {e}")

    async def process_single_email(self, user: User, message_id: str):
        """Process a single email"""
        try:
            # Check if already processed
            existing_email = await Email.filter(gmail_message_id=message_id).first()
            if existing_email:
                return
            
            # Get message details
            message_data = await self.gmail_service.get_message(user, message_id)
            if not message_data:
                return
            
            # Extract sender email
            sender_email = self.extract_email_address(message_data['sender'])
            
            # Categorize email
            category = await self.gemini_service.categorize_email(
                message_data['subject'], 
                message_data['body']
            )
            
            # Save email record
            email_record = await Email.create(
                gmail_message_id=message_id,
                user=user,
                sender_email=sender_email,
                subject=message_data['subject'],
                body=message_data['body'],
                category=category
            )
            
            # Process based on category
            if category == EmailCategory.QUESTION:
                await self.handle_question(email_record, user)
            elif category == EmailCategory.REFUND:
                await self.handle_refund_request(email_record, user)
            else:  # OTHER
                await self.handle_other_email(email_record)
            
            # Mark as read (optional - requires gmail.modify scope)
            try:
                await self.gmail_service.mark_as_read(user, message_id)
            except Exception as e:
                print(f"Could not mark as read (missing scope?): {e}")
                # Continue without marking as read
            
        except Exception as e:
            print(f"Error processing email {message_id}: {e}")

    async def handle_question(self, email: Email, user: User):
        """Handle question emails using RAG"""
        try:
            answer, can_answer = await self.rag_service.answer_question(email.body)
            
            if can_answer:
                # Send response
                success = await self.gmail_service.send_email(
                    user=user,
                    to_email=email.sender_email,
                    subject=f"Re: {email.subject}",
                    body=answer,
                    reply_to_message_id=email.gmail_message_id
                )
                
                if success:
                    email.response_sent = True
                    await email.save()
            else:
                # Cannot answer - save as unhandled with high importance
                await UnhandledEmail.create(
                    email=email,
                    importance_level=ImportanceLevel.HIGH,
                    reason="No relevant information found in knowledge base"
                )
                
        except Exception as e:
            print(f"Error handling question email {email.id}: {e}")

    async def handle_refund_request(self, email: Email, user: User):
        """Handle refund request emails"""
        try:
            # Extract order ID from email
            order_id = await self.gemini_service.extract_order_id(email.body)
            
            if not order_id:
                # Ask for order ID
                response = await self.gemini_service.generate_response(
                    email.body,
                    "Customer is requesting a refund but didn't provide an order ID. Ask them to provide their order ID so we can process the refund."
                )
                
                await self.gmail_service.send_email(
                    user=user,
                    to_email=email.sender_email,
                    subject=f"Re: {email.subject}",
                    body=response,
                    reply_to_message_id=email.gmail_message_id
                )
                
                # Create refund request without order
                await RefundRequest.create(
                    email=email,
                    customer_email=email.sender_email,
                    status="waiting_for_order_id"
                )
                
                email.response_sent = True
                await email.save()
                return
            
            # Check if order exists
            order = await Order.filter(order_id=order_id).first()
            
            if order:
                # Order found - process refund
                order.refund_status = RefundStatus.REQUESTED
                order.refund_requested_at = email.processed_at
                await order.save()
                
                response = f"Thank you for contacting us regarding order {order_id}. We have processed your refund request and the refund will be completed within 3 days. You will receive a confirmation email once the refund has been processed."
                
                await self.gmail_service.send_email(
                    user=user,
                    to_email=email.sender_email,
                    subject=f"Re: {email.subject}",
                    body=response,
                    reply_to_message_id=email.gmail_message_id
                )
                
                await RefundRequest.create(
                    email=email,
                    order=order,
                    customer_email=email.sender_email,
                    requested_order_id=order_id,
                    status="approved"
                )
                
                email.response_sent = True
                await email.save()
                
            else:
                # Order not found
                await self.handle_invalid_order_id(email, user, order_id)
                
        except Exception as e:
            print(f"Error handling refund request {email.id}: {e}")

    async def handle_invalid_order_id(self, email: Email, user: User, invalid_order_id: str):
        """Handle invalid order ID in refund request"""
        try:
            # Check if this customer already tried this order ID
            existing_attempt = await NotFoundRefundRequest.filter(
                customer_email=email.sender_email,
                invalid_order_id=invalid_order_id
            ).first()
            
            if existing_attempt:
                # Second attempt with same invalid ID
                existing_attempt.attempt_count += 1
                existing_attempt.email_content = email.body
                await existing_attempt.save()
                
                response = f"We still cannot find order {invalid_order_id} in our system. Please double-check your order ID or contact our support team directly for assistance."
            else:
                # First attempt with this invalid ID
                await NotFoundRefundRequest.create(
                    customer_email=email.sender_email,
                    invalid_order_id=invalid_order_id,
                    email_content=email.body,
                    attempt_count=1
                )
                
                response = f"We cannot find order {invalid_order_id} in our system. Please check your order ID and try again. You can find your order ID in your purchase confirmation email."
            
            await self.gmail_service.send_email(
                user=user,
                to_email=email.sender_email,
                subject=f"Re: {email.subject}",
                body=response,
                reply_to_message_id=email.gmail_message_id
            )
            
            await RefundRequest.create(
                email=email,
                customer_email=email.sender_email,
                requested_order_id=invalid_order_id,
                status="invalid_order_id"
            )
            
            email.response_sent = True
            await email.save()
            
        except Exception as e:
            print(f"Error handling invalid order ID: {e}")

    async def handle_other_email(self, email: Email):
        """Handle other/nonsense emails"""
        try:
            # Determine importance level based on content
            importance = await self.determine_importance(email.body)
            
            await UnhandledEmail.create(
                email=email,
                importance_level=importance,
                reason="Categorized as other/nonsense email"
            )
            
        except Exception as e:
            print(f"Error handling other email {email.id}: {e}")

    async def determine_importance(self, email_body: str) -> ImportanceLevel:
        """Determine importance level of an email"""
        try:
            importance_text = await self.gemini_service.determine_importance(email_body)
            
            if importance_text == "HIGH":
                return ImportanceLevel.HIGH
            elif importance_text == "MEDIUM":
                return ImportanceLevel.MEDIUM
            else:
                return ImportanceLevel.LOW
                
        except Exception as e:
            print(f"Error determining importance: {e}")
            return ImportanceLevel.MEDIUM

    def extract_email_address(self, from_header: str) -> str:
        """Extract email address from From header"""
        # Handle format like "John Doe <john@example.com>"
        email_match = re.search(r'<(.+@.+)>', from_header)
        if email_match:
            return email_match.group(1)
        
        # Handle direct email format
        email_match = re.search(r'[\w\.-]+@[\w\.-]+', from_header)
        if email_match:
            return email_match.group(0)
        
        return from_header