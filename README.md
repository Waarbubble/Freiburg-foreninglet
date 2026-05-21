# Freiburg ForeningLet

Member portal helper app for Freiburg using Streamlit and the ForeningLet/Bifrost member portal.

## Running version

The deployed app is available at: https://freiburg.streamlit.app/

## Requirements

- Python 3.9+ (recommended: 3.10 or newer)
- `pip`
- Internet access (the app connects to `https://bifrost.foreninglet.dk`)

## Install dependencies

From the repository root:

```bash
python -m pip install -r requirements.txt
```

## Run from CLI

This repository includes a CLI script (`user-info.py`) that can log in and fetch user/event data.

### Option 1: pass credentials as arguments

```bash
python user-info.py "<EMAIL>" "<PASSWORD>"
```

### Option 2: use environment variables

Set environment variables:

```bash
export EMAIL="<EMAIL>"
export PASSWORD="<PASSWORD>"
python user-info.py
```

Or create a `.env` file in the project root:

```env
EMAIL=<EMAIL>
PASSWORD=<PASSWORD>
```

Then run:

```bash
python user-info.py
```

If credentials are not provided through args or environment, the script will prompt for them.

## Run the Streamlit app locally

```bash
streamlit run user-interface.py
```

Then open the local URL shown in your terminal (usually `http://localhost:8501`).
