from django.shortcuts import render
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from django.conf import settings

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBRegressor

from django.contrib import messages
from django.shortcuts import render, redirect
from .models import UserRegistrationModel

def UserRegisterActions(request):
    if request.method == 'POST':

        image = request.FILES.get('image')

        user = UserRegistrationModel(
            name=request.POST['name'],
            loginid=request.POST['loginid'],
            password=request.POST['password'],
            mobile=request.POST.get('mobile', ''),
            email=request.POST['email'],
            locality=request.POST.get('locality', ''),
            address=request.POST.get('address', ''),
            image=image,
            status='waiting'
        )

        user.save()
        messages.success(request, "Registration successful! Please wait for admin approval.")
        return redirect('UserLogin')

    return render(request, 'userRegistration.html')


from django.shortcuts import render, redirect
from django.contrib import messages
from .models import UserRegistrationModel

def UserLoginCheck(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = UserRegistrationModel.objects.get(email=email, password=password)
            if user.status == 'active':
                request.session['id'] = user.id
                request.session['name'] = user.name
                return redirect('UserHome')
            elif user.status == 'waiting':
                messages.warning(request, "Your account is pending admin approval.")
            else:
                messages.error(request, "Your account has been deactivated.")
        except UserRegistrationModel.DoesNotExist:
            messages.error(request, "Invalid email or password.")
        
        return redirect('UserLogin')

    return render(request, 'login.html')


def UserHome(request):
    user_id = request.session.get('id')
    if not user_id:
        return redirect('UserLogin')
    
    user = UserRegistrationModel.objects.get(id=user_id)
    return render(request, 'users/userHome.html', {'user': user})


def base(request):
    return render(request, 'base.html')


def index(request):
    return render(request, "index.html")


def logout_view(request):
    request.session.flush()
    return redirect('index')

# ===============================
# 🟢 TRAINING VIEW
# ===============================
def train_model_view(request):

    context = {}

    if request.method == "POST":

        df = pd.read_csv(r'media\construction_cost_dataset.csv')

        # ===============================
        # 🔹 Encoding
        # ===============================
        from sklearn.preprocessing import LabelEncoder

        le_city = LabelEncoder()
        le_state = LabelEncoder()
        le_quality = LabelEncoder()
        le_type = LabelEncoder()

        df['City'] = le_city.fit_transform(df['City'])
        df['State'] = le_state.fit_transform(df['State'])
        df['Material_Quality'] = le_quality.fit_transform(df['Material_Quality'])
        df['Building_Type'] = le_type.fit_transform(df['Building_Type'])

        # ===============================
        # 🔥 PREPARE FEATURES AND TARGET
        # ===============================
        # Keep all features including Material_Cost and Labor_Cost for prediction
        X = df.drop(['Total_Cost'], axis=1)
        y = df['Total_Cost']

        # ===============================
        # 🔹 Train-Test Split
        # ===============================
        from sklearn.model_selection import train_test_split

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42
        )

        # ===============================
        # 🌲 Random Forest (STRONG REGULARIZATION)
        # ===============================
        from sklearn.ensemble import RandomForestRegressor

        rf_model = RandomForestRegressor(
            n_estimators=30,
            max_depth=4,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42
        )

        rf_model.fit(X_train, y_train)

        rf_train = rf_model.predict(X_train)
        rf_test = rf_model.predict(X_test)

        from sklearn.metrics import r2_score, mean_absolute_error

        rf_train_score = r2_score(y_train, rf_train)
        rf_test_score = r2_score(y_test, rf_test)
        rf_mae = mean_absolute_error(y_test, rf_test)

        # ===============================
        # ⚡ XGBoost (REGULARIZED)
        # ===============================
        from xgboost import XGBRegressor

        xgb_model = XGBRegressor(
            n_estimators=30,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.7,
            colsample_bytree=0.7,
            reg_alpha=1,
            reg_lambda=1,
            random_state=42
        )

        xgb_model.fit(X_train, y_train)

        xgb_train = xgb_model.predict(X_train)
        xgb_test = xgb_model.predict(X_test)

        xgb_train_score = r2_score(y_train, xgb_train)
        xgb_test_score = r2_score(y_test, xgb_test)
        xgb_mae = mean_absolute_error(y_test, xgb_test)

        # ===============================
        # 📊 VISUALIZATION
        # ===============================
        import matplotlib.pyplot as plt
        import os

        os.makedirs('static/plots', exist_ok=True)

        plt.figure()
        plt.scatter(y_test, xgb_test)
        plt.xlabel("Actual")
        plt.ylabel("Predicted")
        plt.title("Actual vs Predicted")
        plt.savefig('static/plots/actual_vs_pred.png')
        plt.close()

        plt.figure()
        plt.hist(y_test - xgb_test, bins=30)
        plt.title("Error Distribution")
        plt.savefig('static/plots/error.png')
        plt.close()

        plt.figure()
        plt.barh(X.columns, xgb_model.feature_importances_)
        plt.title("Feature Importance")
        plt.savefig('static/plots/feature.png')
        plt.close()

        # ===============================
        # 📤 Context
        # ===============================
        context = {
            'rf_train_score': round(rf_train_score, 3),
            'rf_test_score': round(rf_test_score, 3),
            'rf_mae': round(rf_mae, 2),

            'xgb_train_score': round(xgb_train_score, 3),
            'xgb_test_score': round(xgb_test_score, 3),
            'xgb_mae': round(xgb_mae, 2),
        }

    return render(request, 'users/training.html', context)


# ===============================
# 🔮 PREDICTION VIEW (NO PICKLE)
# ===============================
def predict_view(request):

    prediction = None

    # ALWAYS load dataset
    df = pd.read_csv(os.path.join(settings.MEDIA_ROOT, 'construction_cost_dataset.csv'))

    # Dropdown values
    cities = df['City'].unique()
    states = df['State'].unique()
    qualities = df['Material_Quality'].unique()
    types = df['Building_Type'].unique()

    if request.method == "POST":

        # Encoding
        le_city = LabelEncoder()
        le_state = LabelEncoder()
        le_quality = LabelEncoder()
        le_type = LabelEncoder()

        df['City'] = le_city.fit_transform(df['City'])
        df['State'] = le_state.fit_transform(df['State'])
        df['Material_Quality'] = le_quality.fit_transform(df['Material_Quality'])
        df['Building_Type'] = le_type.fit_transform(df['Building_Type'])

        X = df.drop('Total_Cost', axis=1)
        y = df['Total_Cost']

        model = XGBRegressor()
        model.fit(X, y)

        # Get input
        area = int(request.POST['area'])
        floors = int(request.POST['floors'])
        city = le_city.transform([request.POST['city']])[0]
        state = le_state.transform([request.POST['state']])[0]
        quality = le_quality.transform([request.POST['quality']])[0]
        btype = le_type.transform([request.POST['btype']])[0]
        material_cost = float(request.POST['material_cost'])
        labor_cost = float(request.POST['labor_cost'])

        input_data = np.array([[area, floors, city, state, quality, btype, material_cost, labor_cost]])

        prediction = model.predict(input_data)[0]

    return render(request, 'users/prediction.html', {
        'prediction': prediction,
        'cities': cities,
        'states': states,
        'qualities': qualities,
        'types': types
    })

from django.http import JsonResponse
from django.conf import settings

import re

from django.http import JsonResponse
from django.conf import settings
from google import genai
import re

def chatbot_view(request):
    """Render the chatbot page"""
    return render(request, 'chatbot.html')

def chatbot_response(request):
    user_message = request.GET.get('message', '').lower()
    mode = request.GET.get('mode', '')

    try:
        # Load dataset for context
        df = pd.read_csv(os.path.join(settings.MEDIA_ROOT, 'construction_cost_dataset.csv'))
        
        # Handle interactive prediction mode
        if mode == 'predict':
            prediction_result = handle_interactive_prediction(request, df)
            return JsonResponse({'response': prediction_result})
        
        # STEP 1: Rule-based responses (Fixed Q&A)
        rule_response = handle_rule_based_query(user_message, df)
        if rule_response:
            return JsonResponse({'response': rule_response})
        
        # STEP 2: ML-based prediction
        if any(word in user_message for word in ['predict', 'estimate', 'cost for', 'price for', 'calculate']):
            ml_result = handle_ml_prediction(user_message, df)
            if ml_result:
                return JsonResponse({'response': ml_result})
        
        # STEP 3: Dataset statistics queries
        if any(word in user_message for word in ['average', 'mean', 'statistics', 'data', 'info about']):
            stats_result = handle_statistics_query(user_message, df)
            if stats_result:
                return JsonResponse({'response': stats_result})
        
        # STEP 4: AI-based response (Gemini) for complex queries
        ai_response = handle_ai_query(user_message, df)
        return JsonResponse({'response': ai_response})

    except Exception as e:
        reply = "I'm here to help with construction cost queries. Could you please rephrase your question?"
        return JsonResponse({'response': reply})

def handle_interactive_prediction(request, df):
    """Handle interactive step-by-step prediction"""
    try:
        # Get all parameters
        area = int(request.GET.get('area', 0))
        floors = int(request.GET.get('floors', 0))
        city = request.GET.get('city', '').strip()
        state = request.GET.get('state', '').strip()
        material_quality = request.GET.get('material_quality', '').strip()
        building_type = request.GET.get('building_type', '').strip()
        material_cost = float(request.GET.get('material_cost', 0))
        labor_cost = float(request.GET.get('labor_cost', 0))
        
        # Prepare data for ML prediction
        le_city = LabelEncoder()
        le_state = LabelEncoder()
        le_quality = LabelEncoder()
        le_type = LabelEncoder()
        
        df_encoded = df.copy()
        df_encoded['City'] = le_city.fit_transform(df_encoded['City'])
        df_encoded['State'] = le_state.fit_transform(df_encoded['State'])
        df_encoded['Material_Quality'] = le_quality.fit_transform(df_encoded['Material_Quality'])
        df_encoded['Building_Type'] = le_type.fit_transform(df_encoded['Building_Type'])
        
        # Train model
        X = df_encoded.drop('Total_Cost', axis=1)
        y = df_encoded['Total_Cost']
        model = XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42)
        model.fit(X, y)
        
        # Encode user inputs
        try:
            city_encoded = le_city.transform([city])[0]
        except:
            city_encoded = 0
            
        try:
            state_encoded = le_state.transform([state])[0]
        except:
            state_encoded = 0
            
        try:
            quality_encoded = le_quality.transform([material_quality])[0]
        except:
            quality_encoded = 1
            
        try:
            type_encoded = le_type.transform([building_type])[0]
        except:
            type_encoded = 0
        
        # Make prediction
        input_data = np.array([[area, floors, city_encoded, state_encoded, quality_encoded, type_encoded, material_cost, labor_cost]])
        prediction = model.predict(input_data)[0]
        
        # Get similar projects for comparison
        similar = df[
            (df['Area_sqft'].between(area * 0.8, area * 1.2)) &
            (df['City'] == city) &
            (df['Building_Type'] == building_type)
        ]
        
        result = f"""**🎯 Cost Prediction Complete!**

**Your Project Details:**
• Area: {area:,} sqft
• Floors: {floors}
• City: {city}
• State: {state}
• Material Quality: {material_quality}
• Building Type: {building_type}
• Material Cost: ₹{material_cost:,.0f}
• Labor Cost: ₹{labor_cost:,.0f}

**💰 Predicted Total Cost: ₹{prediction:,.0f}**

**Cost Breakdown:**
• Material Cost: ₹{material_cost:,.0f} ({(material_cost/prediction*100):.1f}%)
• Labor Cost: ₹{labor_cost:,.0f} ({(labor_cost/prediction*100):.1f}%)
• Other Costs: ₹{(prediction-material_cost-labor_cost):,.0f} ({((prediction-material_cost-labor_cost)/prediction*100):.1f}%)

**Per Square Foot: ₹{(prediction/area):,.0f}/sqft**
"""
        
        if len(similar) > 0:
            avg_similar = similar['Total_Cost'].mean()
            result += f"""
**📊 Market Comparison:**
Based on {len(similar)} similar projects in {city}:
• Average cost: ₹{avg_similar:,.0f}
• Your estimate vs market: {((prediction/avg_similar - 1) * 100):+.1f}%
"""
        
        result += "\n\nWant another prediction? Just say 'start prediction' or 'predict cost'!"
        
        return result
        
    except Exception as e:
        return f"Error making prediction: {str(e)}. Please ensure all values are entered correctly."

def handle_rule_based_query(message, df):
    """Rule-based responses for common fixed questions"""
    
    # Greeting responses
    if any(word in message for word in ['hello', 'hi', 'hey', 'greetings']):
        return """Hello! 👋 I'm your Construction Cost Assistant.

I can help you with:
• **Cost Predictions** - Estimate project costs
• **Dataset Statistics** - Get insights from 10,000+ projects
• **Construction Advice** - Materials, planning, best practices

Try asking:
- "Predict cost for 2000 sqft in Mumbai"
- "Average cost in Delhi"
- "What factors affect construction cost?"

How can I assist you today?"""
    
    # Help/capabilities
    if any(word in message for word in ['help', 'what can you do', 'capabilities', 'features']):
        return """**I can assist you with:**

**1. Cost Predictions (ML-based)**
- Estimate costs based on area, location, building type
- Example: "Estimate cost for 3000 sqft commercial in Bangalore"

**2. Dataset Statistics**
- City-wise analysis
- Building type comparisons
- Material quality insights
- Example: "Show me statistics for Chennai"

**3. Construction Guidance (AI-powered)**
- Material recommendations
- Cost optimization tips
- Project planning advice
- Best practices

**4. Quick Facts**
- Available cities: Mumbai, Delhi, Bangalore, Chennai, Hyderabad
- Building types: Residential, Commercial
- Material qualities: Low, Medium, High

What would you like to know?"""
    
    # Available cities
    if 'which cities' in message or 'available cities' in message or 'supported cities' in message:
        cities = df['City'].unique()
        return f"""**Available Cities in Database:**

{chr(10).join([f'• {city}' for city in cities])}

We have data from {len(df)} construction projects across these cities.

Ask me about any city for detailed statistics!"""
    
    # Building types
    if 'building types' in message or 'types of buildings' in message:
        types = df['Building_Type'].unique()
        type_counts = df['Building_Type'].value_counts()
        return f"""**Building Types Available:**

{chr(10).join([f'• **{btype}**: {type_counts[btype]} projects' for btype in types])}

I can provide cost estimates and statistics for any building type."""
    
    # Material quality
    if 'material quality' in message or 'quality levels' in message:
        qualities = df['Material_Quality'].unique()
        return f"""**Material Quality Levels:**

{chr(10).join([f'• **{quality}** - Avg cost: ₹{df[df["Material_Quality"]==quality]["Total_Cost"].mean():,.0f}' for quality in qualities])}

Higher quality materials increase costs but improve durability and aesthetics."""
    
    # Cost factors
    if 'factors' in message and 'cost' in message:
        return """**Key Factors Affecting Construction Cost:**

**1. Location (City/State)**
- Urban areas typically cost more
- Local material availability matters

**2. Building Size & Floors**
- Larger area = higher total cost
- Multi-story buildings need stronger foundations

**3. Material Quality**
- Low: Budget-friendly, basic materials
- Medium: Standard quality, good durability
- High: Premium materials, best finish

**4. Building Type**
- Commercial: Higher specifications
- Residential: Standard requirements

**5. Labor & Material Costs**
- Varies by region and season
- Skilled labor commands premium rates

Want a specific cost estimate? Just ask!"""
    
    # Cost range
    if 'cost range' in message or 'price range' in message:
        min_cost = df['Total_Cost'].min()
        max_cost = df['Total_Cost'].max()
        avg_cost = df['Total_Cost'].mean()
        return f"""**Construction Cost Range (from our database):**

• **Minimum**: ₹{min_cost:,.0f}
• **Maximum**: ₹{max_cost:,.0f}
• **Average**: ₹{avg_cost:,.0f}

Costs vary based on location, size, and quality.

Want a specific estimate? Tell me your requirements!"""
    
    return None

def handle_ml_prediction(message, df):
    """ML-based cost prediction from natural language"""
    try:
        numbers = re.findall(r'\d+', message)
        
        # Extract city
        cities = df['City'].unique()
        mentioned_city = None
        for city in cities:
            if city.lower() in message:
                mentioned_city = city
                break
        
        # Extract building type
        building_types = df['Building_Type'].unique()
        mentioned_type = None
        for btype in building_types:
            if btype.lower() in message:
                mentioned_type = btype
                break
        
        # Extract material quality
        qualities = df['Material_Quality'].unique()
        mentioned_quality = None
        for quality in qualities:
            if quality.lower() in message:
                mentioned_quality = quality
                break
        
        if numbers and len(numbers) >= 1:
            area = int(numbers[0])
            floors = int(numbers[1]) if len(numbers) > 1 else 2
            
            # Prepare data for ML prediction
            le_city = LabelEncoder()
            le_state = LabelEncoder()
            le_quality = LabelEncoder()
            le_type = LabelEncoder()
            
            df_encoded = df.copy()
            df_encoded['City'] = le_city.fit_transform(df_encoded['City'])
            df_encoded['State'] = le_state.fit_transform(df_encoded['State'])
            df_encoded['Material_Quality'] = le_quality.fit_transform(df_encoded['Material_Quality'])
            df_encoded['Building_Type'] = le_type.fit_transform(df_encoded['Building_Type'])
            
            # Train quick model
            X = df_encoded.drop('Total_Cost', axis=1)
            y = df_encoded['Total_Cost']
            model = XGBRegressor(n_estimators=50, max_depth=5, random_state=42)
            model.fit(X, y)
            
            # Get similar projects for estimation
            similar = df[df['Area_sqft'].between(area * 0.8, area * 1.2)]
            if mentioned_city:
                similar = similar[similar['City'] == mentioned_city]
            if mentioned_type:
                similar = similar[similar['Building_Type'] == mentioned_type]
            if mentioned_quality:
                similar = similar[similar['Material_Quality'] == mentioned_quality]
            
            if len(similar) > 0:
                # Use average values from similar projects
                avg_material = similar['Material_Cost'].mean()
                avg_labor = similar['Labor_Cost'].mean()
                
                # Prepare input
                city_encoded = le_city.transform([mentioned_city])[0] if mentioned_city else le_city.transform([df['City'].mode()[0]])[0]
                state_encoded = le_state.transform([df[df['City']==mentioned_city]['State'].iloc[0]])[0] if mentioned_city else 0
                quality_encoded = le_quality.transform([mentioned_quality])[0] if mentioned_quality else 1
                type_encoded = le_type.transform([mentioned_type])[0] if mentioned_type else 0
                
                input_data = np.array([[area, floors, city_encoded, state_encoded, quality_encoded, type_encoded, avg_material, avg_labor]])
                
                # ML Prediction
                ml_prediction = model.predict(input_data)[0]
                
                # Statistical range
                avg_cost = similar['Total_Cost'].mean()
                min_cost = similar['Total_Cost'].min()
                max_cost = similar['Total_Cost'].max()
                
                return f"""**🤖 ML-Based Cost Prediction**

**Project Details:**
- Area: {area} sqft
- Floors: {floors}
{f'- City: {mentioned_city}' if mentioned_city else ''}
{f'- Type: {mentioned_type}' if mentioned_type else ''}
{f'- Quality: {mentioned_quality}' if mentioned_quality else ''}

**ML Model Prediction:** ₹{ml_prediction:,.0f}

**Statistical Analysis ({len(similar)} similar projects):**
- Average: ₹{avg_cost:,.0f}
- Range: ₹{min_cost:,.0f} - ₹{max_cost:,.0f}
- Cost per sqft: ₹{(avg_cost/area):,.0f}

**Breakdown Estimate:**
- Material Cost: ~₹{avg_material:,.0f}
- Labor Cost: ~₹{avg_labor:,.0f}

💡 For precise prediction with all parameters, visit the Prediction page."""
        
        return None
    except Exception as e:
        return None

def handle_ai_query(message, df):
    """AI-based response using Gemini for complex queries"""
    try:
        dataset_context = f"""
Dataset Summary:
- Total projects: {len(df)}
- Cities: {', '.join(df['City'].unique())}
- States: {', '.join(df['State'].unique())}
- Building types: {', '.join(df['Building_Type'].unique())}
- Material qualities: {', '.join(df['Material_Quality'].unique())}
- Average cost: ₹{df['Total_Cost'].mean():,.0f}
- Cost range: ₹{df['Total_Cost'].min():,.0f} - ₹{df['Total_Cost'].max():,.0f}
- Average area: {df['Area_sqft'].mean():.0f} sqft
"""

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""You are an expert construction cost assistant with access to real Indian construction project data.

{dataset_context}

User question: {message}

Provide helpful, accurate, and concise information about construction costs, materials, and project planning. 
Use the dataset context to give data-driven insights.
Keep responses practical and actionable.
If suggesting costs, mention they are estimates and actual costs may vary."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:
        return "I'm here to help with construction queries. Could you please rephrase your question?"

def handle_prediction_query(message, df):
    """Handle prediction requests from natural language"""
    try:
        # Extract numbers (could be area, floors)
        numbers = re.findall(r'\d+', message)
        
        # Check for city mentions
        cities = df['City'].unique()
        mentioned_city = None
        for city in cities:
            if city.lower() in message:
                mentioned_city = city
                break
        
        # Check for building type
        building_types = df['Building_Type'].unique()
        mentioned_type = None
        for btype in building_types:
            if btype.lower() in message:
                mentioned_type = btype
                break
        
        # If we have enough info, provide a rough estimate
        if numbers and len(numbers) >= 1:
            area = int(numbers[0])
            
            # Filter similar projects
            similar = df[df['Area_sqft'].between(area * 0.8, area * 1.2)]
            
            if mentioned_city:
                similar = similar[similar['City'] == mentioned_city]
            
            if mentioned_type:
                similar = similar[similar['Building_Type'] == mentioned_type]
            
            if len(similar) > 0:
                avg_cost = similar['Total_Cost'].mean()
                min_cost = similar['Total_Cost'].min()
                max_cost = similar['Total_Cost'].max()
                
                return f"""Based on similar projects in our database:

**Estimated Cost Range:** ₹{min_cost:,.0f} - ₹{max_cost:,.0f}
**Average Cost:** ₹{avg_cost:,.0f}

This is based on {len(similar)} similar projects{' in ' + mentioned_city if mentioned_city else ''}{' for ' + mentioned_type if mentioned_type else ''}.

For a precise prediction, please visit the Prediction page with complete details:
- Area (sqft)
- Number of floors
- City and State
- Material quality (Low/Medium/High)
- Building type (Residential/Commercial)
- Material and labor costs"""
        
        return None
    except:
        return None

def handle_statistics_query(message, df):
    """Handle statistical queries about the dataset"""
    try:
        # City-specific stats
        for city in df['City'].unique():
            if city.lower() in message:
                city_data = df[df['City'] == city]
                return f"""**{city} Construction Statistics:**

- Total projects: {len(city_data)}
- Average cost: ₹{city_data['Total_Cost'].mean():,.0f}
- Average area: {city_data['Area_sqft'].mean():.0f} sqft
- Cost range: ₹{city_data['Total_Cost'].min():,.0f} - ₹{city_data['Total_Cost'].max():,.0f}
- Most common building type: {city_data['Building_Type'].mode()[0]}"""
        
        # Building type stats
        for btype in df['Building_Type'].unique():
            if btype.lower() in message:
                type_data = df[df['Building_Type'] == btype]
                return f"""**{btype} Building Statistics:**

- Total projects: {len(type_data)}
- Average cost: ₹{type_data['Total_Cost'].mean():,.0f}
- Average area: {type_data['Area_sqft'].mean():.0f} sqft
- Average floors: {type_data['Floors'].mean():.1f}
- Cost per sqft: ₹{(type_data['Total_Cost'] / type_data['Area_sqft']).mean():.0f}"""
        
        # Material quality stats
        for quality in df['Material_Quality'].unique():
            if quality.lower() in message:
                quality_data = df[df['Material_Quality'] == quality]
                return f"""**{quality} Quality Material Statistics:**

- Total projects: {len(quality_data)}
- Average cost: ₹{quality_data['Total_Cost'].mean():,.0f}
- Average material cost: ₹{quality_data['Material_Cost'].mean():,.0f}
- Average labor cost: ₹{quality_data['Labor_Cost'].mean():,.0f}"""
        
        return None
    except:
        return None
    