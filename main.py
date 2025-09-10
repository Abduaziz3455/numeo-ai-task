from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
import uvicorn
import asyncio
from contextlib import asynccontextmanager

from database import init_db, close_db
from models import User, Order
from services.gmail_service import GmailService
from services.email_processor import EmailProcessor
from services.rag_service import RAGService
from config import APP_HOST, APP_PORT


# Global services
gmail_service = GmailService()
email_processor = EmailProcessor()
rag_service = RAGService()

# Background task flag
processing_active = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await init_db()

    # !!! Load knowledge only first time !!!
    await rag_service.load_initial_knowledge()
    ###

    await create_sample_orders()
    
    # Start email processing
    asyncio.create_task(continuous_email_processing())
    
    yield
    
    # Shutdown
    global processing_active
    processing_active = False
    await close_db()


app = FastAPI(
    title="Customer Support Email Agent",
    description="Automated customer support email processing system",
    version="1.0.0",
    lifespan=lifespan
)


async def create_sample_orders():
    """Create sample orders for testing"""
    sample_orders = [
        {"order_id": "ORD001", "customer_email": "customer1@example.com", "amount": 99.99},
        {"order_id": "ORD002", "customer_email": "customer2@example.com", "amount": 149.50},
        {"order_id": "ABC123", "customer_email": "customer3@example.com", "amount": 75.00},
    ]
    
    for order_data in sample_orders:
        existing = await Order.filter(order_id=order_data["order_id"]).first()
        if not existing:
            await Order.create(**order_data)


async def continuous_email_processing():
    """Continuously process emails for all active users"""
    global processing_active
    processing_active = True
    
    while processing_active:
        try:
            # Get all active users
            users = await User.filter(is_active=True).all()
            
            for user in users:
                await email_processor.process_user_emails(user)
            
            # Wait 30 seconds before next check
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Error in continuous email processing: {e}")
            await asyncio.sleep(60)  # Wait longer on error


@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "Customer Support Email Agent",
        "status": "running",
        "endpoints": {
            "auth": "/auth",
            "callback": "/auth/callback",
            "users": "/users",
            "process": "/process/{user_id}",
            "knowledge": "/knowledge"
        }
    }


@app.get("/auth")
async def start_auth():
    """Start Gmail OAuth authentication"""
    auth_url = gmail_service.get_auth_url()
    return {"auth_url": auth_url}


@app.get("/auth/callback")
async def auth_callback(code: str):
    """Handle OAuth callback"""
    try:
        result = await gmail_service.handle_oauth_callback(code)
        return {
            "message": "Authentication successful",
            "user_id": result["user_id"],
            "email": result["email"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@app.get("/users")
async def list_users():
    """List all connected users"""
    users = await User.all()
    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "created_at": user.created_at
            }
            for user in users
        ]
    }


@app.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: int):
    """Deactivate a user account"""
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    await user.save()
    
    return {"message": f"User {user.email} deactivated"}


@app.post("/users/{user_id}/activate")
async def activate_user(user_id: int):
    """Activate a user account"""
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    await user.save()
    
    return {"message": f"User {user.email} activated"}


@app.post("/process/{user_id}")
async def manual_process_emails(user_id: int, background_tasks: BackgroundTasks):
    """Manually trigger email processing for a specific user"""
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    background_tasks.add_task(email_processor.process_user_emails, user)
    
    return {"message": f"Email processing started for {user.email}"}

@app.get("/knowledge/search")
async def search_knowledge(q: str):
    """Search knowledge base"""
    results = await rag_service.search_knowledge(q)
    return {"query": q, "results": results}


@app.get("/knowledge/info")
async def get_knowledge_info():
    """Get ChromaDB collection information"""
    return rag_service.get_collection_info()


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    from models import Email, UnhandledEmail, RefundRequest, NotFoundRefundRequest
    
    total_emails = await Email.all().count()
    unhandled_emails = await UnhandledEmail.all().count()
    refund_requests = await RefundRequest.all().count()
    not_found_refunds = await NotFoundRefundRequest.all().count()
    active_users = await User.filter(is_active=True).count()
    
    return {
        "total_emails_processed": total_emails,
        "unhandled_emails": unhandled_emails,
        "refund_requests": refund_requests,
        "not_found_refund_requests": not_found_refunds,
        "active_users": active_users,
        "processing_active": processing_active
    }


@app.get("/orders")
async def list_orders():
    """List all orders"""
    orders = await Order.all()
    return {
        "orders": [
            {
                "id": order.id,
                "order_id": order.order_id,
                "customer_email": order.customer_email,
                "amount": float(order.amount),
                "status": order.status,
                "refund_status": order.refund_status
            }
            for order in orders
        ]
    }


@app.post("/orders")
async def create_order(request: Request):
    """Create a new order"""
    data = await request.json()
    
    required_fields = ["order_id", "customer_email", "amount"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"{field} is required")
    
    # Check if order already exists
    existing = await Order.filter(order_id=data["order_id"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Order ID already exists")
    
    order = await Order.create(
        order_id=data["order_id"],
        customer_email=data["customer_email"],
        amount=data["amount"],
        status=data.get("status", "completed")
    )
    
    return {
        "message": "Order created successfully",
        "order": {
            "id": order.id,
            "order_id": order.order_id,
            "customer_email": order.customer_email,
            "amount": float(order.amount)
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        log_level="info"
    )