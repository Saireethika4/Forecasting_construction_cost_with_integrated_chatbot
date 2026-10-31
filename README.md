# Construction Cost Forecasting with Integrated Chatbot

A Django web app that estimates construction costs in India. It offers machine learning predictions for buildings, rates by construction type and site, a nearby labour search with contact details, and a chatbot.

## Run it

Requires Python 3.12. On macOS, XGBoost may also need `brew install libomp`.

```bash
cd Forecasting_construction_cost_with_integrated_chatbot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then edit the values
python manage.py migrate
python manage.py seed_sample_labour   # optional demo listings
python manage.py runserver
```

Open http://127.0.0.1:8000. New users can log in after an admin activates them at `/Adminlogin/`. The admin login comes from `ADMIN_LOGIN` and `ADMIN_PASSWORD` in `.env`; change the default `admin` / `admin` before sharing the app.

Run the tests with `python manage.py test`.

## Features

| Area | What it does |
| --- | --- |
| Prediction (`/predict/`) | Estimates material, labour and total cost from area, floors, city, quality, building type and site. Known quotes can replace the estimates. |
| Training (`/train/`) | Trains Random Forest and XGBoost, compares them and keeps the better model. |
| Rates (`/rates/`) | Prices buildings, bridges, roads, tunnels and retaining walls on plains, hill stations, water bodies, coastal, desert, forest and dense urban sites. |
| Find Labour (`/labour/`) | Searches by place or current location, trade and radius, sorted by distance, with contact details. It also shows public OpenStreetMap listings. |
| List as Labour (`/labour/register/`) | Lets workers add themselves, with consent. Listings appear after admin approval. |
| Chatbot (`/chat/`) | Handles guided predictions, rates, labour, and statistics. Other questions go to Gemini when a key is set. |
| Admin | Manages users, labour listings and all rates. |

## Limits of the data

- **The dataset looks formula-generated.** Costs follow fixed rates by city and quality, so the near-perfect model scores will not carry over to real projects. Floors and building type have almost no effect on its costs.
- **Machine learning covers buildings only.** The dataset has no bridges, roads or tunnels, and no hill or water sites, so those figures come from the rate table.
- **Rates are indicative.** Road and tunnel starting rates are based on rough published figures. Bridge, retaining wall and site differences are assumptions. Replace them with a schedule of rates or quotes from the admin Rates page before relying on them.
- **Sample labour listings are placeholders.** Remove them with `python manage.py seed_sample_labour --clear`, and add real listings through the admin page or the public form.

## External services

- **Gemini (optional):** set `GEMINI_API_KEY` in `.env`. Everything else in the chatbot works without it.
- **OpenStreetMap Nominatim and Overpass:** used for places outside the built-in list and for public listings. They need no key, but are shared public services that are sometimes busy. The search sends the location being searched to them.

This setup is for local development. A public deployment also needs `DJANGO_DEBUG=False`, a production web server, and static and media file hosting.
