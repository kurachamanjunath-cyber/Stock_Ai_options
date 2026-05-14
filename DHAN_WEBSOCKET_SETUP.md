# Dhan WebSocket Setup Guide

This guide will help you enable real-time live data streaming via Dhan WebSocket.

## 🚀 Quick Setup (5 minutes)

### Step 1: Get Dhan Account
1. Visit https://dhanhq.com
2. Sign up (free account)
3. Complete KYC verification
4. Log in to dashboard

### Step 2: Get API Credentials
1. Go to Dashboard → API Settings
2. Copy your **API Key**
3. Copy your **Client ID**
4. Make sure API is enabled

### Step 3: Install WebSocket Package
```bash
pip install websocket-client python-dotenv
```

### Step 4: Create .env File
In the project root, create a file named `.env`:
```
DHAN_API_KEY=your_api_key_here
DHAN_CLIENT_ID=your_client_id_here
```

Replace:
- `your_api_key_here` → Your actual API key from Dhan
- `your_client_id_here` → Your actual Client ID from Dhan

### Step 5: Restart the App
```bash
streamlit run app.py
```

✅ Done! You should see **"✅ WebSocket Connected"** in the sidebar.

---

## 🔍 Verify Connection

### Check Status in Sidebar
- ✅ **✅ WebSocket Connected** → Real-time data is active
- ⚠️ **⚠️ WebSocket Offline** → Fallback to yfinance (slower)
- ❌ **❌ Credentials not found** → Check your `.env` file

### Troubleshooting

**Problem: WebSocket Offline**
- Check if `websocket-client` is installed: `pip install websocket-client`
- Verify `.env` file exists with correct credentials
- Make sure API is enabled in Dhan dashboard
- Check internet connection

**Problem: "Credentials not found"**
- Verify `.env` file is in the project root (same folder as `app.py`)
- Check exact format: 
  ```
  DHAN_API_KEY=xxxx
  DHAN_CLIENT_ID=yyyy
  ```
- No extra spaces or quotes needed

**Problem: Connection timeout**
- Check if Dhan servers are up (https://dhanhq.com)
- Try restarting the app
- Check firewall/proxy settings

---

## 📊 What You Get

### Real-Time Updates
- **Sub-second latency** - Data updates every 0-1 seconds
- **MCX Commodities** - Live from MCX exchange
- **NIFTY/SENSEX** - Live from NSE/BSE
- **Options Chains** - Real premiums and Greeks

### Benefits
- 🚀 Faster signals - React to market instantly
- 💰 Better entry prices - Based on actual live data
- ⚡ Accurate targets - Real support/resistance
- 📊 Professional grade - Same data as professional traders

---

## 📚 Data Subscription

Once connected, the app automatically:
1. **Subscribes** to your selected asset (e.g., NIFTY)
2. **Receives** live price updates via WebSocket
3. **Displays** real-time data in charts
4. **Generates** signals based on live prices

No manual subscription needed!

---

## ⚙️ Advanced Configuration

### Change Connection Settings
Edit `analytics/dhan_websocket.py` if needed:
```python
self.ws_url = "wss://api-feed.dhan.co"  # WebSocket endpoint
```

### Monitor Connection
The app logs connection status:
- Connected → Shows in sidebar
- Disconnected → Falls back to yfinance
- Errors → Shown in Tab 6

---

## 🔐 Security Notes

- ✅ `.env` file is git-ignored (not committed)
- ✅ Credentials stay local (not sent anywhere)
- ✅ Only connects to official Dhan servers
- ⚠️ Keep your API key safe - don't share it!

---

## 📞 Support

- **Dhan Support**: https://dhanhq.com/support
- **Check Tab 6** in the app for detailed info
- **Restart the app** if connection drops

---

**Version**: 1.0
**Last Updated**: May 2026
