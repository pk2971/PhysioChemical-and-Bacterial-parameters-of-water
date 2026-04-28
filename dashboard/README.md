# Tirupati Water Quality Dashboard

Interactive Streamlit dashboard for physicochemical and bacterial analysis of water sources in Tirupati, with BIS IS 10500:2012 compliance checking.

## Features
- 🗺️ **Interactive map** — colour-coded markers by WQI, source type, E.coli status, or any parameter
- 📍 **Location detail** — full compliance table, radar chart, heavy metals bar chart per location
- 🔬 **Parameter explorer** — box plots, histograms, scatter plots with BIS limit lines
- 📊 **Overview** — exceedance counts, WQI distribution, compliance heatmap
- 🔗 **Correlations** — full Pearson correlation matrix + top correlates with WQI

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Cloud (free, permanent link)

1. Push this folder to a **public GitHub repo**
2. Go to https://share.streamlit.io → "New app"
3. Select your repo, set main file to `app.py`
4. Deploy — you'll get a shareable link in ~2 minutes

### Keep it awake (prevent sleep after 7 days)
- Sign up at https://uptimerobot.com (free)
- Add a new HTTP(s) monitor with your Streamlit URL
- Set interval to 5 minutes → dashboard never sleeps

## File structure
```
dashboard/
├── app.py            # Main dashboard
├── data.xlsx         # Water quality dataset
├── requirements.txt  # Python dependencies
└── README.md
```
