# 📧 Customer Support Email Agent

An intelligent email automation system that processes customer emails using AI categorization, RAG-powered responses, and automated refund processing.

## ✨ Features

- **🤖 AI Email Categorization** - Automatically categorizes emails using Google Gemini
- **📚 RAG-Powered Responses** - Answers questions using knowledge base search
- **💰 Automated Refund Processing** - Handles refund requests with order verification  
- **📊 Real-time Monitoring** - Tracks all email processing and system statistics
- **🔄 Background Processing** - Continuous email monitoring without blocking API

---

## 🚀 Quick Start

### Prerequisites

Before you begin, ensure you have:

- **Python 3.9+** installed on your system
- **PostgreSQL** database running locally
- **Google Cloud Project** with Gmail API enabled
- **Gemini API key** from Google AI Studio

### Installation

#### 1. **Environment Setup**
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. **Database Configuration**
```sql
-- Connect to PostgreSQL and run:
CREATE DATABASE customer_support;
CREATE USER your_username WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE customer_support TO your_username;
```

#### 3. **Google Gmail API Setup**

1. Navigate to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the **Gmail API**
4. Create **OAuth 2.0 credentials**:
   - Application type: `Web application`
   - Authorized redirect URIs: `http://localhost:8000/auth/callback`
5. Download credentials JSON and save Client ID and Secret

#### 4. **Gemini API Key**

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Generate a new API key
3. Copy the key for environment configuration

#### 5. **Environment Variables**
```bash
# Copy example environment file
cp .env.example .env
```

Edit your `.env` file:
```env
# Database Configuration
DATABASE_URL=postgres://your_username:your_password@localhost:5432/customer_support

# Google API Credentials
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# Gemini AI API
GEMINI_API_KEY=your_gemini_api_key

# Application Settings
APP_HOST=localhost
APP_PORT=8000
```

#### 6. **Database Initialization**
```bash
# Initialize database migrations
aerich init -t config.TORTOISE_ORM
aerich init-db

# For future model changes:
# aerich migrate && aerich upgrade
```

#### 7. **Knowledge Base Setup**
```bash
# Create knowledge base directory
mkdir -p knowledge_base
# Sample knowledge file will be auto-generated
```

---

## 🎯 Running the Application

### Start the Server
```bash
python main.py
```
**Server runs on:** `http://localhost:8000`

---

## 📚 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Application info and available endpoints |
| `GET` | `/auth` | Get Gmail OAuth authorization URL |
| `GET` | `/auth/callback` | OAuth callback handler (automatic) |
| `GET` | `/users` | List all connected Gmail accounts |
| `POST` | `/users/{user_id}/deactivate` | Pause email processing for user |
| `POST` | `/users/{user_id}/activate` | Resume email processing for user |
| `POST` | `/process/{user_id}` | Manually trigger email processing |
| `GET` | `/knowledge/search?q=query` | Search knowledge base |
| `GET` | `/stats` | View system statistics |
| `GET` | `/orders` | List all orders |
| `POST` | `/orders` | Create new order record |

---

## 🔄 Usage Workflow

### 1. **Connect Gmail Account**
```bash
# Get authorization URL
curl http://localhost:8000/auth

# Visit the returned auth_url in your browser
# Complete OAuth authorization
# Email processing starts automatically!!!
```

### 2. **Monitor System**
```bash
# Check system statistics
curl http://localhost:8000/stats

# View processed emails
curl http://localhost:8000/users

# View extracted orders
curl http://localhost:8000/orders
```

---

## ⚙️ How It Works

### **Email Processing Pipeline**

```
📨 New Email → 🤖 AI Categorization → 🔄 Processing → 📤 Response
```

1. **🔍 Continuous Monitoring** - Checks for unread emails every 30 seconds
2. **🏷️ AI Categorization** - Uses Gemini to classify emails:
   - `QUESTION` - Customer inquiries
   - `REFUND` - Refund requests  
   - `OTHER` - Requires human review
3. **⚡ Smart Processing**:
   - **Questions**: RAG search through knowledge base → Automated response
   - **Refunds**: Order ID extraction → Database verification → Processing
   - **Other**: Flagged for human review with importance level
4. **📧 Response Generation** - Sends contextual automated replies
5. **📊 Complete Tracking** - All interactions logged in PostgreSQL

### **Database Schema**

| Table | Purpose |
|-------|---------|
| `users` | Connected Gmail accounts and settings |
| `emails` | All processed email records |
| `orders` | Order database for refund verification |
| `unhandled_emails` | Questions without available answers |
| `refund_requests` | Processed refund tracking |
| `not_found_refund_requests` | Invalid refund attempt logs |
| `knowledge_base` | RAG content and embeddings |

---

## 🧪 Test Email Examples

### **📋 QUESTION Category** *(RAG-Powered Responses)*

**Example 1: Shipping Inquiry**
```
Subject: How long does shipping take?
Body: Hi, I placed an order yesterday and wondering when it will arrive. What are your shipping times?

✅ Agent Response: Searches knowledge base → Finds shipping policy → 
"We offer free shipping on orders over $50. Standard shipping takes 3-7 business days..."
```

**Example 2: Return Policy**
```
Subject: Return policy question  
Body: Can I return an item I bought 2 weeks ago? What's your return policy?

✅ Agent Response: Locates return policy → 
"Our return policy allows returns within 30 days of purchase. Items must be unused..."
```

**Example 3: Account Issues**
```
Subject: Account login issues
Body: I can't log into my account. Forgot my password. Help!

✅ Agent Response: Finds account help documentation →
"If you're having trouble accessing your account, try resetting your password..."
```

### **💰 REFUND Category** *(Order Processing)*

**Example 4: Valid Refund Request**
```
Subject: Refund request
Body: I want a refund for order ORD001. The product doesn't work.

✅ Agent Response: Extracts "ORD001" → Verifies in database → 
"Thank you for contacting us regarding order ORD001. We have processed your refund request and the refund will be completed within 3 days..."
```

**Example 5: Missing Order ID**
```
Subject: I want my money back
Body: This product is terrible, I want a refund!

✅ Agent Response: No order ID detected → 
"We'd be happy to help with your refund request. Could you please provide your order ID so we can process this for you?"
```

**Example 6: Invalid Order ID**
```
Subject: Refund request
Body: Please refund order INVALID123

✅ Agent Response: Database lookup fails → 
"We cannot find order INVALID123 in our system. Please check your order ID..."
```

### **⚠️ OTHER Category** *(Human Review Required)*

**Example 7: Complaint**
```
Subject: You guys suck!!!
Body: Worst company ever! I'm never buying from you again!

✅ Agent Response: Categorized as "OTHER" → Flagged as HIGH importance → 
Requires human review (no automated response)
```
