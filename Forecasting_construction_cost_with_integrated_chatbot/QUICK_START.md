# 🚀 Quick Start Guide - Construction Cost Estimator

## Prerequisites
- Python 3.8+
- Django 5.2+
- Required packages: pandas, numpy, scikit-learn, xgboost, matplotlib, google-generativeai

## Installation Steps

### 1. Install Dependencies
```bash
pip install django pandas numpy scikit-learn xgboost matplotlib google-generativeai
```

### 2. Navigate to Project Directory
```bash
cd "C:\Users\Prakash\Downloads\Machine Learning Model for Estimating Building Material and Labor Costs with Integrated chatbot\CODE\Forecasting_construction_cost_with_integrated_chatbot"
```

### 3. Run Migrations (if needed)
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Start the Server
```bash
python manage.py runserver
```

### 5. Access the Application
Open your browser and go to:
- **Homepage**: http://localhost:8000/
- **User Registration**: http://localhost:8000/UserRegister/
- **User Login**: http://localhost:8000/UserLogin/
- **Admin Login**: http://localhost:8000/Adminlogin/

## 🎯 User Journey

### Step 1: Register
1. Go to http://localhost:8000/UserRegister/
2. Fill in your details (name, email, password, etc.)
3. Submit the form
4. Wait for admin approval (status: "waiting")

### Step 2: Admin Approval
1. Admin logs in at http://localhost:8000/Adminlogin/
2. Admin activates your account
3. Your status changes to "active"

### Step 3: Login
1. Go to http://localhost:8000/UserLogin/
2. Enter your login ID and password
3. Access the dashboard

### Step 4: Use Features

#### 🤖 Train Model
1. Click "Training" in navigation
2. Click "Train Models Now" button
3. Wait for training to complete
4. View accuracy metrics and visualizations

#### 🔮 Predict Cost
1. Click "Prediction" in navigation
2. Fill in the form:
   - Area (sqft)
   - Number of floors
   - City (Mumbai, Delhi, Bangalore, Chennai, Hyderabad)
   - State
   - Material Quality (Low, Medium, High)
   - Building Type (Residential, Commercial)
   - Material Cost (₹)
   - Labor Cost (₹)
3. Click "Calculate Cost Prediction"
4. View predicted total cost

#### 💬 Use Chatbot
1. Click "Chatbot" in navigation
2. Try these queries:
   - "Hello" - Get started
   - "Help" - See capabilities
   - "Predict cost" - Interactive prediction
   - "Average cost in Mumbai" - Get statistics
   - "What factors affect cost?" - Get advice

## 🎤 Chatbot Features

### Voice Input
- Click the 🎤 microphone button
- Speak your question
- It will automatically send when you stop speaking

### Text-to-Speech
- Click the 🔊 speaker button to enable
- All bot responses will be read aloud
- Click again to disable

### Quick Actions
- Use pre-defined buttons for common queries
- Faster than typing

### Interactive Prediction
1. Say "predict cost" or "start prediction"
2. Answer 8 questions step by step:
   - Area in sqft
   - Number of floors
   - City
   - State
   - Material quality
   - Building type
   - Material cost
   - Labor cost
3. Get detailed prediction with breakdown

## 📊 Sample Queries for Chatbot

### Greetings
- "Hello"
- "Hi"
- "Hey"

### Help & Info
- "Help"
- "What can you do?"
- "Which cities are available?"
- "What building types do you support?"

### Statistics
- "Average cost in Mumbai"
- "Show me statistics for Delhi"
- "Residential building statistics"
- "High quality material cost"
- "Commercial building data"

### Predictions
- "Predict cost for 2000 sqft in Mumbai"
- "Estimate cost for 3000 sqft commercial in Bangalore"
- "Calculate cost for residential building"
- "Start prediction" (interactive mode)

### General Questions (AI-powered)
- "What factors affect construction cost?"
- "How can I reduce building costs?"
- "Best materials for residential construction"
- "Construction trends in India"

## 🔧 Troubleshooting

### Issue: "Account not activated"
**Solution**: Wait for admin to activate your account or contact admin

### Issue: "Dataset not found"
**Solution**: Ensure `construction_cost_dataset.csv` exists in `media/` folder

### Issue: "Gemini API error"
**Solution**: Check internet connection and API key in settings.py

### Issue: "Voice input not working"
**Solution**: Use Chrome or Edge browser (Safari/Firefox may not support speech recognition)

### Issue: "Plots not showing after training"
**Solution**: Ensure `static/plots/` directory exists and has write permissions

### Issue: "Import errors"
**Solution**: Install missing packages:
```bash
pip install pandas numpy scikit-learn xgboost matplotlib google-generativeai
```

## 📱 Browser Compatibility

### Fully Supported
- ✅ Chrome (recommended)
- ✅ Edge
- ✅ Firefox (except voice input)

### Partially Supported
- ⚠️ Safari (no voice input)

### Mobile
- ✅ Responsive design works on all mobile browsers
- ⚠️ Voice input may not work on all mobile browsers

## 🎨 Features Overview

### Frontend
- Modern gradient design
- Card-based layouts
- Smooth animations
- Responsive (mobile-friendly)
- Clean typography

### Backend
- Django 5.2
- SQLite database
- Session-based authentication
- ML models (Random Forest, XGBoost)
- Gemini AI integration

### Chatbot
- Rule-based responses
- ML predictions
- Dataset statistics
- AI-powered answers
- Voice input/output
- Interactive prediction mode

## 📈 Dataset Info

- **Total Projects**: 10,000+
- **Cities**: Mumbai, Delhi, Bangalore, Chennai, Hyderabad
- **Building Types**: Residential, Commercial
- **Material Qualities**: Low, Medium, High
- **Features**: Area, Floors, Location, Quality, Costs

## 🔐 Default Admin Credentials

Check your database or create a superuser:
```bash
python manage.py createsuperuser
```

## 💡 Tips

1. **Train the model first** before making predictions for best accuracy
2. **Use voice input** for hands-free chatbot interaction
3. **Enable auto-speak** to hear responses while multitasking
4. **Try quick action buttons** in chatbot for common queries
5. **Use interactive prediction** in chatbot for guided cost estimation

## 📞 Support

For issues or questions:
- Check PROJECT_SUMMARY.md for detailed documentation
- Review the code comments in views.py
- Test with sample data first

---

**Ready to use!** 🎉

Start the server and access http://localhost:8000/
